"""Feature management API routes — versions, metrics, reports"""
import json
import os
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.config import get_settings
from backend.app.database import get_db
from backend.models.feature import FeatureVersion, FeatureMetric

router = APIRouter()


@router.get("/versions")
def api_feature_versions(
    project_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """获取所有特征版本列表"""
    query = db.query(FeatureVersion)
    if project_id is not None:
        query = query.filter(FeatureVersion.project_id == project_id)
    items = query.order_by(desc(FeatureVersion.id)).all()
    return {"items": [v.to_dict() for v in items]}


@router.get("/versions/{version}")
def api_feature_version_detail(
    version: str,
    project_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """获取某个版本的详细特征指标"""
    query = db.query(FeatureMetric).filter(FeatureMetric.version == version)
    if project_id is not None:
        query = query.filter(FeatureMetric.project_id == project_id)
    items = query.order_by(desc(FeatureMetric.iv)).all()

    if not items:
        raise HTTPException(status_code=404, detail=f"版本 {version} 不存在或没有评估数据")

    passed = sum(1 for i in items if i.is_passed)
    return {
        "version": version,
        "total": len(items),
        "passed": passed,
        "items": [i.to_dict() for i in items],
    }


@router.get("/versions/{version}/report")
def api_feature_version_report(version: str):
    """返回某版本的HTML评估报告"""
    settings = get_settings()
    report_path = os.path.join(settings.evaluation_dir, "feature_evaluation_report.html")
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="评估报告文件不存在")

    from fastapi.responses import HTMLResponse
    with open(report_path, "r", encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(content=html)


@router.get("/stats")
def api_feature_stats():
    """获取全局特征统计（累计通过数、最新版本等）"""
    settings = get_settings()

    # 读取累计通过特征数
    acc_path = os.path.join(settings.evaluation_dir, "accumulated_passed_features.json")
    accumulated_passed = 0
    if os.path.exists(acc_path):
        with open(acc_path) as f:
            acc = json.load(f)
        accumulated_passed = acc.get("total_passed", 0)

    # 读取最新版本评估结果
    pf_path = os.path.join(settings.evaluation_dir, "passed_features.json")
    current_total = 0
    current_passed = 0
    if os.path.exists(pf_path):
        with open(pf_path) as f:
            pf = json.load(f)
        current_total = pf.get("total_features", 0)
        current_passed = pf.get("passed", 0)

    # 读取最新版本号
    latest_version = ""
    dv_path = os.path.join(settings.evaluation_dir, "..", "deployment")
    if os.path.exists(dv_path):
        versions = [d for d in os.listdir(dv_path) if d.startswith("v") and os.path.isdir(os.path.join(dv_path, d))]
        if versions:
            latest_version = sorted(versions, key=lambda x: int(x[1:]))[-1]

    return {
        "current_total": current_total,
        "current_passed": current_passed,
        "accumulated_passed": accumulated_passed,
        "latest_version": latest_version,
    }


@router.get("/top")
def api_feature_top(
    n: int = 20,
    project_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """获取所有版本中IV最高的Top N特征"""
    query = db.query(FeatureMetric)
    if project_id is not None:
        query = query.filter(FeatureMetric.project_id == project_id)
    items = query.order_by(desc(FeatureMetric.iv)).limit(n).all()
    return {"items": [i.to_dict() for i in items]}


class ComputeRequest(BaseModel):
    samples: list[dict]


@router.post("/compute")
def api_feature_compute(body: ComputeRequest):
    """上传样本数据并计算所有特征值 (POST /api/features/compute)"""
    settings = get_settings()
    samples = body.samples

    # 1. 动态导入 FeatureCalculator
    calculator_path = os.path.join(settings.output_dir, "feature_code", "features_calculator_v2.py")
    if not os.path.exists(calculator_path):
        raise HTTPException(status_code=500, detail="特征计算器文件不存在")

    import importlib.util
    spec = importlib.util.spec_from_file_location("features_calculator_module", calculator_path)
    if spec is None or spec.loader is None:
        raise HTTPException(status_code=500, detail="无法加载特征计算器模块")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    CalculatorCls = getattr(mod, "FeatureCalculator", None)
    if CalculatorCls is None:
        raise HTTPException(status_code=500, detail="FeatureCalculator 类未找到")

    # 2. 加载 APP 分类缓存
    app_cache = _load_app_cache(os.path.join(settings.output_dir, "app_analysis"))

    # 3. 加载参考分布
    ref_dist = _load_ref_distribution(settings.evaluation_dir)

    try:
        calculator = CalculatorCls(app_category_cache=app_cache, ref_distributions=ref_dist)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"初始化计算器失败: {e}")

    # 4. 逐个计算特征
    results = []
    for sample in samples:
        order_id = sample.get("order_id") or sample.get("orderId", "")
        t0 = time.time()
        try:
            features = calculator.calculate_all(sample)
            elapsed = round((time.time() - t0) * 1000, 2)
            results.append({
                "order_id": order_id,
                "features": features,
                "processing_time_ms": elapsed,
            })
        except Exception as e:
            results.append({
                "order_id": order_id,
                "features": {},
                "processing_time_ms": 0,
                "error": str(e),
            })

    return {"total": len(results), "results": results}


def _load_app_cache(cache_dir: str) -> dict:
    """加载最新的 APP 分类缓存文件（返回 classifications 子字段）"""
    if not os.path.exists(cache_dir):
        return {}
    files = [f for f in os.listdir(cache_dir)
             if f.startswith("classification_complete_") and f.endswith(".json")]
    if not files:
        return {}
    latest = max(files, key=lambda f: os.path.getmtime(os.path.join(cache_dir, f)))
    with open(os.path.join(cache_dir, latest)) as f:
        raw = json.load(f)
    # The cache file contains {total_apps, classification_date, model, classifications: {...}}
    if isinstance(raw, dict) and "classifications" in raw:
        return raw["classifications"]
    return raw


def _load_ref_distribution(eval_dir: str) -> dict:
    """加载参考分布（如存在）"""
    path = os.path.join(eval_dir, "ref_distributions.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


@router.get("/download/{version}")
def api_download_deployment(version: str):
    """下载指定版本的部署包"""
    settings = get_settings()
    # Try .tar.gz first, then directory
    tarball = os.path.join(settings.deployment_dir, f"{version}.tar.gz")
    dir_path = os.path.join(settings.deployment_dir, version)
    if os.path.exists(tarball):
        from fastapi.responses import FileResponse
        return FileResponse(tarball, filename=f"{version}.tar.gz", media_type="application/gzip")
    elif os.path.exists(dir_path):
        import shutil
        import tempfile
        tmp = os.path.join(tempfile.gettempdir(), f"{version}.tar.gz")
        shutil.make_archive(tmp.replace(".tar.gz", ""), "gztar", dir_path)
        from fastapi.responses import FileResponse
        return FileResponse(tmp, filename=f"{version}.tar.gz", media_type="application/gzip")
    raise HTTPException(status_code=404, detail=f"版本 {version} 部署包不存在")
