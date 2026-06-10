"""
Knowledge extraction service — upload a file → LLM extracts template(s) → store pending templates.

Each file may yield 0..N template records aligned with the channel2 pending template schema.
Templates are written to PostgreSQL templates with status="pending" and source="知识".
"""
import json
import logging
import os
import re
from datetime import datetime
from typing import List, Optional

from backend.app.config import get_settings
from backend.app.database import SessionLocal
from backend.services.template_library import (
    active_dsl_set,
    format_active_templates_for_prompt,
    upsert_template_from_payload,
)

logger = logging.getLogger(__name__)

EXTRACTION_VERSION = "1.0"
EXTRACTION_DIR_NAME = "user_knowledge_extracted"
MAX_PREVIEW_LINES = 300
MAX_PREVIEW_BYTES = 16384

TEXT_EXTENSIONS = {".txt", ".md", ".json", ".csv", ".py", ".sql", ".yaml", ".yml"}

# A real channel2 template example injected into the prompt so the LLM sees the target format.
_CHANNEL2_EXAMPLE = json.dumps(
    {
        "template_name": "recency_days",
        "template_name_cn": "最近事件距今天数",
        "dimension": "change",
        "complexity": "L1",
        "description": "计算用户在指定时间窗口内，最近一次发生目标事件距离当前申请时间的天数。",
        "dsl": "apply_time_dt - max(time_field, window)",
        "dsl_description": "在指定窗口内过滤事件记录，提取时间字段的最大值，计算与申请时间的差值。",
        "parameter_space": {
            "source": {"type": "string", "description": "数据源: applist/fdc_inquiry/fdc_pinjaman/base"},
            "window": {"type": "int", "description": "回溯窗口天数, 如30/60/90"},
            "time_field": {"type": "string", "description": "事件时间字段名"},
            "default_value": {"type": "int", "description": "无事件时的默认返回值"},
        },
        "python_function": "calc_recency_days(data, apply_time_dt, window_days=90, time_field='event_time', default_value=180, source='fdc_inquiry')",
        "python_code": "# 包含防穿越逻辑的完整计算函数\nfrom datetime import datetime\n\ndef calc_recency_days(data, apply_time_dt, window_days=90, time_field='event_time', default_value=180, source='fdc_inquiry'):\n    events = data.get(source, [])\n    if not events:\n        return float(default_value)\n    valid_times = []\n    for evt in events:\n        t = evt.get(time_field)\n        if t and t <= apply_time_dt.isoformat():\n            valid_times.append(datetime.fromisoformat(t))\n    if not valid_times:\n        return float(default_value)\n    delta = (apply_time_dt - max(valid_times)).total_seconds() / 86400.0\n    return max(0.0, delta)",
        "formula_template": "申请时间 - 近{window}天内最近一次{time_field}的时间",
        "examples": ["近90天FDC多头查询距今天数", "近60天博彩APP安装距今天数"],
    },
    ensure_ascii=False,
    indent=2,
)


# ---------------------------------------------------------------------------
# Channel1 DSL list (for dedup)
# ---------------------------------------------------------------------------

def _load_channel1_dsls() -> set:
    """Load active template DSLs as a normalized set for dedup checking."""
    db = SessionLocal()
    try:
        return active_dsl_set(db)
    finally:
        db.close()


def _format_channel1_for_prompt() -> str:
    """Load channel1 templates and format as a compact text block for the LLM prompt.

    Returns a string listing each template's ID, name, normalized DSL, and description,
    so the LLM can judge whether a new extraction is redundant.
    """
    db = SessionLocal()
    try:
        return format_active_templates_for_prompt(db)
    finally:
        db.close()


def _normalize_dsl(dsl: str) -> str:
    """Normalize a DSL string to a canonical form for dedup comparison.

    Replaces parameter names and specific values with wildcards so that
    e.g. 'count_distinct(institution, filter(history_inquiry, inquiry_time
    >= apply_time_dt - 30))' and 'distinct(dedup_field, field_set, window)'
    can be compared structurally.
    """
    normalized = dsl.strip()
    # Remove inline filter expressions with specific values (e.g. =='active')
    normalized = re.sub(r"==\s*['\"]?\w+['\"]?", "==*", normalized)
    # Replace quoted strings (e.g. 'gambling', "loan") with *
    normalized = re.sub(r"['\"][^'\"]*['\"]", "*", normalized)
    # Replace numbers with *
    normalized = re.sub(r"\b\d+\b", "*", normalized)
    # Replace parameter-like names inside parentheses with *
    # e.g. count(field_set, window, cond) → count(*, *, *)
    normalized = re.sub(r"(?<=[\s(,])[a-z_][a-z0-9_]*(?=[,)\s])", "*", normalized)
    # Collapse multiple * into one
    normalized = re.sub(r"\*\s*\*", "*", normalized)
    # Collapse whitespace
    normalized = re.sub(r"\s+", "", normalized)
    return normalized


