"""Task management API routes"""
import csv
import io
import json
import math
import os
import threading
import time
from typing import Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import get_db, SessionLocal
from backend.models.task import Task
from backend.services.task_service import (
    create_task,
    get_task,
    get_task_list,
    save_task_result,
    add_task_log,
    update_task_status,
    clear_all_tasks,
)


router = APIRouter()


def _add_step_log(db, task_id: int, step: str, status: str, message: str = ""):
    """添加步骤级日志（level='step'），供前端 Steps 组件解析"""
    msg = f"{step}:{status}"
    if message:
        msg += f" {message}"
    add_task_log(db, task_id, "step", msg)


def _run_mass_production_background(task_id: int, short_url_path: str = None, label_path: str = None):
    """在后台线程中执行批量生产，使用独立 DB session"""
    db = SessionLocal()
    try:
        # 强制新任务重跑 orchestrator：清空 state 避免幂等跳过
        state_file = 'outputs/feature_code/orchestrator_state.json'
        registry_file = 'outputs/feature_code/data_flow_registry.json'
        for f in [state_file, registry_file]:
            if os.path.exists(f):
                os.remove(f)

        add_task_log(db, task_id, "info", "开始批量特征生产...")
        update_task_status(db, task_id, status="running", progress=10.0)

        import sys
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

        # ---- 数据准备：从短链下载JSON到本地缓存 ----
        _add_step_log(db, task_id, "data_download", "started")
        if short_url_path and os.path.exists(short_url_path):
            add_task_log(db, task_id, "info", f"使用短链文件: {short_url_path}")
            with open(short_url_path, "r", encoding="utf-8") as f:
                urls = [line.strip() for line in f if line.strip()]

            cache_dir = "data/all_samples"
            os.makedirs(cache_dir, exist_ok=True)

            from concurrent.futures import ThreadPoolExecutor, as_completed
            import requests

            # 预计算需要下载的 URL 列表
            _to_download = []
            for url in urls:
                order_id = url.split("/")[-1].strip()
                local_path = os.path.join(cache_dir, f"{order_id}.json")
                if not os.path.exists(local_path):
                    _to_download.append((url, order_id, local_path))

            total_to_download = len(_to_download)
            if total_to_download == 0:
                add_task_log(db, task_id, "info", f"所有样本已缓存，无需下载")
            else:
                add_task_log(db, task_id, "info",
                             f"需下载 {total_to_download}/{len(urls)} 个样本，使用并发下载(workers=20)")

                _downloaded = 0
                _failed = 0
                _lock = threading.Lock()

                def _dl_one(item):
                    url, order_id, local_path = item
                    try:
                        resp = requests.get(url, timeout=30)
                        if resp.status_code == 200:
                            with open(local_path, "w", encoding="utf-8") as f:
                                json.dump(resp.json(), f, ensure_ascii=False)
                            return True, order_id
                        else:
                            return False, order_id
                    except Exception:
                        return False, order_id

                with ThreadPoolExecutor(max_workers=20) as pool:
                    futures = {pool.submit(_dl_one, item): item for item in _to_download}
                    done_count = 0
                    for fut in as_completed(futures):
                        ok, _ = fut.result()
                        done_count += 1
                        with _lock:
                            if ok:
                                _downloaded += 1
                            else:
                                _failed += 1
                        if done_count % 200 == 0 or done_count == total_to_download:
                            add_task_log(db, task_id, "info",
                                         f"数据下载进度: {done_count}/{total_to_download}"
                                         f" (成功:{_downloaded}, 失败:{_failed})")

                add_task_log(db, task_id, "info",
                             f"数据下载完成: 新增{_downloaded}/{total_to_download}, 失败{_failed}")

                # 如果下载失败超过一半或者成功数为0，这是严重问题，中止任务
                # 但如果有大量已缓存的样本（>100），少量URL过期不影响执行
                cached_count = len([f for f in os.listdir('data/all_samples') if f.endswith('.json')]) if os.path.exists('data/all_samples') else 0
                if _downloaded == 0 and total_to_download > 0:
                    if cached_count >= 100:
                        add_task_log(db, task_id, "warning",
                                     f"新增URL全部失效（{_failed}/{total_to_download}），但已有{cached_count}个缓存样本，继续执行")
                    else:
                        err_msg = f"数据下载全部失败 ({_failed}/{total_to_download})，请检查短链URL是否有效"
                        raise Exception(err_msg)
                if _downloaded < total_to_download * 0.5 and total_to_download > 10:
                    if cached_count >= 100:
                        add_task_log(db, task_id, "warning",
                                     f"新增URL下载失败率过高（{_failed}/{total_to_download}），但已有{cached_count}个缓存样本，继续执行")
                    else:
                        err_msg = f"数据下载失败率过高 ({_failed}/{total_to_download})，请检查网络或短链有效性"
                        raise Exception(err_msg)

            _add_step_log(db, task_id, "data_download", "completed")
        else:
            short_url_path = None
            add_task_log(db, task_id, "warning", "短链文件不存在，将使用默认短链文件")
            _add_step_log(db, task_id, "data_download", "completed", "(默认文件)")

        if label_path and os.path.exists(label_path):
            add_task_log(db, task_id, "info", f"使用标签文件: {label_path}")
        else:
            label_path = None
            add_task_log(db, task_id, "warning", "标签文件不存在，将使用默认标签文件")

        _add_step_log(db, task_id, "mass_production", "started")
        from agents.feature_orchestrator import FeatureOrchestrator
        orch = FeatureOrchestrator()

        # ---- 监控线程：orchestrator 运行时同步步骤状态到 DB ----
        _STEPS_MONITOR_MAP = {
            "mass_production": "mass_production",
            "reference_computation": "reference_computation",
            "feature_evaluation": "feature_evaluation",
            "feature_deployment": "feature_deployment",
            "feedback_aggregation": "feedback_aggregation",
        }
        # 每个步骤完成时的进度百分比
        _STEP_PROGRESS = {
            "mass_production": 30,
            "reference_computation": 45,
            "feature_evaluation": 70,
            "feature_deployment": 85,
            "feedback_aggregation": 95,
        }
        # 每个步骤开始时的中间进度（用于长时间运行步骤如 feature_evaluation）
        _STEP_START_PROGRESS = {
            "feature_evaluation": 50,
        }
        _stop_monitor = threading.Event()

        def _monitor_orchestrator_steps():
            _seen = set()
            _step_logged = set()
            _step_start_time = {}  # step_name -> timestamp
            _timeout_notified = set()  # 已通知超时的步骤，避免重复日志
            while not _stop_monitor.wait(10):
                try:
                    if os.path.exists(state_file):
                        with open(state_file) as _mf:
                            _ms = json.load(_mf)
                        now = time.time()
                        for _cs in _ms.get("completed_steps", []):
                            if _cs not in _seen:
                                _seen.add(_cs)
                                _mapped = _STEPS_MONITOR_MAP.get(_cs, _cs)
                                if _mapped not in _step_logged:
                                    _step_logged.add(_mapped)
                                    try:
                                        _mdb = SessionLocal()
                                        _add_step_log(_mdb, task_id, _mapped, "completed")
                                        _pct = _STEP_PROGRESS.get(_cs)
                                        if _pct:
                                            update_task_status(_mdb, task_id, progress=_pct)
                                        _mdb.commit()
                                        _mdb.close()
                                    except Exception:
                                        pass
                        _curr = _ms.get("current_step", "")
                        if _curr and _curr not in _step_logged and _curr not in _seen:
                            _mapped = _STEPS_MONITOR_MAP.get(_curr, _curr)
                            _step_logged.add(_mapped)
                            _step_start_time[_curr] = now
                            try:
                                _mdb = SessionLocal()
                                _add_step_log(_mdb, task_id, _mapped, "started")
                                _pct = _STEP_START_PROGRESS.get(_curr)
                                if _pct:
                                    update_task_status(_mdb, task_id, progress=_pct)
                                _mdb.commit()
                                _mdb.close()
                            except Exception:
                                pass

                        # 超时检测：步骤运行超过 15 分钟发出提醒
                        if _curr and _curr not in _timeout_notified:
                            _start_ts = _step_start_time.get(_curr)
                            if _start_ts and (now - _start_ts) > 900:  # 15 min
                                _timeout_notified.add(_curr)
                                try:
                                    _mdb = SessionLocal()
                                    add_task_log(_mdb, task_id, "info",
                                        f"⏳ {_curr} 步骤正在执行中（已运行 {int((now - _start_ts)/60)} 分钟），请耐心等待...")
                                    _mdb.commit()
                                    _mdb.close()
                                except Exception:
                                    pass
                except Exception:
                    pass

        _monitor_thread = threading.Thread(target=_monitor_orchestrator_steps, daemon=True)
        _monitor_thread.start()

        try:
            orch.run_mass_production(short_url_file=short_url_path, labels_excel=label_path)
        finally:
            _stop_monitor.set()
            _monitor_thread.join(timeout=5)

        add_task_log(db, task_id, "info", "批量生产完成")

        # 从 orchestrator_state.json 读取最终完成的步骤（监控线程可能漏掉最后一步）
        if os.path.exists(state_file):
            try:
                with open(state_file) as _sf:
                    _s = json.load(_sf)
                for _step_name in _s.get("completed_steps", []):
                    _mapped = _STEPS_MONITOR_MAP.get(_step_name, _step_name)
                    _add_step_log(db, task_id, _mapped, "completed")
            except Exception:
                pass

        # 检查任务是否已被用户手动终止
        try:
            _check = db.query(Task.status).filter(Task.id == task_id).scalar()
            if _check == "cancelled":
                add_task_log(db, task_id, "info", "任务已被用户终止，跳过结果保存")
                db.close()
                return
        except Exception:
            pass

        db.rollback()  # 清除可能的 session error 状态
        settings = get_settings()
        pf_path = os.path.join(settings.evaluation_dir, "passed_features.json")
        if os.path.exists(pf_path):
            with open(pf_path) as f:
                pf = json.load(f)
            try:
                save_task_result(db, task_id, {
                    "passed": pf.get("passed", 0),
                    "total": pf.get("total_features", 0),
                })
            except Exception as e2:
                add_task_log(db, task_id, "warning", f"保存结果时出错: {e2}，但任务已完成")
                db2 = SessionLocal()
                try:
                    update_task_status(db2, task_id, status="completed", progress=100.0)
                    db2.commit()
                finally:
                    db2.close()
        else:
            update_task_status(db, task_id, status="completed", progress=100.0)
    except Exception as e:
        import traceback
        error_msg = f"批量生产失败: {e}"
        traceback.print_exc()
        _add_step_log(db, task_id, "error", "failed", str(e)[:100])
        try:
            db.close()
        except Exception:
            pass
        try:
            db2 = SessionLocal()
            update_task_status(db2, task_id, status="failed", progress=0.0, error_message=str(e))
            db2.commit()
            db2.close()
        except Exception:
            pass
    finally:
        db.close()


