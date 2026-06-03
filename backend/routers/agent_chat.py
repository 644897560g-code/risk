"""Agent chat API route — LLM chat with channel1 template memory + tool calls"""
import asyncio
import json
import os
import re
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import get_db
from backend.models.chat import ChatSession, ChatMessage

router = APIRouter()


# ============================================================
#  Schemas
# ============================================================


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ToolCallInfo(BaseModel):
    tool: str
    status: str
    detail: str


class ChatResponse(BaseModel):
    reply: str
    tool_call: Optional[ToolCallInfo] = None
    conversation_id: str


# ============================================================
#  Session management
# ============================================================


@router.get("/chat/sessions")
def api_list_sessions(db: Session = Depends(get_db)):
    """List all chat sessions, newest first."""
    sessions = db.query(ChatSession).order_by(ChatSession.updated_at.desc()).all()
    return [s.to_dict() for s in sessions]


@router.get("/chat/sessions/{session_id}")
def api_get_session(session_id: str, db: Session = Depends(get_db)):
    """Get a single session with all its messages."""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session.to_dict(include_messages=True)


@router.delete("/chat/sessions/{session_id}")
def api_delete_session(session_id: str, db: Session = Depends(get_db)):
    """Delete a session and its messages."""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    db.delete(session)
    db.commit()
    return {"ok": True}


@router.delete("/chat/sessions")
def api_clear_sessions(db: Session = Depends(get_db)):
    """Delete all chat sessions."""
    db.query(ChatMessage).delete()
    db.query(ChatSession).delete()
    db.commit()
    return {"ok": True}


def _ensure_session(conv_id: str, db: Session) -> ChatSession:
    """Get or create a ChatSession for the given conversation_id."""
    session = db.query(ChatSession).filter(ChatSession.id == conv_id).first()
    if not session:
        session = ChatSession(id=conv_id, title="新对话")
        db.add(session)
        db.commit()
    return session


def _persist_message(session_id: str, role: str, content: str, db: Session, tool_call: Optional[dict] = None):
    """Write a single message to DB and update session timestamp/title."""
    msg = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        tool_call=tool_call,
    )
    db.add(msg)

    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session:
        session.updated_at = datetime.utcnow()
        # Auto-title: use first user message (first ~30 chars)
        if role == "user":
            msg_count = db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id, ChatMessage.role == "user"
            ).count()
            if msg_count <= 1:
                title = content.strip()[:30]
                if len(content) > 30:
                    title += "..."
                session.title = title

    db.commit()


# ============================================================
#  Chat endpoint
# ============================================================


@router.post("/chat")
def api_agent_chat(req: ChatRequest) -> ChatResponse:
    """Send a chat message to the LLM. System prompt includes channel1 templates + knowledge docs for context."""
    conv_id = req.conversation_id or str(uuid.uuid4())

    # 1. Build system prompt from channel1 templates
    system_prompt = _build_system_prompt()

    # 2. Call LLM
    try:
        llm = _get_llm_client()
        reply = llm.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.message},
        ])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM调用失败: {e}")

    # 3. Parse tool calls from reply
    tool_call = _parse_tool_call(reply)

    return ChatResponse(
        reply=reply,
        tool_call=tool_call,
        conversation_id=conv_id,
    )


@router.post("/chat/stream")
async def api_agent_chat_stream(req: ChatRequest, db: Session = Depends(get_db)):
    """SSE streaming chat — pushes LLM tokens as Server-Sent Events."""
    conv_id = req.conversation_id or str(uuid.uuid4())
    system_prompt = _build_system_prompt()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": req.message},
    ]

    # Ensure session exists in DB
    _ensure_session(conv_id, db)
    # Persist user message immediately
    _persist_message(conv_id, "user", req.message, db)

    async def event_generator():
        # Send conversation_id first
        yield f"data: {json.dumps({'type': 'meta', 'conversation_id': conv_id})}\n\n"

        full_reply = ""
        try:
            llm = _get_llm_client()
            for chunk in llm.chat_stream(messages):
                full_reply += chunk
                i = 0
                while i < len(chunk):
                    piece = chunk[i:i + 2]
                    yield f"data: {json.dumps({'type': 'chunk', 'content': piece})}\n\n"
                    i += 2
                    await asyncio.sleep(0.015)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"
            return

        # After full reply, parse tool call
        tool_call = _parse_tool_call(full_reply)
        tool_call_dict = {"tool": tool_call.tool, "status": tool_call.status, "detail": tool_call.detail} if tool_call else None

        if tool_call:
            yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_call.tool, 'status': tool_call.status, 'detail': tool_call.detail})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

        # Persist assistant message after streaming completes
        _persist_message(conv_id, "assistant", full_reply, db, tool_call=tool_call_dict)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================
#  Helpers
# ============================================================