def _dedup_vs_channel1(templates: list) -> list:
    """Filter out templates whose DSL already exists in channel1 templates.

    Uses _normalize_dsl() to compare computational structure ignoring
    parameter/field names and specific values.
    """
    channel1_dsls = _load_channel1_dsls()
    if not channel1_dsls:
        return templates

    kept = []
    for t in templates:
        dsl = t.get("dsl", "")
        if not dsl:
            kept.append(t)
            continue
        normalized = _normalize_dsl(dsl)
        if normalized in channel1_dsls:
            logger.info(
                "Skipping template '%s' — DSL '%s' normalized to '%s' already exists in channel1",
                t.get("template_name"), dsl, normalized,
            )
            continue
        kept.append(t)
    return kept


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def trigger_extraction(filename: str) -> dict:
    """
    Synchronous extraction workflow (call from a background thread).
    1. Read file text preview
    2. Classify file type
    3. Build LLM prompt & call (outputs template-aligned JSON)
    4. Parse & persist extraction result
    5. Store each returned template as pending in PostgreSQL
    """
    settings = get_settings()
    knowledge_dir = os.path.join(settings.data_dir, "user_knowledge")
    filepath = os.path.join(knowledge_dir, filename)

    if not os.path.exists(filepath):
        logger.warning("Extraction skipped — file not found: %s", filename)
        return {"error": "file_not_found"}

    content = _read_file_preview(filepath)
    file_type = _classify_file(filename)
    file_size = os.path.getsize(filepath)

    try:
        response = _call_llm_for_extraction(filename, file_type, content)
        extracted = _parse_llm_response(response, filename, file_type, file_size)
    except Exception as e:
        logger.error("LLM extraction failed for %s: %s", filename, e)
        extracted = {
            "extraction_version": EXTRACTION_VERSION,
            "extracted_at": datetime.now().isoformat(),
            "filename": filename,
            "file_type": file_type,
            "file_size": file_size,
            "templates": [],
            "error": str(e),
        }

    # Always persist raw extraction result for debugging
    _write_extraction(filename, extracted)

    # Store each template as pending in PostgreSQL
    templates = extracted.get("templates", [])
    if templates:
        _push_to_template_library(filename, templates)

    return extracted