def _run_template_generation_background(task_id: int, request_description: str = ""):
    """后台线程：调用模板生成Agent（LLM），生成通道2模板并写入 pending 列表"""
    db = SessionLocal()
    try:
        add_task_log(db, task_id, "info", "正在加载模板生成Agent...")
        update_task_status(db, task_id, progress=20.0)

        import sys as _sys
        _sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
        from agents.template_generation_agent import generate_templates

        add_task_log(db, task_id, "info", "开始调用LLM生成模板...")
        update_task_status(db, task_id, progress=40.0)

        result = generate_templates(request_description)

        if result.get("success"):
            templates = result.get("templates", [])
            count = result.get("count", len(templates))
            add_task_log(db, task_id, "info",
                         f"✅ 成功生成 {count} 个模板，已写入待审核列表")
            for tmpl in templates:
                name = tmpl.get("template_name", "?")
                dim = tmpl.get("dimension", "?")
                add_task_log(db, task_id, "info",
                             f"  - {tmpl.get('template_id')} [{name}] ({dim}) — {tmpl.get('description', '')[:80]}")
            update_task_status(db, task_id, status="completed", progress=100.0,
                               completed_at=datetime.utcnow())
        else:
            error = result.get("error", "未知错误")
            add_task_log(db, task_id, "error", f"❌ 模板生成失败: {error}")
            update_task_status(db, task_id, status="failed", progress=0.0,
                               error_message=error, completed_at=datetime.utcnow())
    except Exception as e:
        import traceback
        traceback.print_exc()
        add_task_log(db, task_id, "error", f"❌ 模板生成异常: {e}")
        try:
            db2 = SessionLocal()
            update_task_status(db2, task_id, status="failed", progress=0.0,
                               error_message=str(e), completed_at=datetime.utcnow())
            db2.commit()
            db2.close()
        except Exception:
            pass
    finally:
        db.close()


# ---- 后台调度线程：轮询到期 pending 任务 ----

import time as _time_module


def _scheduler_loop():
    """后台调度线程：每 30 秒检查一次是否有到期 pending 任务需要执行。"""
    import logging
    logger = logging.getLogger("scheduler")
    while True:
        try:
            db = SessionLocal()
            now = datetime.now(timezone.utc)
            pending_tasks = db.query(Task).filter(
                Task.status == "pending",
                Task.scheduled_at.isnot(None),
                Task.scheduled_at <= now,
            ).all()
            for t in pending_tasks:
                try:
                    logger.info(f"调度执行到期任务: id={t.id}, scheduled_at={t.scheduled_at}")
                    add_task_log(db, t.id, "info", "调度器触发：计划时间已到，开始执行...")
                    update_task_status(db, t.id, status="running", progress=5.0)
                    cfg = t.config or {}
                    t_ = threading.Thread(
                        target=_run_mass_production_background,
                        args=(t.id, cfg.get("url_path"), cfg.get("label_path")),
                        daemon=True,
                    )
                    t_.start()
                except Exception as e:
                    logger.error(f"调度任务 {t.id} 失败: {e}")
            db.close()
        except Exception:
            pass
        _time_module.sleep(30)


# 模块加载时启动调度线程
_scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
_scheduler_thread.start()