def _build_system_prompt() -> str:
    """Build system prompt with channel1 template context + knowledge documents."""
    settings = get_settings()

    # ---- channel1 templates ----
    templates_path = os.path.join(settings.data_dir, "templates", "channel1_templates.json")
    alt_path = os.path.join(settings.output_dir, "feature_templates", "channel1_templates.json")

    templates = []
    for p in (templates_path, alt_path):
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    items = data.get("templates", data.get("items", []))
                else:
                    items = data
                templates = items
                break
            except (json.JSONDecodeError, IOError):
                continue

    template_lines = []
    for t in templates:
        tid = t.get("template_id", t.get("name", "?"))
        desc = t.get("description", "")
        dim = t.get("dimension", "")
        dsl = t.get("dsl", "")
        template_lines.append(
            f"## {tid}\n"
            f"- 维度: {dim}\n"
            f"- 描述: {desc}\n"
            f"- DSL: {dsl}\n"
        )

    templates_section = "\n".join(template_lines) if template_lines else "（暂无已生效模板）"

    # ---- knowledge documents ----
    knowledge_section = _build_knowledge_section(settings)

    return f"""你是一个风控特征挖掘系统的AI助手，负责帮助用户设计和创建风险特征模板。

## 系统能力

1. **回答特征挖掘相关问题** — 基于已生效的通道1模板，回答用户关于特征设计、风险分析的咨询
2. **创建通道2特征模板** — 用户提出新特征需求时，输出JSON格式的 tool call 来触发模板创建

## 已生效的通道1模板（参考用）

以下模板已经部署到生产环境，设计新特征时请参考它们的模式和风格：

{templates_section}

## 知识文档上下文

以下知识文档由用户上传，请根据这些文档内容回答相关问题：

{knowledge_section}

## Tool Call 格式

当用户要求创建新特征模板时，在回复末尾输出以下JSON：

```json
{{"tool": "trigger_channel2", "template_name": "特征名称（snake_case，不含具体业务值）", "dimension": "维度", "description": "特征描述（抽象计算逻辑，不含具体业务值）", "dsl": "DSL表达式", "python_function": "Python函数签名", "python_code": "完整Python计算代码"}}
```

请确保：
- template_name 使用英文，snake_case，**必须剥离业务含义**（如用 category_count 代替 gambling_app_count）
- description 描述计算逻辑，**不含具体业务值**，把业务值放到 parameter_space 中
- dimension 可选值: applist, fdc, base, behavior
- **DSL 不能与已生效模板重复**：创建前对照已生效模板列表，确保 DSL 的计算模式未被覆盖
- 不输出 tool call 格式以外的JSON
- 如果用户只是咨询，不需要创建模板，则只回复文本

## 回答风格

- 专业、简洁
- 中文回复
- 涉及特征时引用具体的数据维度和模板
"""


