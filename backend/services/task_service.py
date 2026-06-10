"""Task service — CRUD + business logic"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.models.task import Task, TaskLog
from backend.models.feature import FeatureVersion, FeatureMetric
from backend.services.template_library import PENDING_STATUS, list_templates


def create_task(db: Session, name: str, mode: str, config: dict = None,
                linked_task_id: int = None, scheduled_at: datetime = None) -> Task:
    """创建新任务。"""
    task = Task(
        name=name or f"{mode} 任务",
        mode=mode,
        status="pending",
        progress=0.0,
        config=config,
        linked_task_id=linked_task_id,
        scheduled_at=scheduled_at,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_task(db: Session, task_id: int) -> Optional[Task]:
    return db.query(Task).filter(Task.id == task_id).first()


def get_task_list(db: Session, skip: int = 0, limit: int = 50,
                  mode: str = None) -> tuple[List[Task], int]:
    q = db.query(Task)
    if mode:
        q = q.filter(Task.mode == mode)
    else:
        # 默认排除旧的关联模板任务（linked_task_id is not null 的 template_task）
        q = q.filter(~((Task.mode == "template_task") & Task.linked_task_id.isnot(None)))
    total = q.count()
    items = q.order_by(Task.id.desc()).offset(skip).limit(limit).all()
    return items, total


def add_task_log(db: Session, task_id: int, level: str, message: str):
    log = TaskLog(task_id=task_id, level=level, message=message)
    db.add(log)
    db.commit()


def update_task_status(db: Session, task_id: int, **kwargs):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        for k, v in kwargs.items():
            setattr(task, k, v)
        db.commit()


def save_task_result(db: Session, task_id: int, result: Dict):
    """保存任务执行结果到数据库（特征指标 + 版本记录）"""
    settings = get_settings()

    passed = result.get("passed", 0)
    total = result.get("total", 0)

    # 读取 passed_features.json 获取版本信息
    passed_path = os.path.join(settings.evaluation_dir, "passed_features.json")
    deployed_version = None
    if os.path.exists(passed_path):
        with open(passed_path) as f:
            data = json.load(f)

        passed_features = data.get("passed_features", [])
        failed_features = data.get("failed_features", [])

        # 找最新部署版本
        if os.path.exists(settings.deployment_dir):
            versions = [d for d in os.listdir(settings.deployment_dir)
                       if d.startswith("v") and os.path.isdir(os.path.join(settings.deployment_dir, d))]
            if versions:
                versions.sort(key=lambda v: int(v[1:]))
                deployed_version = versions[-1]

        # 创建 FeatureVersion 记录（如果版本已存在则更新）
        if deployed_version:
            existing_fv = db.query(FeatureVersion).filter(
                FeatureVersion.version == deployed_version
            ).first()
            if existing_fv:
                existing_fv.task_id = task_id
                existing_fv.total_features = total
                existing_fv.passed_features = passed
            else:
                fv = FeatureVersion(
                    version=deployed_version,
                    task_id=task_id,
                    total_features=total,
                    passed_features=passed,
                )
                db.add(fv)

        # 写入所有特征的评估指标（用于ECharts可视化）
        for feat in passed_features + failed_features:
            fm = FeatureMetric(
                version=deployed_version or f"task_{task_id}",
                task_id=task_id,
                feature_name=feat.get("feature_name", ""),
                iv=feat.get("iv", 0),
                psi=feat.get("psi", 0),
                coverage=feat.get("coverage", 0),
                is_passed=1 if feat.get("status") == "passed" else 0,
            )
            db.add(fm)

    # 更新任务记录
    update_task_status(
        db, task_id,
        status="completed",
        progress=100.0,
        total_features=total,
        passed_features=passed,
        deployed_version=deployed_version,
        completed_at=datetime.utcnow(),
    )

    db.commit()


def clear_all_tasks(db: Session) -> int:
    """清空所有任务记录（含日志）。
    如果存在 running/pending 状态的任务则抛出异常。"""
    running = db.query(Task).filter(Task.status.in_(["running", "pending"])).count()
    if running > 0:
        raise RuntimeError(f"有 {running} 个任务正在执行中，请等待完成后重试")

    # 先清除 linked_task_id 自引用外键
    db.query(Task).update({"linked_task_id": None})
    db.commit()

    count = db.query(Task).count()
    db.query(Task).delete()
    db.commit()
    return count


def _trigger_template_task(db: Session, normal_task_id: int):
    """普通任务完成后，查找关联的 template_task 并触发执行"""
    tmpl = db.query(Task).filter(
        Task.mode == "template_task",
        Task.linked_task_id == normal_task_id,
    ).first()
    if not tmpl:
        return

    # 标记模板任务为进行中
    add_task_log(db, tmpl.id, "info", "普通任务已完成，开始模板评估...")
    update_task_status(db, tmpl.id, status="running", progress=10.0,
                       started_at=datetime.utcnow())

    # 这里植入模板任务的执行逻辑（通道2模板评估 + IV/PSI 验证）
    try:
        _run_template_evaluation(db, tmpl.id)
        add_task_log(db, tmpl.id, "info", "模板评估完成")
        update_task_status(db, tmpl.id, status="completed", progress=100.0,
                           completed_at=datetime.utcnow())
    except Exception as e:
        import traceback
        traceback.print_exc()
        add_task_log(db, tmpl.id, "error", f"模板评估失败: {e}")
        update_task_status(db, tmpl.id, status="failed", progress=0.0,
                           error_message=str(e), completed_at=datetime.utcnow())


def _run_template_evaluation(db: Session, tmpl_task_id: int):
    """模板任务的实际执行逻辑 — 通道2模板评估"""
    add_task_log(db, tmpl_task_id, "info", "检查通道2待审批模板...")
    pending = list_templates(db, status=PENDING_STATUS)

    if not pending:
        add_task_log(db, tmpl_task_id, "info", "暂无待审批通道2模板，跳过")
        return

    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    from agents.feature_evaluation_agent import FeatureEvaluationAgent

    evaluator = FeatureEvaluationAgent()
    total = len(pending)
    passed = 0

    for idx, tmpl in enumerate(pending):
        name = tmpl.template_name_cn or tmpl.template_name or f"模板{idx}"
        add_task_log(db, tmpl_task_id, "info",
                     f"评估模板 [{idx+1}/{total}]: {name}")
        try:
            # 提取模板中的特征代码进行 IV/PSI 评估
            python_code = tmpl.python_code or tmpl.python_function
            if not python_code:
                add_task_log(db, tmpl_task_id, "warning", f"{name}: 无Python代码，跳过")
                continue

            result = evaluator.evaluate_single_feature(python_code)
            tmpl.quality_checks = {
                **(tmpl.quality_checks or {}),
                "iv": result.get("iv", 0),
                "psi": result.get("psi", 0),
                "coverage": result.get("coverage", 0),
                "evaluated": True,
                "evaluated_at": datetime.utcnow().isoformat(),
                "template_task_id": tmpl_task_id,
            }

            passed += 1
            add_task_log(db, tmpl_task_id, "info",
                         f"{name}: IV={result.get('iv', 0):.4f}, "
                         f"PSI={result.get('psi', 0):.4f}, "
                         f"覆盖率={result.get('coverage', 0):.2%}")
        except Exception as e:
            add_task_log(db, tmpl_task_id, "error", f"{name}: 评估失败 — {e}")

    db.commit()

    add_task_log(db, tmpl_task_id, "info",
                 f"模板评估完成: {passed}/{total} 个已评估")
