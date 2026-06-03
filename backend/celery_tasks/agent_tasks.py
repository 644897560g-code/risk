"""Celery agent tasks — wraps existing agent code without modification

Each task:
1. Calls the corresponding agent code
2. Captures output and writes logs to database
3. Updates task progress/status
4. Saves results to database on completion
"""
import json
import os
import sys
import traceback
from datetime import datetime

# Ensure project root is importable
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from celery import current_task
from sqlalchemy.orm import Session

from backend.celery_tasks.celery_app import celery_app
from backend.app.database import SessionLocal
from backend.services.task_service import (
    update_task_status, add_task_log, save_task_result
)


def _get_db() -> Session:
    """Create a new DB session for the worker (each task gets its own)"""
    return SessionLocal()


def _update_progress(task_id: int, progress: float, message: str = None):
    """Update task progress and optionally add a log entry"""
    db = _get_db()
    try:
        update_task_status(db, task_id, progress=progress)
        if message:
            add_task_log(db, task_id, "info", message)
    finally:
        db.close()

    # Also update Celery task state for real-time progress
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"progress": progress, "message": message or ""}
        )
    except Exception:
        pass


@celery_app.task(bind=True, name="run_mass_production")
def run_mass_production(self, task_id: int, config: dict = None):
    """封装现有 FeatureOrchestrator.run_mass_production() 为Celery任务

    1. 更新任务状态为 running
    2. 调用现有 agent 代码
    3. 捕获日志输出
    4. 保存结果到数据库
    """
    db = _get_db()
    try:
        # 标记任务开始
        update_task_status(db, task_id, status="running", started_at=datetime.utcnow())
        add_task_log(db, task_id, "info", "批量特征生产任务已启动")
        db.close()

        _update_progress(task_id, 5.0, "正在加载特征生产引擎...")

        # 调用现有的 agent 代码（不做任何修改）
        from agents.feature_orchestrator import FeatureOrchestrator

        _update_progress(task_id, 10.0, "正在枚举参数组合并生成特征代码...")

        orchestrator = FeatureOrchestrator()
        orchestrator.run_mass_production()

        _update_progress(task_id, 90.0, "特征评估完成，正在保存结果...")

        # 读取结果并保存到数据库
        db2 = _get_db()
        try:
            eval_dir = 'outputs/evaluation'
            passed_path = os.path.join(eval_dir, 'passed_features.json')
            if os.path.exists(passed_path):
                with open(passed_path) as f:
                    result = json.load(f)
                save_task_result(db2, task_id, result)
        finally:
            db2.close()

        _update_progress(task_id, 100.0, "批量特征生产任务完成")

        return {"status": "completed", "task_id": task_id}

    except Exception as e:
        tb = traceback.format_exc()
        db3 = _get_db()
        try:
            update_task_status(
                db3, task_id,
                status="failed",
                error_message=f"{type(e).__name__}: {str(e)}",
                completed_at=datetime.utcnow(),
            )
            add_task_log(db3, task_id, "error", f"任务失败: {type(e).__name__}: {str(e)}")
            add_task_log(db3, task_id, "error", tb[-2000:] if len(tb) > 2000 else tb)
        finally:
            db3.close()
        raise


@celery_app.task(bind=True, name="run_feature_evaluation")
def run_feature_evaluation(self, task_id: int, config: dict = None):
    """封装现有 FeatureEvaluator 的样本加载+评估流程"""
    db = _get_db()
    try:
        update_task_status(db, task_id, status="running", started_at=datetime.utcnow())
        add_task_log(db, task_id, "info", "特征评估任务已启动")
        db.close()

        _update_progress(task_id, 10.0, "正在加载样本数据...")

        from agents.feature_evaluation_agent import FeatureEvaluator

        evaluator = FeatureEvaluator()
        n = evaluator.load_sample_data_local(
            short_url_file='0421全样本短链.txt',
            labels_excel='印尼模型分_2026_04_21_建模样本aiagent.xlsx',
            data_dir='data/all_samples'
        )

        _update_progress(task_id, 30.0, f"已加载 {n} 个样本，正在划分数据集...")

        evaluator.split_data(oot_ratio=0.2)

        _update_progress(task_id, 50.0, "正在计算特征...")

        evaluator.load_feature_calculator('outputs/feature_code/features_calculator_v2.py')
        df_train = evaluator.calculate_features_on_dataset(evaluator.train_data)
        df_oot = evaluator.calculate_features_on_dataset(evaluator.oot_data)

        _update_progress(task_id, 70.0, "正在评估IV/PSI...")

        evaluator.evaluate_features(
            df_train, df_oot,
            iv_threshold=0.02, psi_threshold=0.25, coverage_threshold=0.05
        )

        _update_progress(task_id, 90.0, "正在生成报告...")

        evaluator.generate_html_report()

        _update_progress(task_id, 100.0, "特征评估完成")

        return {"status": "completed", "task_id": task_id}

    except Exception as e:
        tb = traceback.format_exc()
        db3 = _get_db()
        try:
            update_task_status(
                db3, task_id,
                status="failed",
                error_message=f"{type(e).__name__}: {str(e)}",
                completed_at=datetime.utcnow(),
            )
            add_task_log(db3, task_id, "error", f"任务失败: {type(e).__name__}: {str(e)}")
        finally:
            db3.close()
        raise