@router.post("")
async def api_create_task(
    name: str = Form(""),
    mode: str = Form("normal"),
    url_file: Optional[UploadFile] = File(None),
    label_file: Optional[UploadFile] = File(None),
    url_path: Optional[str] = Form(None),
    label_path: Optional[str] = Form(None),
    scheduled_at: Optional[str] = Form(None),
    recurring_cron: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """创建新任务。
    支持两种模式：
    - normal: 特征挖掘任务（需要数据文件/路径），自动创建关联的模板任务
    - template_task: 模板生成任务（不需要数据文件，由LLM生成通道2模板）
    """
    config = {}

    # 解析计划执行时间（early parse，两种模式都需要）
    parsed_scheduled_at = None
    if scheduled_at:
        try:
            parsed_scheduled_at = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        except ValueError:
            pass

    if mode == "template_task":
        # 模板生成任务：不需要数据配置
        if recurring_cron:
            config["recurring_cron"] = recurring_cron

        task = create_task(db, name, mode="template_task", config=config,
                           scheduled_at=parsed_scheduled_at)

        update_task_status(db, task.id, status="running", progress=5.0)
        add_task_log(db, task.id, "info", "模板生成任务已创建，开始LLM生成...")

        t = threading.Thread(
            target=_run_template_generation_background,
            args=(task.id, name),
            daemon=True,
        )
        t.start()
        return task.to_dict(include_logs=False)

    # 以下为 normal 模式（原逻辑）
    if url_file:
        settings = get_settings()
        task_dir = os.path.join(settings.data_dir, "task_uploads")
        os.makedirs(task_dir, exist_ok=True)

        url_content = await url_file.read()
        url_save_path = os.path.join(task_dir, url_file.filename or "shortlinks.txt")
        with open(url_save_path, "wb") as f:
            f.write(url_content)
        config["url_path"] = url_save_path

        if label_file:
            label_content = await label_file.read()
            label_save_path = os.path.join(task_dir, label_file.filename or "labels.xlsx")
            with open(label_save_path, "wb") as f:
                f.write(label_content)
            config["label_path"] = label_save_path
    else:
        config["url_path"] = url_path
        config["label_path"] = label_path

    config["data_source"] = "upload" if url_file else "local"

    # 解析计划执行时间
    parsed_scheduled_at = None
    if scheduled_at:
        try:
            parsed_scheduled_at = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        except ValueError:
            pass

    task = create_task(db, name, mode="normal", config=config, scheduled_at=parsed_scheduled_at)

    # 判断是否计划未来执行
    now = datetime.now(timezone.utc)
    is_scheduled = parsed_scheduled_at is not None and parsed_scheduled_at > now

    if is_scheduled:
        # 计划未来执行：保持 pending 状态，等待调度线程触发
        local_t = parsed_scheduled_at.astimezone(timezone(timedelta(hours=8)))
        add_task_log(db, task.id, "info",
                     f"任务已创建，计划执行时间: {local_t.strftime('%Y-%m-%d %H:%M:%S')}（北京时间），等待调度...")
        return task.to_dict(include_logs=False)

    # 立即执行
    is_testing = os.environ.get("RISK_AGENT_TESTING") == "true"
    update_task_status(db, task.id, status="running" if not is_testing else "completed", progress=5.0)
    add_task_log(db, task.id, "info", "任务已创建，后台执行中...")

    if not is_testing:
        t = threading.Thread(
            target=_run_mass_production_background,
            args=(task.id, config.get("url_path"), config.get("label_path")),
            daemon=True,
        )
        t.start()

    return task.to_dict(include_logs=False)


@router.get("")
def api_list_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    mode: str = Query(None),
    db: Session = Depends(get_db),
):
    """获取任务列表（按创建时间倒序）。可传 mode=normal 或 mode=template_task 过滤。"""
    items, total = get_task_list(db, skip=skip, limit=limit, mode=mode)
    return {"items": [t.to_dict(include_logs=False) for t in items], "total": total}


@router.delete("")
def api_clear_tasks(db: Session = Depends(get_db)):
    """清空所有任务记录。如有正在执行的任务则拒绝。"""
    try:
        deleted = clear_all_tasks(db)
        return {"status": "ok", "deleted": deleted}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/{task_id}")
def api_get_task(task_id: int, db: Session = Depends(get_db)):
    """获取任务详情（含日志）"""
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task.to_dict(include_logs=True)


