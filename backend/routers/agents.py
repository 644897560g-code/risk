"""Agent orchestrator control + human review API routes"""
import json
import os
import threading
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import get_db
from backend.auth.deps import get_current_user
from backend.models.user import User
from backend.services.task_service import create_task, add_task_log, update_task_status, save_task_result
from backend.services.template_library import (
    PENDING_STATUS,
    append_template_python_code,
    approve_template,
    list_templates,
    reject_template,
    template_to_pending_item,
)

router = APIRouter()


# ============================================================
#  Orchestrator endpoints
# ============================================================


@router.get("/orchestrator/status")
def api_orchestrator_status():
    """获取 Orchestrator 当前状态"""
    settings = get_settings()
    state_path = os.path.join(settings.output_dir, "feature_code", "orchestrator_state.json")

    state = {}
    if os.path.exists(state_path):
        with open(state_path) as f:
            try:
                state = json.load(f)
            except json.JSONDecodeError:
                state = {"status": "error", "error": "orchestrator_state.json 解析失败"}

    # 累计通过特征数
    acc_path = os.path.join(settings.evaluation_dir, "accumulated_passed_features.json")
    accumulated_passed = 0
    if os.path.exists(acc_path):
        with open(acc_path) as f:
            acc = json.load(f)
        accumulated_passed = acc.get("total_passed", 0)

    # 最新部署版本
    latest_version = ""
    if os.path.exists(settings.deployment_dir):
        versions = [d for d in os.listdir(settings.deployment_dir)
                    if d.startswith("v") and os.path.isdir(os.path.join(settings.deployment_dir, d))]
        if versions:
            versions.sort(key=lambda v: int(v[1:]))
            latest_version = versions[-1]

    return {
        "status": state.get("status", "idle"),
        "current_step": state.get("current_step", ""),
        "completed_steps": state.get("completed_steps", []),
        "start_time": state.get("start_time"),
        "end_time": state.get("end_time"),
        "error": state.get("error"),
        "accumulated_passed": accumulated_passed,
        "latest_version": latest_version,
    }


@router.post("/orchestrator/run")
def api_orchestrator_run(db: Session = Depends(get_db)):
    """后台启动 Orchestrator 批量特征生产"""
    task = create_task(db, "批量特征生产", "mass_production")
    update_task_status(db, task.id, status="running", progress=5.0)
    add_task_log(db, task.id, "info", "任务已创建，后台执行中...")

    def _run_background(task_id: int):
        import sys
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
        from backend.app.database import SessionLocal
        from agents.feature_orchestrator import FeatureOrchestrator

        _db = SessionLocal()
        try:
            add_task_log(_db, task_id, "info", "开始批量特征生产...")
            update_task_status(_db, task_id, status="running", progress=10.0)

            orch = FeatureOrchestrator()
            orch.run_mass_production()

            add_task_log(_db, task_id, "info", "批量生产完成")
            settings = get_settings()
            pf_path = os.path.join(settings.evaluation_dir, "passed_features.json")
            if os.path.exists(pf_path):
                with open(pf_path) as f:
                    pf = json.load(f)
                save_task_result(_db, task_id, {
                    "passed": pf.get("passed", 0),
                    "total": pf.get("total_features", 0),
                })
            else:
                update_task_status(_db, task_id, status="completed", progress=100.0)
        except Exception as e:
            import traceback
            error_msg = f"批量生产失败: {e}"
            traceback.print_exc()
            try:
                add_task_log(_db, task_id, "error", error_msg)
                update_task_status(_db, task_id, status="failed", progress=0.0, error_message=str(e))
            except Exception:
                pass
        finally:
            _db.close()

    t = threading.Thread(target=_run_background, args=(task.id,), daemon=True)
    t.start()
    return {"task_id": task.id, "status": "created"}


@router.get("/orchestrator/logs")
def api_orchestrator_logs(lines: int = 50):
    """获取 Orchestrator 日志最后 N 行"""
    settings = get_settings()
    log_path = os.path.join(settings.output_dir, "feature_code", "orchestrator.log")
    if not os.path.exists(log_path):
        return {"lines": []}

    with open(log_path, "r", encoding="utf-8") as f:
        all_lines = f.readlines()

    return {"lines": all_lines[-lines:]}


# ============================================================
#  Review endpoints
# ============================================================


class RejectBody(BaseModel):
    reason: str = ""


# --- Channel 2 template approvals ---


@router.get("/reviews/channel2-pending")
def api_channel2_pending(db: Session = Depends(get_db)):
    """获取待审批的通道2模板列表"""
    items = list_templates(db, status=PENDING_STATUS)
    return {"items": [template_to_pending_item(t) for t in items]}


@router.post("/reviews/channel2-pending/{template_id}/approve")
def api_channel2_approve(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """审批通过通道2模板（晋升为通道1）"""
    try:
        template = approve_template(db, template_id, reviewer=current_user.username)
        append_template_python_code(template)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")
    return {"status": "approved", "template_id": template_id}


@router.post("/reviews/channel2-pending/{template_id}/reject")
def api_channel2_reject(
    template_id: str,
    body: RejectBody = RejectBody(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """拒绝通道2模板，并写入审批历史和被拒记忆"""
    if not body.reason:
        raise HTTPException(status_code=400, detail="驳回原因必填")
    try:
        reject_template(db, template_id, reason=body.reason, reviewer=current_user.username)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")
    return {"status": "rejected", "template_id": template_id}


# --- Feature review confirmations ---


@router.get("/reviews/feature-review")
def api_feature_review():
    """获取特征审核结果"""
    path = _feature_review_path()
    if not os.path.exists(path):
        return {"exists": False, "review": None}

    with open(path, "r", encoding="utf-8") as f:
        try:
            review = json.load(f)
        except json.JSONDecodeError:
            return {"exists": False, "review": None}

    return {"exists": True, "review": review}


@router.post("/reviews/feature-review/confirm")
def api_feature_review_confirm():
    """确认通过特征审核"""
    path = _feature_review_path()
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="审核结果文件不存在")

    with open(path, "r", encoding="utf-8") as f:
        review = json.load(f)

    review["human_confirmed"] = True
    review["final_passed"] = True
    review["confirmed_at"] = datetime.now().isoformat()

    with open(path, "w", encoding="utf-8") as f:
        json.dump(review, f, ensure_ascii=False, indent=2)

    return {"status": "confirmed"}


@router.post("/reviews/feature-review/reject")
def api_feature_review_reject(body: RejectBody = RejectBody()):
    """退回特征审核"""
    path = _feature_review_path()
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="审核结果文件不存在")

    with open(path, "r", encoding="utf-8") as f:
        review = json.load(f)

    review["human_confirmed"] = False
    review["final_passed"] = False
    review["rejection_reason"] = body.reason
    review["rejected_at"] = datetime.now().isoformat()

    with open(path, "w", encoding="utf-8") as f:
        json.dump(review, f, ensure_ascii=False, indent=2)

    return {"status": "rejected"}


# ============================================================
#  Helpers
# ============================================================


def _feature_review_path() -> str:
    settings = get_settings()
    return os.path.join(settings.output_dir, "feature_code", "review_result.json")
