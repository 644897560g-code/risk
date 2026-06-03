"""Knowledge management API routes — file upload, list, delete, search, preview, tags, stats, extraction"""
import json
import os
import shutil
import threading
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel

from backend.app.config import get_settings
from backend.services.knowledge_extractor import (
    trigger_extraction,
    get_extraction,
    delete_extraction,
)

router = APIRouter()

ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".json", ".csv", ".xlsx", ".xls",
    ".py", ".sql", ".yaml", ".yml", ".pdf", ".doc", ".docx",
}

PREVIEW_EXTENSIONS = {".txt", ".md", ".json", ".csv", ".py", ".sql", ".yaml", ".yml"}


class KnowledgeItem(BaseModel):
    id: str
    filename: str
    size: int
    uploaded_at: str
    category: str  # doc | excel | code | other
    tags: List[str] = []


class KnowledgeListResponse(BaseModel):
    items: List[KnowledgeItem]
    total: int


class KnowledgeStats(BaseModel):
    total_files: int
    total_size: int
    by_category: dict


class DeleteResponse(BaseModel):
    status: str
    filename: str


class UpdateTagsBody(BaseModel):
    tags: List[str]


def _knowledge_dir() -> str:
    settings = get_settings()
    path = os.path.join(settings.data_dir, "user_knowledge")
    os.makedirs(path, exist_ok=True)
    return path


def _load_manifest() -> list:
    path = os.path.join(_knowledge_dir(), "_manifest.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def _save_manifest(manifest: list):
    path = os.path.join(_knowledge_dir(), "_manifest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def _category_for(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    doc_exts = {".txt", ".md", ".pdf", ".doc", ".docx"}
    excel_exts = {".xlsx", ".xls", ".csv"}
    code_exts = {".py", ".sql", ".yaml", ".yml", ".json"}
    if ext in doc_exts:
        return "doc"
    if ext in excel_exts:
        return "excel"
    if ext in code_exts:
        return "code"
    return "other"


@router.get("")
def api_list_knowledge(
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
) -> KnowledgeListResponse:
    """获取知识文件列表，支持分类筛选和搜索"""
    manifest = _load_manifest()

    items = []
    for item in manifest:
        # Filter by category
        if category and item.get("category") != category:
            continue
        # Search by filename
        if q and q.lower() not in item.get("filename", "").lower():
            continue
        items.append(KnowledgeItem(**item))

    return KnowledgeListResponse(items=items, total=len(items))


@router.get("/stats")
def api_knowledge_stats() -> KnowledgeStats:
    """获取知识文件统计"""
    manifest = _load_manifest()
    total_files = len(manifest)
    total_size = sum(m.get("size", 0) for m in manifest)

    by_category = {}
    for m in manifest:
        cat = m.get("category", "other")
        if cat not in by_category:
            by_category[cat] = {"count": 0, "size": 0}
        by_category[cat]["count"] += 1
        by_category[cat]["size"] += m.get("size", 0)

    return KnowledgeStats(
        total_files=total_files,
        total_size=total_size,
        by_category=by_category,
    )


@router.get("/{filename}/preview")
def api_preview_knowledge(filename: str, lines: int = Query(100, le=500)):
    """预览知识文件内容（纯文本格式，前 N 行）"""
    kdir = _knowledge_dir()
    file_path = os.path.join(kdir, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {filename}")

    ext = os.path.splitext(filename)[1].lower()
    if ext not in PREVIEW_EXTENSIONS:
        raise HTTPException(status_code=400, detail="该文件类型不支持预览")

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content_lines = []
            for i, line in enumerate(f):
                if i >= lines:
                    break
                content_lines.append(line.rstrip("\n"))
        return {
            "filename": filename,
            "total_lines": _count_lines(file_path),
            "preview_lines": lines,
            "content": "\n".join(content_lines),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取文件失败: {e}")


@router.post("/{filename}/tags")
def api_update_knowledge_tags(filename: str, body: UpdateTagsBody):
    """更新知识文件标签"""
    kdir = _knowledge_dir()
    file_path = os.path.join(kdir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {filename}")

    manifest = _load_manifest()
    updated = False
    for m in manifest:
        if m["filename"] == filename:
            m["tags"] = body.tags
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail=f"文件不在清单中: {filename}")

    _save_manifest(manifest)
    return {"status": "updated", "filename": filename, "tags": body.tags}


@router.post("/upload")
async def api_upload_knowledge(file: UploadFile = File(...)):
    """上传知识文件"""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")

    kdir = _knowledge_dir()
    file_path = os.path.join(kdir, file.filename or "unknown")

    # Save file
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Update manifest
    manifest = _load_manifest()
    # Remove existing entry with same filename
    manifest = [m for m in manifest if m["filename"] != file.filename]

    item = KnowledgeItem(
        id=f"k_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(manifest) + 1}",
        filename=file.filename or "unknown",
        size=len(content),
        uploaded_at=datetime.now().isoformat(),
        category=_category_for(file.filename or ""),
    )
    manifest.append(item.model_dump())
    _save_manifest(manifest)

    # Trigger extraction in background thread so upload returns instantly
    def _run_extraction_bg(fname: str):
        try:
            trigger_extraction(fname)
        except Exception as e:
            logger = __import__("logging").getLogger(__name__)
            logger.warning("Knowledge extraction failed for %s: %s", fname, e)

    thread = threading.Thread(
        target=_run_extraction_bg,
        args=(file.filename,),
        daemon=True,
    )
    thread.start()

    return {"status": "uploaded", "item": item.model_dump()}


@router.get("/{filename}/extraction")
def api_get_knowledge_extraction(filename: str):
    """获取知识文件的结构化提取结果"""
    extraction = get_extraction(filename)
    if extraction is None:
        raise HTTPException(status_code=404, detail=f"提取结果不存在: {filename}")
    return extraction


@router.delete("/{filename}")
def api_delete_knowledge(filename: str):
    """删除知识文件（同时清理提取结果）"""
    kdir = _knowledge_dir()
    file_path = os.path.join(kdir, filename)

    if os.path.exists(file_path):
        os.remove(file_path)
    else:
        raise HTTPException(status_code=404, detail=f"文件不存在: {filename}")

    manifest = _load_manifest()
    manifest = [m for m in manifest if m["filename"] != filename]
    _save_manifest(manifest)

    # Clean up extraction
    delete_extraction(filename)

    return DeleteResponse(status="deleted", filename=filename)


def _count_lines(filepath: str) -> int:
    """快速统计文件行数"""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0
