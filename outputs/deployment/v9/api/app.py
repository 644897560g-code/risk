"""
Feature Calculation API Service

Single sample:
    POST /api/v1/calculate

Batch processing:
    POST /api/v1/calculate_batch
    GET /api/v1/batch_status/{job_id}
    GET /api/v1/batch_results/{job_id}
"""

import asyncio
import json
import os
import sys
import time
import uuid
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from fastapi import FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor

# 添加core目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))

from feature_calculator import FeatureCalculator

app = FastAPI(title="Feature Calculation Service", version="1.0.0")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 加载版本信息
VERSION_FILE = os.path.join(os.path.dirname(__file__), '..', 'config', 'version.json')
with open(VERSION_FILE, 'r') as f:
    VERSION_INFO = json.load(f)

# 初始化计算器
calculator = FeatureCalculator()

# API Key 鉴权
API_KEY = os.environ.get("FEATURE_API_KEY", "change-me-in-production")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# 超时配置（可通过环境变量覆盖）
CALCULATE_TIMEOUT = float(os.environ.get("CALCULATE_TIMEOUT", "1.8"))  # 单样本计算超时（秒）


def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")
    return api_key


def _version_info() -> Dict[str, Any]:
    """获取版本信息"""
    return {
        "version": VERSION_INFO.get("version"),
        "total_features": VERSION_INFO.get("total_evaluated", 0),
        "passed_features": VERSION_INFO.get("total_evaluated", 0),
    }


def _success_response(order_id: str, features: Dict, elapsed_ms: float) -> Dict:
    return {
        "status": "success",
        "version": VERSION_INFO.get("version"),
        "order_id": order_id,
        "processing_time_ms": round(elapsed_ms, 2),
        "message": "ok",
        "features": features,
    }


def _timeout_response(order_id: str, elapsed_ms: float) -> Dict:
    return {
        "status": "timeout",
        "version": VERSION_INFO.get("version"),
        "order_id": order_id,
        "processing_time_ms": round(elapsed_ms, 2),
        "message": f"计算超过服务端超时限制({int(CALCULATE_TIMEOUT * 1000)}ms)，请降低请求数据量或联系管理员",
        "error_type": "timeout",
        "features": {},
    }


def _error_response(order_id: str, error_msg: str, elapsed_ms: float) -> Dict:
    return {
        "status": "error",
        "version": VERSION_INFO.get("version"),
        "order_id": order_id,
        "processing_time_ms": round(elapsed_ms, 2),
        "message": f"内部计算错误: {error_msg[:200]}",
        "error_type": "calculation_error",
        "features": {},
    }


def _filter_passed_features(features: Dict) -> Dict:
    """只保留通过评估的特征"""
    passed_features = VERSION_INFO.get('passed_features', [])
    if not passed_features:
        return features
    if isinstance(passed_features, list):
        passed_names = {f.get("feature_name", f) if isinstance(f, dict) else f for f in passed_features}
        return {k: v for k, v in features.items() if k in passed_names}
    return features


# 批处理存储
batch_jobs = {}
executor = ThreadPoolExecutor(max_workers=4)


class CalculateRequest(BaseModel):
    order_id: str
    apply_time: Optional[Union[int, str]] = None  # 支持毫秒时间戳(int) 或 日期字符串(YYYY-MM-DD)
    raw_data: Dict


class BatchRequest(BaseModel):
    samples: List[CalculateRequest]
    batch_size: Optional[int] = 100


@app.get("/")
async def root():
    return {
        "service": "Feature Calculation Service",
        "version": VERSION_INFO.get("version"),
        "features": VERSION_INFO.get("total_evaluated", 0),
        "status": "running",
    }


@app.post("/api/v1/calculate")
async def calculate(request: CalculateRequest, _=Security(verify_api_key)):
    """单样本特征计算（带超时控制）"""
    start_time = time.time()

    try:
        # 异步执行计算，带超时
        features = await asyncio.wait_for(
            asyncio.to_thread(
                calculator.calculate_all,
                request.raw_data,
                apply_time=request.apply_time,
            ),
            timeout=CALCULATE_TIMEOUT,
        )

        elapsed_ms = (time.time() - start_time) * 1000
        filtered_features = _filter_passed_features(features)
        return _success_response(request.order_id, filtered_features, elapsed_ms)

    except asyncio.TimeoutError:
        elapsed_ms = (time.time() - start_time) * 1000
        return _timeout_response(request.order_id, elapsed_ms)

    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        import traceback
        print(f"ERROR calculating features: {traceback.format_exc()}")
        return _error_response(request.order_id, str(e), elapsed_ms)


@app.post("/api/v1/calculate_batch")
async def calculate_batch(request: BatchRequest, _=Security(verify_api_key)):
    """批量特征计算（异步）"""
    job_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    batch_jobs[job_id] = {
        "status": "processing",
        "progress": 0.0,
        "total": len(request.samples),
        "processed": 0,
        "results": [],
        "created_at": datetime.now().isoformat(),
    }

    # 异步处理
    executor.submit(_process_batch, job_id, request.samples, request.batch_size)

    return {
        "status": "processing",
        "job_id": job_id,
        "total": len(request.samples),
    }


@app.get("/api/v1/batch_status/{job_id}")
async def batch_status(job_id: str):
    """查询批处理进度"""
    if job_id not in batch_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = batch_jobs[job_id]
    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "total": job["total"],
        "processed": job["processed"],
    }


@app.get("/api/v1/batch_results/{job_id}")
async def batch_results(job_id: str):
    """获取批处理结果"""
    if job_id not in batch_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = batch_jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed. Status: {job['status']}",
        )

    return {
        "job_id": job_id,
        "status": "completed",
        "total": job["total"],
        "results": job["results"],
    }


def _process_batch(job_id: str, samples: List[CalculateRequest], batch_size: int):
    """处理批任务"""
    job = batch_jobs[job_id]

    try:
        for i in range(0, len(samples), batch_size):
            batch = samples[i:i + batch_size]

            for sample in batch:
                sample_start = time.time()
                try:
                    features = calculator.calculate_all(
                        sample.raw_data,
                        apply_time=sample.apply_time,
                    )
                    filtered_features = _filter_passed_features(features)
                    elapsed_ms = (time.time() - sample_start) * 1000

                    job["results"].append({
                        "order_id": sample.order_id,
                        "status": "success",
                        "processing_time_ms": round(elapsed_ms, 2),
                        "features": filtered_features,
                    })
                except Exception as e:
                    elapsed_ms = (time.time() - sample_start) * 1000
                    job["results"].append({
                        "order_id": sample.order_id,
                        "status": "error",
                        "processing_time_ms": round(elapsed_ms, 2),
                        "message": str(e)[:200],
                        "features": {},
                    })

                job["processed"] += 1

            job["progress"] = round(job["processed"] / job["total"] * 100, 2)

        job["status"] = "completed"
        job["completed_at"] = datetime.now().isoformat()

    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
