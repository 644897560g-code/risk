"""Template management API routes — channel1 + channel2 pending"""
import ast
import json
import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import get_db
from backend.services.task_service import get_task_list

router = APIRouter()


class Channel1Template(BaseModel):
    template_id: str
    template_name: str
    dimension: str
    description: str = ""
    dsl: str
    python_function: str
    python_code: str = ""


class Channel1ListResponse(BaseModel):
    items: List[Channel1Template]
    total: int


class PendingTemplateItem(BaseModel):
    template_id: str
    template_name: str
    dimension: str
    description: str
    iv: float = 0
    psi: float = 0
    coverage: float = 0
    dsl: str = ""
    python_function: str = ""
    python_code: str = ""
    created_at: str = ""
    source: str = ""


class PendingListResponse(BaseModel):
    items: List[PendingTemplateItem]
    total: int


def _channel1_path() -> str:
    settings = get_settings()
    # 优先 output_dir/feature_templates（LLM生成的路径），回退到 data/templates
    primary = os.path.join(settings.output_dir, "feature_templates", "channel1_templates.json")
    if os.path.exists(primary):
        return primary
    return os.path.join(settings.data_dir, "templates", "channel1_templates.json")


def _channel2_pending_path() -> str:
    settings = get_settings()
    return os.path.join(settings.output_dir, "feature_design", "channel2_pending.json")


@router.get("/channel1")
def api_list_channel1_templates() -> Channel1ListResponse:
    """获取已生效的通道1模板列表"""
    path = _channel1_path()
    if not os.path.exists(path):
        return Channel1ListResponse(items=[], total=0)

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return Channel1ListResponse(items=[], total=0)

    # Normalize: might be list or dict with "templates" key
    if isinstance(data, dict):
        items = data.get("templates", data.get("items", []))
    else:
        items = data

    return Channel1ListResponse(items=items, total=len(items))


@router.get("/channel2-pending")
def api_list_channel2_pending() -> PendingListResponse:
    """获取待审核的通道2模板列表"""
    path = _channel2_pending_path()
    if not os.path.exists(path):
        return PendingListResponse(items=[], total=0)

    with open(path, "r", encoding="utf-8") as f:
        try:
            items = json.load(f)
        except json.JSONDecodeError:
            return PendingListResponse(items=[], total=0)

    return PendingListResponse(items=items, total=len(items))


def _find_template_code(template_id: str) -> str:
    """从 channel1_templates.json 查找 python_module + python_function，读取对应文件中的源码"""
    path = _channel1_path()
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return ""
    items = data if isinstance(data, list) else data.get("templates", data.get("items", []))
    for item in items:
        if item.get("template_id") == template_id:
            module = item.get("python_module", "")
            func = item.get("python_function", "")
            if not module or not func:
                return ""
            settings = get_settings()
            pr = settings.project_root
            possible_paths = [
                os.path.join(pr, "agents", f"{module}.py"),
                os.path.join(pr, "outputs", "feature_code", f"{module}.py"),
                os.path.join(pr, f"{module}.py"),
            ]
            for p in possible_paths:
                if os.path.exists(p):
                    return _extract_function_source(p, func)
            return ""
    return ""


def _extract_function_source(filepath: str, func_name: str) -> str:
    """解析 Python 文件，提取指定函数的完整源代码"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                return ast.get_source_segment(source, node) or ""
        return ""
    except Exception:
        return ""


@router.get("/channel1/{template_id}/code")
def api_channel1_template_code(template_id: str) -> dict:
    """获取通道1模板的完整Python函数源代码"""
    code = _find_template_code(template_id)
    return {"template_id": template_id, "code": code}
