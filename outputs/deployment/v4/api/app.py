"""
Feature Calculation API Service

Single sample:
    POST /api/v1/calculate

Batch processing:
    POST /api/v1/calculate_batch
    GET /api/v1/batch_status/{job_id}
    GET /api/v1/batch_results/{job_id}
"""

import json
import os
import sys
import time
import uuid
from typing import Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

# 批处理存储
batch_jobs = {}
executor = ThreadPoolExecutor(max_workers=4)


class CalculateRequest(BaseModel):
    order_id: str
    apply_time: Optional[str] = None
    raw_data: Dict


class BatchRequest(BaseModel):
    samples: List[CalculateRequest]
    batch_size: Optional[int] = 100


@app.get("/")
async def root():
    return {
        "service": "Feature Calculation Service",
        "version": VERSION_INFO.get("version"),
        "features": VERSION_INFO.get("total_features"),
        "status": "running"
    }


@app.post("/api/v1/calculate")
async def calculate(request: CalculateRequest):
    """单样本特征计算"""
    start_time = time.time()

    try:
        features = calculator.calculate_all(request.raw_data, apply_time=request.apply_time)

        # 只返回通过的特征
        passed_features = VERSION_INFO.get('passed_features', [])
        filtered_features = {
            k: v for k, v in features.items()
            if k in passed_features or not passed_features
        }

        return {
            "status": "success",
            "version": VERSION_INFO.get("version"),
            "order_id": request.order_id,
            "processing_time_ms": round((time.time() - start_time) * 1000, 2),
            "features": filtered_features
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/calculate_batch")
async def calculate_batch(request: BatchRequest):
    """批量特征计算（异步）"""
    job_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    batch_jobs[job_id] = {
        "status": "processing",
        "progress": 0.0,
        "total": len(request.samples),
        "processed": 0,
        "results": [],
        "created_at": datetime.now().isoformat()
    }

    # 异步处理
    executor.submit(_process_batch, job_id, request.samples, request.batch_size)

    return {
        "status": "processing",
        "job_id": job_id,
        "total": len(request.samples)
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
        "processed": job["processed"]
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
            detail=f"Job not completed. Status: {job['status']}"
        )

    return {
        "job_id": job_id,
        "status": "completed",
        "total": job["total"],
        "results": job["results"]
    }


def _process_batch(job_id: str, samples: List[CalculateRequest], batch_size: int):
    """处理批任务"""
    job = batch_jobs[job_id]

    try:
        for i in range(0, len(samples), batch_size):
            batch = samples[i:i + batch_size]

            for sample in batch:
                try:
                    features = calculator.calculate_all(
                        sample.raw_data,
                        apply_time=sample.apply_time
                    )

                    passed_features = VERSION_INFO.get('passed_features', [])
                    filtered_features = {
                        k: v for k, v in features.items()
                        if k in passed_features or not passed_features
                    }

                    job["results"].append({
                        "order_id": sample.order_id,
                        "features": filtered_features
                    })
                except Exception as e:
                    job["results"].append({
                        "order_id": sample.order_id,
                        "error": str(e)
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