def _build_knowledge_section(settings) -> str:
    """Format knowledge files for the system prompt.

    Priority: structured extraction JSON → compact summary per file.
    Fallback: raw text preview (50 lines / 4KB max per file).
    """
    kdir = os.path.join(settings.data_dir, "user_knowledge")
    if not os.path.isdir(kdir):
        return "（暂无知识文档）"

    parts = []
    text_exts = {".txt", ".md", ".json", ".csv", ".py", ".sql", ".yaml", ".yml"}

    for fname in sorted(os.listdir(kdir)):
        if fname == "_manifest.json":
            continue
        ext = os.path.splitext(fname)[1].lower()
        if ext not in text_exts:
            continue

        # Try structured extraction first
        extraction = _load_extraction(fname)
        if extraction and not extraction.get("error"):
            summary = _format_extraction_summary(fname, extraction)
            parts.append(summary)
            continue

        # Fallback: read raw content (limited)
        fpath = os.path.join(kdir, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                lines = []
                total_bytes = 0
                for line in f:
                    lines.append(line.rstrip("\n"))
                    total_bytes += len(line.encode("utf-8"))
                    if len(lines) >= 50 or total_bytes > 4096:
                        break
            content = "\n".join(lines)
            parts.append(f"### {fname} [原始内容]\n```\n{content}\n```\n")
        except (IOError, OSError):
            continue

    if not parts:
        return "（暂无知识文档）"

    return "\n".join(parts)


def _load_extraction(fname: str) -> Optional[dict]:
    """Load extraction JSON for *fname* if it exists."""
    from backend.services.knowledge_extractor import get_extraction
    return get_extraction(fname)


def _format_extraction_summary(fname: str, ext: dict) -> str:
    """Format a structured extraction as a compact text block (5-15 lines)."""
    lines = [f"### {fname} [知识提取]"]
    lines.append(f"类型: {ext.get('file_type', '?')} | 摘要: {ext.get('overall_summary', '')}")

    file_type = ext.get("file_type")

    if file_type == "doc":
        insights = ext.get("key_insights", [])
        for ins in insights[:5]:
            lines.append(f"- {ins}")
        rules = ext.get("business_rules", [])
        for r in rules[:3]:
            lines.append(f"- 规则: {r}")
        fields = ext.get("data_fields", [])
        if fields:
            field_desc = ", ".join(f"{f.get('name','')}({f.get('type','')})" for f in fields[:8])
            lines.append(f"数据字段: {field_desc}")

    elif file_type == "code":
        funcs = ext.get("functions", [])
        for fn in funcs[:5]:
            params = ", ".join(p.get("name", "") for p in fn.get("parameters", []))
            lines.append(f"- {fn.get('name', '?')}({params}) → {fn.get('return_type','?')} [{fn.get('computation_pattern','')}]")
        imports = ext.get("imports", [])
        if imports:
            lines.append(f"依赖: {', '.join(imports[:5])}")

    elif file_type == "table":
        schema = ext.get("schema", [])
        if schema:
            col_desc = ", ".join(f"{c.get('name','')}({c.get('inferred_type','')})" for c in schema[:10])
            lines.append(f"列: {col_desc}")
        stats = ext.get("statistical_patterns", [])
        for s in stats[:5]:
            lines.append(f"- {s.get('metric','')}={s.get('value','')} ({s.get('interpretation','')})")
        rc = ext.get("row_count")
        if rc:
            lines.append(f"行数: {rc}")

    return "\n".join(lines) + "\n"


def _get_llm_client():
    """Lazy import LLMClient to avoid import errors when env not configured."""
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    from utils.llm_client import LLMClient
    return LLMClient()


def _parse_tool_call(reply: str) -> Optional[ToolCallInfo]:
    """Parse tool call JSON from LLM reply."""
    # Match ```json ... ``` blocks
    json_blocks = re.findall(r'```json\s*(\{.*?\})\s*```', reply, re.DOTALL)

    for block in json_blocks:
        try:
            payload = json.loads(block)
        except json.JSONDecodeError:
            continue

        if payload.get("tool") == "trigger_channel2":
            return _execute_trigger_channel2(payload)

    # Also try to find inline JSON
    inline_match = re.search(r'\{\s*"tool"\s*:\s*"trigger_channel2".*?\}', reply, re.DOTALL)
    if inline_match:
        try:
            payload = json.loads(inline_match.group())
            return _execute_trigger_channel2(payload)
        except json.JSONDecodeError:
            pass

    return None


def _execute_trigger_channel2(payload: dict) -> ToolCallInfo:
    """Execute channel2 template creation from tool call payload."""
    settings = get_settings()
    pending_dir = os.path.join(settings.output_dir, "feature_design")
    os.makedirs(pending_dir, exist_ok=True)
    pending_path = os.path.join(pending_dir, "channel2_pending.json")

    # Read existing pending list + channel1 templates for dedup
    ch1_dsls = _load_channel1_dsls_normalized()

    template_entry = {
        "template_id": payload.get("template_name", "unknown"),
        "template_name": payload.get("template_name", ""),
        "dimension": payload.get("dimension", ""),
        "description": payload.get("description", ""),
        "dsl": payload.get("dsl", ""),
        "python_function": payload.get("python_function", ""),
        "python_code": payload.get("python_code", ""),
        "source": "agent chat",
        "_promotion_status": "pending",
        "created_at": datetime.now().isoformat(),
    }

    # DSL dedup: skip if this template's DSL matches a channel1 template
    dsl = template_entry.get("dsl", "")
    if dsl:
        norm = re.sub(r"\b\d+\b", "*", dsl)
        norm = re.sub(r"\s+", "", norm)
        # Also normalize channel1 DSLs the same way
        norm_ch1 = {re.sub(r"\s+", "", re.sub(r"\b\d+\b", "*", d)) for d in ch1_dsls}
        if norm in norm_ch1:
            return ToolCallInfo(
                tool="trigger_channel2",
                status="skipped",
                detail=f"模板「{template_entry['template_name']}」的DSL与已生效模板重复，已跳过",
            )

    # Read existing pending list
    existing = []
    if os.path.exists(pending_path):
        try:
            with open(pending_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing = []

    existing.append(template_entry)

    with open(pending_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    return ToolCallInfo(
        tool="trigger_channel2",
        status="success",
        detail=f"模板「{template_entry['template_name']}」已加入通道2待审批列表",
    )


def _load_channel1_dsls_normalized() -> set:
    """Load channel1 template DSLs as a set for dedup checking."""
    settings = get_settings()
    primary = os.path.join(settings.output_dir, "feature_templates", "channel1_templates.json")
    fallback = os.path.join(settings.data_dir, "templates", "channel1_templates.json")
    path = primary if os.path.exists(primary) else fallback
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data if isinstance(data, list) else data.get("templates", data.get("items", []))
        return {item.get("dsl", "") for item in items if item.get("dsl")}
    except (json.JSONDecodeError, OSError):
        return set()