def get_extraction(filename: str) -> Optional[dict]:
    """Read persisted extraction JSON for *filename*, or None."""
    path = _extraction_path(filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def delete_extraction(filename: str):
    """Remove extraction JSON for *filename* if it exists."""
    path = _extraction_path(filename)
    if os.path.exists(path):
        os.remove(path)


# ---------------------------------------------------------------------------
# Push to template library pending
# ---------------------------------------------------------------------------

def _push_to_template_library(source_filename: str, templates: list):
    """Write extracted template records into PostgreSQL as pending templates."""
    now = datetime.now()
    ts = now.strftime("%Y%m%d%H%M%S")
    db = SessionLocal()
    try:
        for i, tpl in enumerate(templates):
            tpl["template_id"] = tpl.get("template_id") or f"K_{ts}_{i + 1}"
            tpl["source"] = "知识"
            tpl["_promotion_status"] = "pending"
            tpl["created_at"] = now.isoformat()
            tpl["_source_file"] = source_filename
            upsert_template_from_payload(
                db,
                tpl,
                status="pending",
                source_channel=3,
                source="知识",
                commit=False,
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    logger.info("Pushed %d template(s) from '%s' to template library pending", len(templates), source_filename)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extraction_path(filename: str) -> str:
    settings = get_settings()
    d = os.path.join(settings.data_dir, EXTRACTION_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{filename}.extraction.json")


def _read_file_preview(filepath: str) -> str:
    """Read up to MAX_PREVIEW_LINES / MAX_PREVIEW_BYTES of text content."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in TEXT_EXTENSIONS:
        return "[Binary file — preview not available]"
    try:
        lines = []
        total_bytes = 0
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                total_bytes += len(line.encode("utf-8"))
                if len(lines) >= MAX_PREVIEW_LINES or total_bytes > MAX_PREVIEW_BYTES:
                    break
                lines.append(line.rstrip("\n"))
        return "\n".join(lines)
    except Exception as e:
        logger.warning("Failed to read file preview: %s", e)
        return "[Error reading file]"


def _classify_file(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    doc_exts = {".txt", ".md", ".pdf", ".doc", ".docx"}
    code_exts = {".py", ".sql", ".yaml", ".yml", ".json"}
    table_exts = {".csv", ".xlsx", ".xls"}
    if ext in doc_exts:
        return "doc"
    if ext in code_exts:
        return "code"
    if ext in table_exts:
        return "table"
    return "doc"  # fallback


def _build_extraction_prompt(filename: str, file_type: str, content: str) -> list:
    """Build system + user message list — output is a {templates: [...]} JSON aligned with channel2 schema."""

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Load channel1 templates for dedup context
    channel1_context = _format_channel1_for_prompt()

    system_prompt = f"""你是一个风控特征挖掘领域的知识提取专家。当前时间：{now}

## 任务
分析用户上传的文件内容，判断其中能提取出多少个**风险特征模板**。
输出格式为 JSON 对象，包含一个 "templates" 数组。如果文件内容不能提取任何模板，返回 {{"templates": []}}。

## 模板 JSON 字段说明

每个模板的 JSON schema 如下：

```json
{{
  "template_name": "英文snake_case命名，如 recency_days",
  "template_name_cn": "中文名称，如 最近事件距今天数",
  "dimension": "模板计算维度: volume | structure | change | position | consistency | relation | derived",
  "complexity": "复杂度: L1(简单) | L2(中等) | L3(复杂)",
  "description": "详细描述该模板的计算逻辑和业务含义",
  "dsl": "DSL表达式，描述计算公式，如 apply_time_dt - max(time_field, window)",
  "dsl_description": "DSL表达式的自然语言解释",
  "parameter_space": {{
    "参数名": {{"type": "string|int|float", "description": "参数含义说明"}}
  }},
  "python_function": "函数签名，如 calc_recency_days(data, apply_time_dt, window_days=90, time_field='event_time')",
  "python_code": "完整的Python计算函数代码（包含防穿越逻辑，从订单数据中提取字段计算）",
  "formula_template": "自然语言公式模板，如 申请时间 - 近{{window}}天内最近一次{{time_field}}的时间",
  "examples": ["示例一", "示例二"]
}}
```

## 重要规则

1. **只为确实可以作为风险特征的内容创建模板，且该计算逻辑尚未被已生效模板覆盖**。不要强行提取。
2. **防穿越原则**：所有时间相关计算必须基于申请时间（apply_time_dt）之前的数据。
3. 每个模板的 python_code 必须包含完整可运行的函数。
4. dimension 取值必须是平台模板计算维度之一：volume(数量统计), structure(结构占比), change(变化趋势), position(位置排名), consistency(一致性校验), relation(关系识别), derived(衍生计算)。
5. templates 数组为空表示没提取到任何模板。
6. 输出必须是合法的 JSON，不要包含额外的markdown标记或说明文字。
7. **模板必须剥离业务含义**：从文件中识别出的风险信号（如"赌博应用占比高"、"现金贷多头借贷"）应该抽象为通用计算结构（如 count(filter(source, category==target), window) / count(source, window)），把具体的业务值（赌博、现金贷等）放到 parameter_space 中。模板名和描述不能包含具体业务词（如 high_risk、gambling、loan）。
8. **DSL 不能与已生效模板重复**：如果提取出的计算逻辑已经有一个通道1模板实现了，则跳过该模板。以下是已生效模板的 DSL 列表供参考：

{channel1_context}

## 参考示例（真实通道2模板）

以下是一个已通过的通道2模板示例，请参考其格式和质量。注意该模板已经做到了剥离业务含义：

```json
{_CHANNEL2_EXAMPLE}
```"""

    user_prompt = f"文件名称：{filename}\n文件类型：{file_type}\n\n文件内容：\n```\n{content}\n```"

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _call_llm_for_extraction(filename: str, file_type: str, content: str) -> str:
    """Call the LLM with the extraction prompt and return raw response text."""
    from utils.llm_client import LLMClient

    messages = _build_extraction_prompt(filename, file_type, content)

    client = LLMClient()
    response = client.chat(messages, temperature=0, max_tokens=8192)
    return response


def _parse_llm_response(response: str, filename: str, file_type: str, file_size: int) -> dict:
    """Parse the LLM response JSON, with fallback error handling."""
    result = {
        "extraction_version": EXTRACTION_VERSION,
        "extracted_at": datetime.now().isoformat(),
        "filename": filename,
        "file_type": file_type,
        "file_size": file_size,
        "templates": [],
    }

    # Try to extract JSON from markdown code block first
    json_str = None
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
    else:
        # Try to find a top-level JSON object
        brace_match = re.search(r"\{[\s\S]*\}", response)
        if brace_match:
            json_str = brace_match.group(0)

    if not json_str:
        result["overall_summary"] = ""
        result["error"] = "LLM returned non-JSON response"
        return result

    try:
        parsed = json.loads(json_str)
        result.update(parsed)
    except json.JSONDecodeError as e:
        result["overall_summary"] = ""
        result["error"] = f"JSON parse error: {e}"
        return result

    # Dedup: remove templates whose DSL matches an existing channel1 template
    templates = result.get("templates", [])
    if templates:
        deduped = _dedup_vs_channel1(templates)
        if len(deduped) < len(templates):
            logger.info(
                "Dedup filtered %d/%d templates for '%s'",
                len(templates) - len(deduped), len(templates), filename,
            )
        result["templates"] = deduped

    return result


def _write_extraction(filename: str, data: dict):
    """Persist extraction dict to disk."""
    path = _extraction_path(filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("Extraction saved: %s (templates=%d)", path, len(data.get("templates", [])))