@router.get("/{task_id}/result")
def api_get_task_result(task_id: int):
    """获取任务结果 — 直接返回 passed_features.json 内容"""
    import math
    settings = get_settings()
    path = os.path.join(settings.evaluation_dir, "passed_features.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="结果文件不存在")
    with open(path) as f:
        data = json.load(f)

    # 清理 JSON 无法序列化的 NaN/Infinity 值
    def _clean_nan(obj):
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return 0.0
            return obj
        if isinstance(obj, dict):
            return {k: _clean_nan(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_clean_nan(v) for v in obj]
        return obj

    return _clean_nan(data)


@router.get("/{task_id}/result/csv")
def api_get_task_result_csv(task_id: int, db: Session = Depends(get_db)):
    """获取任务特征评估 CSV 文件下载（优先从 passed_features.json，回退到 DB）"""
    import math
    settings = get_settings()

    all_features = []

    # Try reading from passed_features.json first (global evaluation)
    path = os.path.join(settings.evaluation_dir, "passed_features.json")
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        passed = data.get("passed_features", [])
        failed = data.get("failed_features", [])
        for f_item in passed:
            f_item["status_local"] = "通过"
        for f_item in failed:
            f_item["status_local"] = "未通过"
        all_features = passed + failed
    else:
        # Fallback: query DB FeatureMetric table
        from backend.models.feature import FeatureMetric
        metrics = db.query(FeatureMetric).filter(
            FeatureMetric.task_id == task_id
        ).all()
        if not metrics:
            # Last fallback: any version's metrics (for backward compat)
            latest = db.query(FeatureMetric.version).order_by(
                FeatureMetric.id.desc()
            ).first()
            if latest:
                metrics = db.query(FeatureMetric).filter(
                    FeatureMetric.version == latest[0]
                ).all()
        for m in metrics:
            all_features.append({
                "feature_name": m.feature_name,
                "iv": m.iv or 0,
                "psi": m.psi or 0,
                "coverage": m.coverage or 0,
                "status_local": "通过" if m.is_passed else "未通过",
            })

    if not all_features:
        raise HTTPException(status_code=404, detail="该任务没有特征评估数据")

    # Sort by IV descending
    all_features.sort(key=lambda x: _clean_val(x.get("iv", 0)), reverse=True)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["特征中文描述", "特征名", "IV", "PSI", "覆盖率", "排序(IV降序)", "状态"])

    for i, f in enumerate(all_features, 1):
        name = f.get("feature_name", "")
        desc = _feature_desc(name)
        writer.writerow([
            desc,
            name,
            round(_clean_val(f.get("iv", 0)), 6),
            round(_clean_val(f.get("psi", 0)), 6),
            f"{_clean_val(f.get('coverage', 0)):.2f}",
            i,
            f.get("status_local", "未知"),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={
            "Content-Disposition": f"attachment; filename=feature_evaluation_result_{task_id}.csv"
        },
    )


# ---- Feature name → Chinese description (shared by CSV and report endpoints) ----


def _feature_desc(feature_name: str) -> str:
    """Translate structured feature names into business-meaningful Chinese descriptions
    that a risk control analyst can understand at a glance.

    Feature name convention: {agg}_{domain}_{field}_{timewindow}_{params}
    """
    parts = feature_name.split("_")
    if not parts:
        return feature_name

    # === Aggregation prefix map ===
    agg_map = {
        "cnt": "数量/次数",
        "count": "数量/次数",
        "max": "最大值",
        "min": "最小值",
        "avg": "均值/平均",
        "mean": "均值/平均",
        "sum": "总和",
        "total": "总和",
        "ratio": "占比/比率",
        "rate": "占比/比率",
        "prop": "占比/比率",
        "perc": "百分比",
        "pct": "百分比",
        "std": "标准差(波动)",
        "var": "方差(波动)",
        "median": "中位数",
        "mode": "众数",
        "recent": "最近值",
        "last": "最近值",
        "spike": "突增量",
        "trend": "变化趋势",
        "decay": "衰减加权",
        "decayed": "衰减加权",
        "weighted": "加权",
        "cross": "交叉",
        "diff": "差值/变化",
        "delta": "变化量",
        "is": "是否",
        "has": "是否有",
        "num": "数量",
        "unique": "唯一数",
        "uniq": "唯一数",
        "distinct": "去重数",
        "score": "评分",
        "index": "指数",
        "level": "等级",
        "anom": "异常检测",
        "cluster": "聚类/聚合",
    }

    # === Domain/field → what the data represents ===
    domain_desc_map = {
        "fdciq": "FDC征信查询",
        "fdcpin": "FDC贷款记录",
        "app": "已安装APP",
        "applist": "已安装APP",
        "amt": "金额",
        "amount": "金额",
        "nilai_pendanaan": "融资金额",
        "late": "逾期",
        "overdue": "逾期",
        "bad": "坏账",
        "pay": "还款",
        "repay": "还款",
        "salary": "薪资收入",
        "income": "收入",
        "loan": "贷款",
        "credit": "信贷",
        "phone": "手机号",
        "contact": "通讯录",
        "gps": "GPS定位",
        "location": "位置",
        "aktif": "活跃平台数",
        "pltnf": "平台",
        "platform": "平台",
        "lender": "借贷机构",
        "penyelenggara": "放贷机构",
        "pinjaman": "贷款记录",
        "inquiry": "征信查询",
        "gambling": "赌博类APP",
        "gamble": "赌博类APP",
        "cash_loan": "现金贷类APP",
        "fintech_lending": "金融借贷类APP",
        "shopping": "购物类APP",
        "food_delivery": "外卖类APP",
        "status_pinjaman": "贷款状态",
        "kualitas_pinjaman": "贷款质量",
        "tipe_pinjaman": "贷款类型",
        "pendanaan_syariah": "伊斯兰融资",
        "multiguna": "多用途贷款",
        "produktif": "生产经营贷款",
        "device": "设备",
        "hitby": "被查询机构数",
        "risk": "风险",
        "fraud": "欺诈",
        "tenor": "贷款期限",
        "duration": "期限",
        "age": "客户年龄/账龄",
    }

    # === Time window descriptions ===
    time_desc_map = {
        "1d": "近1天", "3d": "近3天", "7d": "近7天", "15d": "近15天",
        "30d": "近30天", "60d": "近60天", "90d": "近90天", "180d": "近180天",
        "3m": "近3月", "6m": "近6月", "12m": "近12月",
    }

    # === Loan quality mapping ===
    kualitas_map = {
        "1": "Kualitas 1(正常)", "2": "Kualitas 2(关注)",
        "3": "Kualitas 3(次级)", "4": "Kualitas 4(可疑)",
        "5": "Kualitas 5(损失)",
    }

    # === Loan status mapping ===
    status_pinjaman_map = {
        "f": "已结清", "l": "已结清",
        "o": "正常还款中", "w": "核销/坏账",
    }

    # === Strategy: build the description from the feature name structure ===
    name = feature_name

    # Handle anom_* features
    if name.startswith("anom_"):
        target = name.replace("anom_", "")
        if target == "app":
            return "异常APP安装行为检测（高频安装/卸载等）"
        elif target == "loan":
            return "异常贷款行为检测（短时间内多平台借贷等）"
        return f"异常检测-{target}"

    # Handle cluster_* features
    if name.startswith("cluster_"):
        rest = name.replace("cluster_", "")
        if "device" in rest and "penyelenggara" in rest:
            return "同一设备关联的放贷机构聚类数"
        if "device" in rest and "pkg" in rest:
            return "同一设备关联的APP包名聚类数"
        return f"聚类特征-{rest}"

    # Handle spike_* features
    if name.startswith("spike_"):
        rest = name.replace("spike_", "")
        spike_parts = rest.split("_")
        domain_desc = ""
        time_desc = ""
        mult = ""
        for p in spike_parts:
            if p in time_desc_map:
                time_desc = time_desc_map[p]
            elif p in domain_desc_map:
                domain_desc = domain_desc_map[p]
            elif p.endswith("x0") or p.endswith("x1"):
                mult = p.replace("x0", "").replace("x1", "")
        base = f"{domain_desc} {time_desc}" if domain_desc and time_desc else rest
        if mult:
            return f"{base} 突增{mult}倍以上"
        return f"{base} 突增异常"

    # Handle trend_* features
    if name.startswith("trend_"):
        rest = name.replace("trend_", "")
        trend_parts = rest.split("_")
        domain_desc = ""
        time_ranges = []
        for p in trend_parts:
            if p in time_desc_map:
                time_ranges.append(time_desc_map[p])
            elif p in domain_desc_map:
                domain_desc = domain_desc_map[p]
        if domain_desc and time_ranges:
            return f"{domain_desc} 在{''.join(time_ranges)}间的变化趋势"
        return f"{rest} 变化趋势"

    # Handle decay_* features
    if name.startswith("decay_"):
        rest = name.replace("decay_", "")
        decay_parts = rest.split("_")
        domain_desc = ""
        time_desc = ""
        field_desc = ""
        param = ""
        for p in decay_parts:
            if p in time_desc_map:
                time_desc = time_desc_map[p]
            elif p in ("fdc", "fdcpin", "fdciq", "app", "aktif"):
                domain_desc = domain_desc_map.get(p, p)
            elif p in ("amt", "amount", "nilai_pendanaan"):
                field_desc = "金额"
            elif p in ("cnt", "count", "num"):
                field_desc = "笔数"
            elif p.startswith("r") and len(p) <= 4:
                param = f"(衰减系数{p})"
            elif p in agg_map:
                field_desc = agg_map[p]
            elif p in domain_desc_map:
                if not domain_desc:
                    domain_desc = domain_desc_map[p]
        parts_list = [x for x in [domain_desc, field_desc, time_desc, param] if x]
        if parts_list:
            return "".join(parts_list)
        return f"衰减加权-{rest}"

    # Handle uniq_* features
    if name.startswith("uniq_"):
        rest = name.replace("uniq_", "")
        uniq_parts = rest.split("_")
        target_desc = ""
        time_desc = ""
        for p in uniq_parts:
            if p in time_desc_map:
                time_desc = time_desc_map[p]
            elif p == "fdciq":
                time_desc = "近3天"
            elif p in domain_desc_map:
                target_desc = domain_desc_map[p]
        if "hitby" in uniq_parts:
            return f"{time_desc} 查询过该用户的征信机构数" if time_desc else "查询过该用户的征信机构数"
        if "lender" in uniq_parts:
            return f"{time_desc} 该用户有借贷记录的机构数" if time_desc else "该用户有借贷记录的机构数"
        if "loan_status" in uniq_parts:
            return f"{time_desc} 贷款状态种类数" if time_desc else "贷款状态种类数"
        if "loan_type" in uniq_parts:
            return f"{time_desc} 贷款类型种类数" if time_desc else "贷款类型种类数"
        return f"{time_desc} 唯一{target_desc}数" if time_desc and target_desc else rest

    # Helper to build readable descriptions for compound ref names
    def _build_readable_ref(ref_name: str) -> str:
        """Build readable Chinese description for a compound ref name."""
        compound_map = {
            "highrisk_loan": "高风险借贷",
            "highrisk": "高风险",
            "loan": "借贷",
            "banking": "银行",
            "ewallet": "电子钱包",
            "gambling": "赌博",
            "shopping": "购物",
            "consume": "消费",
            "amt": "金额",
            "bal": "在贷余额",
            "inc": "收入",
            "dpd30": "DPD30逾期",
            "aktif": "活跃平台",
            "cnt_a": "特征A数量",
            "cnt_b": "特征B数量",
        }
        for p in ref_name.split("_"):
            if p in domain_desc_map:
                return domain_desc_map[p]
        for key, val in compound_map.items():
            if key in ref_name:
                return val
        return ref_name

    # Handle d_* derived features (T016)
    if name.startswith("d_"):
        body = name[2:]
        d_und = body.find("_")
        if d_und == -1:
            return name
        d_type = body[:d_und]
        d_rest = body[d_und + 1:]

        # d_dens_{ref}_{window}
        if d_type == "dens":
            parts = d_rest.rsplit("_", 1)
            if len(parts) == 2:
                ref, win = parts
                win_desc = time_desc_map.get(win, win)
                ref_desc = _feature_desc(ref)
                return f"{ref_desc} 相对于{win_desc}的密度比"
            return _feature_desc(d_rest) + " 密度比"

        # d_ratio_{a}_vs_{b}_{window} or d_ratio_{ref}_{window}
        if d_type == "ratio":
            vs_idx = d_rest.find("_vs_")
            if vs_idx != -1:
                ref_a = d_rest[:vs_idx]
                right = d_rest[vs_idx + 4:]
                r_parts = right.rsplit("_", 1)
                if len(r_parts) == 2:
                    ref_b, win = r_parts
                    win_desc = time_desc_map.get(win, win)
                    desc_a = _feature_desc(ref_a)
                    desc_b = _feature_desc(ref_b)
                    if len(desc_a.split()) <= 1 or len(desc_b.split()) <= 1:
                        desc_a = _build_readable_ref(ref_a)
                        desc_b = _build_readable_ref(ref_b)
                    return f"{desc_a} 与 {desc_b} 的交叉比率({win_desc})"
                desc_a = _feature_desc(ref_a)
                desc_b = _feature_desc(right)
                return f"{desc_a} 与 {desc_b} 的交叉比率"
            parts = d_rest.rsplit("_", 1)
            if len(parts) == 2:
                ref, win = parts
                if win in time_desc_map:
                    win_desc = time_desc_map[win]
                    readable = _build_readable_ref(ref)
                    return f"{readable} 的比率({win_desc})"
            return _build_readable_ref(d_rest) + " 比率"

        # d_wcomb_{a}_{b}_{window}
        if d_type == "wcomb":
            vs_idx = d_rest.find("_vs_")
            if vs_idx != -1:
                left = d_rest[:vs_idx]
                right = d_rest[vs_idx + 4:]
                r_parts = right.rsplit("_", 1)
                if len(r_parts) == 2:
                    ref_b, win = r_parts
                    win_desc = time_desc_map.get(win, win)
                    a_readable = _build_readable_ref(left)
                    b_readable = _build_readable_ref(ref_b)
                    return f"{a_readable} 与 {b_readable} 的加权组合({win_desc})"
            else:
                parts = d_rest.rsplit("_", 1)
                if len(parts) == 2:
                    inner, win = parts
                    if win in time_desc_map:
                        win_desc = time_desc_map[win]
                        readable = _build_readable_ref(inner)
                        return f"{readable} 的加权组合({win_desc})"
            return d_rest + " 加权组合"

        # d_vel_{ref}_{short}v{long}d
        if d_type in ("vel", "velocity"):
            parts = d_rest.rsplit("_", 1)
            if len(parts) == 2:
                ref = parts[0]
                vel_spec = parts[1]
                v_idx = vel_spec.find("v")
                if v_idx != -1:
                    short = vel_spec[:v_idx]
                    long_rest = vel_spec[v_idx + 1:]
                    if long_rest.endswith("d"):
                        long_ = long_rest[:-1]
                    else:
                        long_ = long_rest
                    ref_desc = _feature_desc(ref)
                    if len(ref_desc.split()) <= 1:
                        ref_desc = _build_readable_ref(ref)
                    return f"{ref_desc} 的{short}→{long_}天速度变化"
                return _build_readable_ref(ref) + f" 速度变化({vel_spec})"
            return _feature_desc(d_rest) + " 速度变化"

        # d_sq_{ref}_{window}
        if d_type == "sq":
            parts = d_rest.rsplit("_", 1)
            if len(parts) == 2:
                ref, win = parts
                win_desc = time_desc_map.get(win, win)
                ref_desc = _feature_desc(ref)
                return f"{ref_desc} 的平方值({win_desc})"
            return _feature_desc(d_rest) + " 平方值"

        # d_log_{ref}_{window}
        if d_type == "log":
            parts = d_rest.rsplit("_", 1)
            if len(parts) == 2:
                ref, win = parts
                win_desc = time_desc_map.get(win, win)
                ref_desc = _feature_desc(ref)
                return f"{ref_desc} 的对数值({win_desc})"
            return _feature_desc(d_rest) + " 对数值"

        # d_diff_{a}_vs_{b}_{window}
        if d_type == "diff":
            vs_idx = d_rest.find("_vs_")
            if vs_idx != -1:
                ref_a = d_rest[:vs_idx]
                right = d_rest[vs_idx + 4:]
                r_parts = right.rsplit("_", 1)
                if len(r_parts) == 2:
                    ref_b, win = r_parts
                    win_desc = time_desc_map.get(win, win)
                    desc_a = _feature_desc(ref_a)
                    desc_b = _feature_desc(ref_b)
                    if len(desc_a.split()) <= 1 or len(desc_b.split()) <= 1:
                        desc_a = _build_readable_ref(ref_a)
                        desc_b = _build_readable_ref(ref_b)
                    return f"{desc_a} 与 {desc_b} 的差值({win_desc})"
                desc_a = _feature_desc(ref_a)
                desc_b = _feature_desc(right)
                return f"{desc_a} 与 {desc_b} 的差值"
            return body

        # d_high_{ref}_{window}
        if d_type == "high":
            parts = d_rest.rsplit("_", 1)
            if len(parts) == 2:
                ref, win = parts
                win_desc = time_desc_map.get(win, win)
                ref_desc = _feature_desc(ref)
                return f"{ref_desc} 是否为高值({win_desc})"
            return _feature_desc(d_rest) + " 高值标志"

        return _feature_desc(d_rest) if d_rest else name

    # Handle cnt_*, max_*, avg_*, prop_* features (the majority)
    parts = name.split("_")
    agg = parts[0]
    agg_desc = agg_map.get(agg, agg)
    rest_parts = parts[1:]

    # Find time window at the end
    time_desc = ""
    if rest_parts and rest_parts[-1] in time_desc_map:
        time_desc = time_desc_map[rest_parts[-1]]
        rest_parts = rest_parts[:-1]

    # Pattern: cnt/avg/max_fdcpin_status_pinjaman_{status}_{time}
    if len(rest_parts) >= 3 and rest_parts[0] == "fdcpin" and rest_parts[1] == "status" and rest_parts[2] == "pinjaman":
        status = rest_parts[3] if len(rest_parts) > 3 else ""
        status_desc = status_pinjaman_map.get(status, status)
        return f"{time_desc} FDC贷款状态为{status_desc}的贷款{'次数' if agg == 'cnt' else '金额' if agg in ('max','avg','sum') else '指标'}"

    # Pattern: cnt_fdcpin_kualitas_pinjaman_{kualitas}_{time}
    if len(rest_parts) >= 3 and rest_parts[0] == "fdcpin" and rest_parts[1] == "kualitas" and rest_parts[2] == "pinjaman":
        kval = rest_parts[3] if len(rest_parts) > 3 else ""
        kval_desc = kualitas_map.get(kval, f"质量等级{kval}")
        return f"{time_desc} FDC贷款质量{kval_desc}的贷款笔数"

    # Pattern: cnt_fdcpin_pendanaan_syariah_{bool}_{time}
    if len(rest_parts) >= 3 and rest_parts[0] == "fdcpin" and "syariah" in rest_parts:
        is_true = "true" in rest_parts
        return f"{time_desc} {'伊斯兰融资' if is_true else '非伊斯兰融资'}的贷款笔数"

    # Pattern: cnt_fdcpin_tipe_pinjaman_{type}_{time}
    if len(rest_parts) >= 3 and rest_parts[0] == "fdcpin" and rest_parts[1] == "tipe" and rest_parts[2] == "pinjaman":
        loan_type = rest_parts[3] if len(rest_parts) > 3 else ""
        type_desc = domain_desc_map.get(loan_type, loan_type)
        return f"{time_desc} FDC{type_desc}笔数"

    # Pattern: prop_app_{category}_{time}
    if agg == "prop" and len(rest_parts) >= 2 and rest_parts[0] == "app":
        cat_str_raw = "_".join(rest_parts[1:])
        for raw, readable in [
            ("cash_loan", "现金贷"), ("fintech_lending", "金融借贷"),
            ("food_delivery", "外卖"), ("gambling", "赌博"),
            ("shopping", "购物"), ("clone_app", "应用克隆"),
            ("fake_gps", "虚拟定位"), ("app_store", "第三方应用商店"),
            ("ewallet", "电子钱包"), ("banking", "银行"),
            ("transportation", "出行"), ("productivity", "效率工具"),
            ("utility", "实用工具"), ("religious", "宗教"),
            ("social_entertainment", "社交娱乐"), ("installment", "分期"),
        ]:
            cat_str_raw = cat_str_raw.replace(raw, readable)
        for t_key in sorted(time_desc_map.keys(), key=len, reverse=True):
            if cat_str_raw.endswith("_" + t_key):
                cat_str_raw = cat_str_raw[:-(len(t_key)+1)]
                break
        cat_str_display = cat_str_raw.replace("_", " + ")
        if cat_str_display:
            return f"{time_desc} {cat_str_display}类APP安装比例"
        return f"{time_desc} 应用类别安装比例"

    # Pattern: prop_fdcpin_*
    if agg == "prop" and len(rest_parts) >= 1 and rest_parts[0] == "fdcpin":
        remaining_rest = "_".join(rest_parts[1:])
        if "kualitas_pinjaman" in remaining_rest:
            kval = remaining_rest.split("_")[-1] if remaining_rest.split("_")[-1].isdigit() else ""
            kval_desc = kualitas_map.get(kval, kval)
            return f"{time_desc} FDC贷款质量{kval_desc}的贷款占比"
        if "status_pinjaman" in remaining_rest:
            for k, v in status_pinjaman_map.items():
                if k in remaining_rest:
                    return f"{time_desc} FDC贷款状态为{v}的贷款占比"
        if "pendanaan_syariah" in remaining_rest:
            is_true = "true" in remaining_rest
            return f"{time_desc} {'伊斯兰融资' if is_true else '非伊斯兰融资'}贷款占比"
        if "tipe_pinjaman" in remaining_rest:
            loan_type = remaining_rest.split("_")[-1]
            type_desc = domain_desc_map.get(loan_type, loan_type)
            return f"{time_desc} FDC{type_desc}占比"

    # Pattern: cnt_fdciq_{time}
    if agg in ("cnt", "count") and len(rest_parts) >= 1 and rest_parts[0] == "fdciq":
        return f"{time_desc} FDC征信被查询次数"

    # Pattern: cnt_fdcpin_{time}
    if agg in ("cnt", "count") and len(rest_parts) >= 1 and rest_parts[0] == "fdcpin":
        if len(rest_parts) == 1:
            return f"{time_desc} FDC贷款记录笔数"

    # Pattern: cnt_app_{time}
    if agg in ("cnt", "count") and len(rest_parts) >= 1 and rest_parts[0] == "app":
        return f"{time_desc} 已安装APP数量"

    # Handle conc_* features (concentration metrics)
    if name.startswith("conc_"):
        rest = name.replace("conc_", "")
        conc_parts = rest.split("_")
        time_desc = ""
        domain_desc = ""
        metric = ""
        for p in conc_parts:
            if p in time_desc_map:
                time_desc = time_desc_map[p]
            elif p in domain_desc_map:
                domain_desc = domain_desc_map[p]
            else:
                metric = p
        metric_desc = {
            "entropy": "集中度(熵)",
            "gini": "集中度(基尼系数)",
            "cv": "集中度(变异系数)",
            "hhi": "集中度(HHI指数)",
        }.get(metric, f"集中度({metric})")
        parts = [x for x in [time_desc, domain_desc, metric_desc] if x]
        return " ".join(parts)

    # Handle perc_* features (percentage features)
    if name.startswith("perc_"):
        rest = name.replace("perc_", "")
        perc_parts = rest.split("_")
        domain_desc = ""
        time_desc1 = ""
        time_desc2 = ""
        for p in perc_parts:
            if p in time_desc_map:
                if not time_desc1:
                    time_desc1 = time_desc_map[p]
                else:
                    time_desc2 = time_desc_map[p]
            elif p in domain_desc_map:
                domain_desc = domain_desc_map[p]
        if not time_desc1 and not time_desc2:
            for p in perc_parts:
                if "v" in p and any(d in p for d in ["3d","7d","15d","30d","60d","90d","180d"]):
                    times = p.split("v")
                    t1 = time_desc_map.get(times[0], times[0])
                    t2 = time_desc_map.get(times[1], times[1])
                    time_desc1 = t1
                    time_desc2 = t2
                    break
        if time_desc1 and time_desc2 and domain_desc:
            if not time_desc1.startswith("近"):
                time_desc1 = "近" + time_desc1
            if not time_desc2.startswith("近"):
                time_desc2 = "近" + time_desc2
            return f"{domain_desc} {time_desc1}占{time_desc2}的比例"
        if time_desc1 and domain_desc:
            return f"{domain_desc} {time_desc1}占比"
        if time_desc1 and time_desc2:
            if not time_desc1.startswith("近"):
                time_desc1 = "近" + time_desc1
            if not time_desc2.startswith("近"):
                time_desc2 = "近" + time_desc2
            domain_str = " ".join(p for p in perc_parts if p not in ("perc",))
            return f"{domain_desc} {time_desc1}占{time_desc2}的比例" if domain_desc else f" {time_desc1}占{time_desc2}的比例"
        return f"{rest} 百分比"

    # Handle ovlap_* features (overlap between domains)
    if name.startswith("ovlap_"):
        rest = name.replace("ovlap_", "")
        ovlap_parts = rest.split("_")
        time_desc = ""
        parts = []
        for p in ovlap_parts:
            if p in time_desc_map:
                time_desc = time_desc_map[p]
            elif p == "fdc":
                parts.append("FDC机构")
            elif p in domain_desc_map:
                parts.append(domain_desc_map[p])
            else:
                parts.append(p)
        domain_str = "与".join(parts) if parts else rest
        if time_desc:
            return f"{time_desc} {domain_str}重叠度"
        return f"{domain_str}重叠度"

    # Handle da_* features (data analysis features)
    if name.startswith("da_"):
        rest = name.replace("da_", "")
        if "salary" in rest and "loan" in rest:
            if "abs_diff" in rest:
                return "薪资与贷款金额的绝对差值"
            if "gap" in rest or "diff" in rest:
                return "薪资与贷款金额的差距"
            if "ratio" in rest:
                return "薪资与贷款金额的比率"
        return f"数据分析-{rest}"

    # Generic fallback for cnt/max/avg/sum/prop
    if agg in agg_map:
        domain_str = ""
        field_str = ""
        for p in rest_parts:
            if p in domain_desc_map:
                domain_str = domain_desc_map[p]
            elif p in time_desc_map:
                break
            else:
                if not field_str:
                    field_str = p

        if domain_str and field_str:
            return f"{time_desc} {domain_str}的{field_str}的{agg_desc}"
        if domain_str:
            return f"{time_desc} {domain_str}的{agg_desc}"
        if field_str:
            return f"{time_desc} {field_str}的{agg_desc}"

    return " ".join([x for x in [time_desc, agg_desc, "_".join(rest_parts)] if x]) or feature_name


def _clean_val(v):
    """Clean NaN/Inf float values for CSV/JSON serialization."""
    import math
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return 0.0
        return v
    return v or 0


@router.get("/{task_id}/result/report")
def api_get_task_result_report(task_id: int, db: Session = Depends(get_db)):
    """获取任务特征评估 HTML 报告下载

    动态注入特征中文描述列，即使缓存报告是旧版本也包含描述。
    """
    import re as _re

    settings = get_settings()
    report_path = os.path.join(settings.evaluation_dir, "feature_evaluation_report.html")
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="评估报告文件不存在")

    with open(report_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # ---- Inject "特征描述" column if not already present ----
    if '特征描述' not in html:
        # 1. Add desc-cell CSS
        css_insert = '.desc-cell { color: #555; font-size: 0.9em; max-width: 250px; }'
        if css_insert not in html:
            html = html.replace(
                'th { background: #4CAF50;',
                'th { background: #4CAF50; white-space: nowrap; }\n        ' + css_insert
            )

        # 2. Add header column
        html = html.replace(
            '<th>特征名称</th>',
            '<th>特征名称</th>\n                    <th>特征描述</th>'
        )

        # 3. Read passed_features.json for descriptions, or fallback to _simple_desc logic
        pf_path = os.path.join(settings.evaluation_dir, "passed_features.json")
        desc_map = {}
        if os.path.exists(pf_path):
            with open(pf_path) as f:
                pf_data = json.load(f)
            for feat in pf_data.get("passed_features", []) + pf_data.get("failed_features", []):
                desc_map[feat.get("feature_name", "")] = _feature_desc(feat.get("feature_name", ""))
        else:
            # No data file — extract feature names from HTML and use inline logic
            names = _re.findall(r'<code>([^<]+)</code>', html)
            for n in names:
                desc_map[n] = _feature_desc(n)

        # 4. Inject description cell into each row
        def _inject_desc(m):
            row_html = m.group(0)
            name_match = _re.search(r'<code>([^<]+)</code>', row_html)
            if name_match and '<td class="desc-cell">' not in row_html:
                fname = name_match.group(1)
                desc = desc_map.get(fname, fname)
                # Insert after the name cell </td>
                row_html = row_html.replace(
                    '</td>',
                    '</td>\n                    <td class="desc-cell">' + desc + '</td>',
                    1  # only first occurrence (the name cell)
                )
            return row_html

        html = _re.sub(r'<tr>\s*<td>\d+</td>.*?</tr>', _inject_desc, html, flags=_re.DOTALL)

    return StreamingResponse(
        iter([html.encode('utf-8')]),
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=feature_evaluation_report_{task_id}.html"
        },
    )



@router.get("/{task_id}/steps")
def api_get_task_steps(task_id: int, db: Session = Depends(get_db)):
    """获取任务步骤状态，供前端 Steps 组件渲染。

    从任务日志中解析 level='step' 的条目，返回结构化步骤列表：
    [{name, label, status, message}, ...]
    """
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 步骤定义（按执行顺序）
    STEP_DEFS = [
        {"name": "data_download", "label": "数据下载"},
        {"name": "mass_production", "label": "特征生产"},
        {"name": "reference_computation", "label": "参考分布"},
        {"name": "feature_evaluation", "label": "特征评估"},
        {"name": "feature_deployment", "label": "部署打包"},
        {"name": "feedback_aggregation", "label": "通道2审核"},
    ]

    # 从日志解析步骤状态
    step_status = {}  # name -> latest status (started/completed/failed)
    step_messages = {}
    if task.logs:
        for log in task.logs:
            if log.level == "step":
                msg = log.message
                if ":" in msg:
                    parts = msg.split(":", 1)
                    step_name = parts[0].strip()
                    rest = parts[1].strip()
                    if " " in rest:
                        st, extra = rest.split(" ", 1)
                        step_status[step_name] = st
                        step_messages[step_name] = extra.strip()
                    else:
                        step_status[step_name] = rest

    result = []
    for sd in STEP_DEFS:
        name = sd["name"]
        st = step_status.get(name, "pending")
        if st == "completed":
            status = "finish"
        elif st == "started":
            status = "process"
        elif st == "failed":
            status = "error"
        else:
            status = "wait"
        result.append({
            "name": name,
            "label": sd["label"],
            "status": status,
            "message": step_messages.get(name, ""),
        })

    # 如果任务整体失败但没有步骤标记为 failed，把当前步骤标为 error
    if task.status == "failed":
        has_error = any(r["status"] == "error" for r in result)
        has_process = any(r["status"] == "process" for r in result)
        if not has_error:
            for r in reversed(result):
                if r["status"] == "process" or r["status"] == "wait":
                    r["status"] = "error"
                    break

    return {"steps": result, "task_status": task.status}


@router.post("/{task_id}/cancel")
def api_cancel_task(task_id: int, db: Session = Depends(get_db)):
    """终止一个运行中的任务"""
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status not in ("running", "pending"):
        raise HTTPException(status_code=400, detail=f"只有运行中或等待中的任务可以终止，当前状态: {task.status}")

    update_task_status(db, task_id, status="cancelled", progress=0.0,
                       error_message="用户手动终止", completed_at=datetime.utcnow())
    add_task_log(db, task_id, "warning", "用户手动终止了该任务")

    return {"status": "cancelled", "task_id": task_id}


@router.post("/{task_id}/resume")
def api_resume_task(task_id: int, db: Session = Depends(get_db)):
    """从失败状态继续执行任务 — 复用已下载的缓存数据"""
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != "failed":
        raise HTTPException(status_code=400, detail="只有失败状态的任务可以继续执行")

    # 从 task config 恢复数据路径
    config = task.config or {}
    short_url_path = config.get("url_path")
    label_path = config.get("label_path")

    # 重置状态为 running
    update_task_status(db, task_id, status="running", progress=10.0, error_message=None)
    add_task_log(db, task_id, "info", "用户点击继续执行，正在恢复...")
    add_task_log(db, task_id, "info", f"使用缓存数据目录: data/all_samples/")

    is_testing = os.environ.get("RISK_AGENT_TESTING") == "true"
    if not is_testing:
        t = threading.Thread(
            target=_run_orchestrator_only_background,
            args=(task_id, short_url_path, label_path),
            daemon=True,
        )
        t.start()
        add_task_log(db, task_id, "info", "已跳过下载阶段，直接从特征生产开始")
    else:
        add_task_log(db, task_id, "info", "测试环境跳过后台执行")

    return {"status": "resumed", "task_id": task_id}


@router.post("/{task_id}/rerun")
def api_rerun_task(task_id: int, db: Session = Depends(get_db)):
    """重新执行已完成/已终止/失败的任务。复用原任务配置，从头开始执行完整流程。"""
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 模板任务重跑：调用 _run_template_generation_background
    if task.mode == "template_task":
        name = task.name
        update_task_status(db, task_id, status="running", progress=5.0,
                           error_message=None, completed_at=None)
        add_task_log(db, task_id, "info", "用户触发模板任务重新执行...")
        t = threading.Thread(
            target=_run_template_generation_background,
            args=(task_id, name),
            daemon=True,
        )
        t.start()
        return {"status": "rerunning", "task_id": task_id}

    config = task.config or {}
    data_source = config.get("data_source", "local")
    short_url_path = config.get("url_path")
    label_path = config.get("label_path")

    if not short_url_path:
        raise HTTPException(status_code=400, detail="该任务没有数据路径配置，无法重新执行")

    # 重置任务状态（复用相同 task_id，保留名称和历史日志）
    update_task_status(db, task_id, status="running", progress=5.0,
                       error_message=None, completed_at=None)
    add_task_log(db, task_id, "info", "用户触发重新执行任务...")
    if data_source == "local":
        add_task_log(db, task_id, "info", f"本地路径模式，将重新下载/加载: {short_url_path}")

    # 清除本地数据缓存，确保重新下载所有样本
    cache_dir = "data/all_samples"
    if os.path.exists(cache_dir):
        import shutil
        shutil.rmtree(cache_dir)
        add_task_log(db, task_id, "info", f"已清除数据缓存目录: {cache_dir}")

    is_testing = os.environ.get("RISK_AGENT_TESTING") == "true"
    if not is_testing:
        t = threading.Thread(
            target=_run_mass_production_background,
            args=(task_id, short_url_path, label_path),
            daemon=True,
        )
        t.start()
        add_task_log(db, task_id, "info", "正在从头开始执行完整流程...")
    else:
        add_task_log(db, task_id, "info", "测试环境跳过后台执行")

    return {"status": "rerunning", "task_id": task_id}


@router.get("/{task_id}/deployment")
def api_get_task_deployment(task_id: int, db: Session = Depends(get_db)):
    """获取任务部署包下载"""
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.deployed_version:
        raise HTTPException(status_code=404, detail="该任务尚未部署")

    settings = get_settings()
    pkg_path = os.path.join(
        settings.deployment_dir,
        f"{task.deployed_version}.tar.gz"
    )
    if not os.path.exists(pkg_path):
        raise HTTPException(status_code=404, detail="部署包文件不存在")

    return FileResponse(
        pkg_path,
        media_type="application/gzip",
        filename=f"deployment_{task.deployed_version}.tar.gz",
    )


@router.get("/{task_id}/samples")
def api_get_task_samples(
    task_id: int,
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """获取任务样本数据（前N个），用于特征测试"""
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 从 data/all_samples 获取
    samples_dir = "data/all_samples"
    if not os.path.exists(samples_dir):
        raise HTTPException(status_code=404, detail="样本缓存目录不存在")

    files = sorted(os.listdir(samples_dir))
    result = []
    for fname in files[:limit]:
        fpath = os.path.join(samples_dir, fname)
        if not fname.endswith(".json"):
            continue
        try:
            with open(fpath) as f:
                data = json.load(f)
            # Return the full raw JSON — FeatureCalculator expects
            # data.params.base, data.params.appList, data.FDC, data.applyTime
            result.append(data)
        except Exception:
            pass

    return {"items": result, "total": len(result)}


def _run_orchestrator_only_background(task_id: int, short_url_path: str = None, label_path: str = None):
    """后台线程：跳过下载，直接执行特征生产 + 评估 + 部署"""
    db = SessionLocal()
    try:
        add_task_log(db, task_id, "info", "开始特征生产...")
        update_task_status(db, task_id, status="running", progress=20.0)

        import sys
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

        # 重置 orchestrator state，确保所有步骤重新执行
        state_file = 'outputs/feature_code/orchestrator_state.json'
        registry_file = 'outputs/feature_code/data_flow_registry.json'
        for f in [state_file, registry_file]:
            if os.path.exists(f):
                os.remove(f)
                add_task_log(db, task_id, "info", f"已清理执行状态: {f}")

        _add_step_log(db, task_id, "mass_production", "started")
        from agents.feature_orchestrator import FeatureOrchestrator
        orch = FeatureOrchestrator()

        # 监控线程：orchestrator 运行时同步步骤状态到 DB
        _stop_monitor = threading.Event()

        def _monitor_orch_steps():
            _seen = set()
            _step_logged = set()
            _map = {
                "mass_production": "mass_production",
                "reference_computation": "reference_computation",
                "feature_evaluation": "feature_evaluation",
                "feature_deployment": "feature_deployment",
                "feedback_aggregation": "feedback_aggregation",
            }
            _step_progress = {
                "mass_production": 30,
                "reference_computation": 45,
                "feature_evaluation": 70,
                "feature_deployment": 85,
                "feedback_aggregation": 95,
            }
            while not _stop_monitor.wait(10):
                try:
                    if os.path.exists(state_file):
                        with open(state_file) as _mf:
                            _ms = json.load(_mf)
                        for _cs in _ms.get("completed_steps", []):
                            if _cs not in _seen:
                                _seen.add(_cs)
                                _mapped = _map.get(_cs, _cs)
                                if _mapped not in _step_logged:
                                    _step_logged.add(_mapped)
                                    _mdb = SessionLocal()
                                    _add_step_log(_mdb, task_id, _mapped, "completed")
                                    _pct = _step_progress.get(_cs)
                                    if _pct:
                                        update_task_status(_mdb, task_id, progress=_pct)
                                    _mdb.commit()
                                    _mdb.close()
                        _curr = _ms.get("current_step", "")
                        if _curr and _curr not in _step_logged and _curr not in _seen:
                            _mapped = _map.get(_curr, _curr)
                            _step_logged.add(_mapped)
                            _mdb = SessionLocal()
                            _add_step_log(_mdb, task_id, _mapped, "started")
                            _mdb.close()
                except Exception:
                    pass

        _monitor_thread = threading.Thread(target=_monitor_orch_steps, daemon=True)
        _monitor_thread.start()

        try:
            orch.run_mass_production(short_url_file=short_url_path, labels_excel=label_path)
        finally:
            _stop_monitor.set()
            _monitor_thread.join(timeout=5)

        add_task_log(db, task_id, "info", "批量生产完成")

        # 从 orchestrator_state.json 读取最终完成的步骤（补漏）
        if os.path.exists(state_file):
            try:
                with open(state_file) as _sf:
                    _s = json.load(_sf)
                for _step_name in _s.get("completed_steps", []):
                    _add_step_log(db, task_id, _step_name, "completed")
            except Exception:
                pass

        # 手动刷新 session，清除可能的 error 状态
        db.rollback()

        settings = get_settings()
        pf_path = os.path.join(settings.evaluation_dir, "passed_features.json")
        if os.path.exists(pf_path):
            with open(pf_path) as f:
                pf = json.load(f)
            try:
                save_task_result(db, task_id, {
                    "passed": pf.get("passed", 0),
                    "total": pf.get("total_features", 0),
                })
            except Exception as e2:
                # save_task_result 可能失败（重复记录等），但任务本身已完成
                add_task_log(db, task_id, "warning", f"保存结果时出错: {e2}，但特征生产已完成")
                # 新 session 直接更新状态
                try:
                    db.commit()
                except Exception:
                    pass
                db2 = SessionLocal()
                try:
                    update_task_status(db2, task_id, status="completed", progress=100.0)
                    db2.commit()
                finally:
                    db2.close()
        else:
            update_task_status(db, task_id, status="completed", progress=100.0)
            db.commit()
    except Exception as e:
        import traceback
        error_msg = f"批量生产失败: {e}"
        traceback.print_exc()
        try:
            _add_step_log(db, task_id, "error", "failed", str(e)[:100])
        except Exception:
            pass
        try:
            db.close()
        except Exception:
            pass
        try:
            db2 = SessionLocal()
            update_task_status(db2, task_id, status="failed", progress=0.0, error_message=str(e))
            db2.commit()
            db2.close()
        except Exception:
            pass
    finally:
        try:
            db.close()
        except Exception:
            pass
