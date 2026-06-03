"""
Feature Deployment Agent - 特征部署Agent

职责：
1. 根据通过筛选的特征列表裁剪特征代码
2. 生成完整的Docker部署包
3. 管理版本（支持回滚）
4. 自动部署在线SaaS服务
5. 生成风控团队私有化部署包

输入：通过评估的特征列表 + 完整特征代码
输出：部署包 + Docker容器
"""

import json
import os
import sys
import shutil
import tarfile
import subprocess
from datetime import datetime
from typing import Dict, List, Optional
import yaml

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


class FeatureDeploymentAgent:
    """特征部署Agent"""

    def __init__(self):
        self.deployment_dir = 'outputs/deployment'
        self.version_info = {}
        self.passed_features = []
        self.full_code_path = None

    def load_passed_features(self, path='outputs/evaluation/passed_features.json'):
        """加载通过筛选的特征列表"""
        print(f"Loading passed features from: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 支持两种格式：
        # 1. 直接是列表
        # 2. 包含passed_features字段
        if isinstance(data, dict):
            self.passed_features = data.get('passed_features', [])
            self.version_info = {
                'total_evaluated': data.get('total_passed', 0),
                'thresholds': data.get('thresholds', {}),
                'metrics': {}
            }
        elif isinstance(data, list):
            self.passed_features = data
            self.version_info = {}

        print(f"   Loaded {len(self.passed_features)} passed features")

        # 如果通过的特征为空，使用所有特征（用于测试）
        if not self.passed_features:
            print("   ⚠️  No passed features found, will use full code as-is")

    def load_full_code(self, path=None):
        """加载完整的特征计算器代码"""
        # 从数据流注册表获取最新路径
        registry_file = 'outputs/feature_code/data_flow_registry.json'
        if path is None and os.path.exists(registry_file):
            with open(registry_file, 'r', encoding='utf-8') as f:
                registry = json.load(f)
            path = registry.get('latest_outputs', {}).get('features_calculator',
                    'outputs/feature_code/features_calculator_v2.py')

        if path is None:
            path = 'outputs/feature_code/features_calculator_v2.py'

        self.full_code_path = path
        print(f"Loading full feature code from: {path}")

        with open(path, 'r', encoding='utf-8') as f:
            self.full_code = f.read()

        print(f"   Loaded {len(self.full_code)} chars, {len(self.full_code.splitlines())} lines")

    def trim_feature_code(self, passed_features: List[str]) -> str:
        """裁剪特征代码，只保留通过筛选的特征

        Args:
            passed_features: 通过筛选的特征名称列表

        Returns:
            裁剪后的代码
        """
        if not passed_features:
            print("   ⚠️  No feature filter, returning full code")
            return self.full_code

        print(f"\n  Trimming code to keep {len(passed_features)} features...")

        lines = self.full_code.split('\n')
        trimmed_lines = []

        # 状态标记
        in_calc_method = False
        current_feature_name = None
        should_keep = True
        indent_level = 0

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # 检测特征计算的赋值语句
            # 如: features['feature_name'] = ...
            if "features['" in line or 'features["' in line:
                # 提取特征名
                feature_name = None
                if "features['" in line:
                    try:
                        feature_name = line.split("features['")[1].split("'")[0]
                    except:
                        pass
                elif 'features["' in line:
                    try:
                        feature_name = line.split('features["')[1].split('"')[0]
                    except:
                        pass

                if feature_name:
                    if feature_name in passed_features:
                        should_keep = True
                    else:
                        should_keep = False

            # 如果应该保留这行
            if should_keep:
                trimmed_lines.append(line)

            i += 1

        trimmed_code = '\n'.join(trimmed_lines)
        print(f"   Original: {len(lines)} lines → Trimmed: {len(trimmed_lines)} lines")

        return trimmed_code

    def generate_version_info(self, version: str = None):
        """生成版本信息"""
        if version is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # 读取现有版本数
            existing_versions = self.list_versions()
            version_num = len(existing_versions) + 1
            version = f"v{version_num}"

        self.version_info.update({
            'version': version,
            'timestamp': datetime.now().isoformat(),
            'passed_features': self.passed_features,
            'total_features': len(self.passed_features)
        })

        return version

    def list_versions(self) -> List[Dict]:
        """列出所有部署版本"""
        if not os.path.exists(self.deployment_dir):
            return []

        versions = []
        for item in os.listdir(self.deployment_dir):
            # Skip symlinks and tar.gz files
            if item.startswith('v') and os.path.isdir(os.path.join(self.deployment_dir, item)):
                version_path = os.path.join(self.deployment_dir, item)
                version_file = os.path.join(version_path, 'config', 'version.json')

                if os.path.exists(version_file):
                    with open(version_file, 'r', encoding='utf-8') as f:
                        info = json.load(f)
                    versions.append({
                        'path': item,
                        'version': info.get('version', 'unknown'),
                        'timestamp': info.get('timestamp', ''),
                        'features': info.get('total_features', 0)
                    })

        return sorted(versions, key=lambda x: x.get('timestamp', ''), reverse=True)

    def create_deployment_package(self, version: str, trimmed_code: str) -> str:
        """创建部署包"""
        print(f"\n  Creating deployment package: {version}")

        package_dir = os.path.join(self.deployment_dir, version)

        # 创建目录结构
        dirs = ['core', 'api', 'config', 'deploy', 'docs', 'tests', 'examples']
        for d in dirs:
            os.makedirs(os.path.join(package_dir, d), exist_ok=True)

        # 1. 保存裁剪后的核心代码
        core_code_path = os.path.join(package_dir, 'core', 'feature_calculator.py')
        with open(core_code_path, 'w', encoding='utf-8') as f:
            f.write(trimmed_code)
        print(f"   ✓ Core code: {core_code_path}")

        # 2. 复制计算函数依赖（channel1_calculators.py）
        calc_src = 'outputs/feature_code/channel1_calculators.py'
        calc_dst = os.path.join(package_dir, 'core', 'channel1_calculators.py')
        if os.path.exists(calc_src):
            shutil.copy(calc_src, calc_dst)
            print(f"   ✓ Calculator functions: {calc_dst}")
        else:
            print(f"   ⚠ channel1_calculators.py not found at {calc_src}")

        # 3. 保存类别配置
        category_config_path = os.path.join(package_dir, 'core', 'category_config.json')
        src_config = 'outputs/feature_code/feature_categories_config.json'
        if os.path.exists(src_config):
            shutil.copy(src_config, category_config_path)
            print(f"   ✓ Category config: {category_config_path}")

        # 3. 保存版本信息
        version_path = os.path.join(package_dir, 'config', 'version.json')
        with open(version_path, 'w', encoding='utf-8') as f:
            json.dump(self.version_info, f, ensure_ascii=False, indent=2)
        print(f"   ✓ Version info: {version_path}")

        # 4. 生成requirements.txt
        requirements = [
            "fastapi>=0.100.0",
            "uvicorn[standard]>=0.23.0",
            "pydantic>=2.0.0",
            "pyyaml>=6.0",
            "pandas>=1.5.0",
            "numpy>=1.24.0",
            "requests>=2.31.0",
            "openpyxl>=3.1.0"
        ]
        req_path = os.path.join(package_dir, 'requirements.txt')
        with open(req_path, 'w') as f:
            f.write('\n'.join(requirements))
        print(f"   ✓ Requirements: {req_path}")

        # 5. 生成配置文件
        self._generate_config(package_dir)

        # 6. 生成API服务代码
        self._generate_api_service(package_dir)

        # 7. 生成Docker文件
        self._generate_docker_files(package_dir)

        # 8. 生成文档
        self._generate_docs(package_dir, version)

        # 9. 生成示例代码
        self._generate_examples(package_dir)

        # 10. 创建tar.gz压缩文件（用于给风控团队）
        tar_path = os.path.join(self.deployment_dir, f"{version}.tar.gz")
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(package_dir, arcname=version)
        print(f"   ✓ Compressed package: {tar_path}")

        # 11. 更新latest软链接
        latest_link = os.path.join(self.deployment_dir, 'latest')
        if os.path.exists(latest_link) or os.path.islink(latest_link):
            os.remove(latest_link)
        os.symlink(version, latest_link)
        print(f"   ✓ Latest -> {version}")

        return package_dir

    def _generate_config(self, package_dir: str):
        """生成运行时配置"""
        config = {
            'server': {
                'host': '0.0.0.0',
                'port': 8000,
                'workers': 2,
                'log_level': 'info'
            },
            'feature_calculator': {
                'code_path': 'core/feature_calculator.py',
                'category_config_path': 'core/category_config.json'
            },
            'batch_processing': {
                'max_batch_size': 10000,
                'default_batch_size': 100,
                'result_ttl_seconds': 3600
            },
            'api': {
                'rate_limit': {
                    'trial': 100,
                    'pro': 10000,
                    'enterprise': 100000
                }
            }
        }

        config_path = os.path.join(package_dir, 'config', 'config.yaml')
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    def _generate_api_service(self, package_dir: str):
        """生成API服务代码"""
        # FastAPI应用
        app_code = '''"""
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
'''

        api_path = os.path.join(package_dir, 'api', 'app.py')
        with open(api_path, 'w', encoding='utf-8') as f:
            f.write(app_code)

    def _generate_docker_files(self, package_dir: str):
        """生成Docker文件"""
        # Dockerfile
        dockerfile = '''FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动
CMD ["python", "api/app.py"]
'''
        with open(os.path.join(package_dir, 'deploy', 'Dockerfile'), 'w') as f:
            f.write(dockerfile)

        # docker-compose.yml
        compose = '''version: '3.8'

services:
  feature-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - PYTHONPATH=/app/core
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 512M
'''
        with open(os.path.join(package_dir, 'deploy', 'docker-compose.yml'), 'w') as f:
            f.write(compose)

    def _generate_docs(self, package_dir: str, version: str):
        """生成文档"""
        readme = f'''# 特征计算服务部署包

**版本**: {version}
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**特征数**: {len(self.passed_features)}

## 快速开始

### 方式1: Docker Compose（推荐）

```bash
cd {version}
docker-compose up -d

# 测试
curl http://localhost:8000/
curl -X POST http://localhost:8000/api/v1/calculate \\
  -H "Content-Type: application/json" \\
  -d @../examples/test_sample.json
```

### 方式2: 直接运行

```bash
cd {version}
pip install -r requirements.txt
python api/app.py
```

## API文档

### 单样本计算
```
POST /api/v1/calculate
Content-Type: application/json

{{
  "order_id": "id002...",
  "apply_time": "2026-03-09 10:00:00",
  "raw_data": {{...}}
}}
```

### 批量计算
```
POST /api/v1/calculate_batch
Content-Type: application/json

{{
  "samples": [...],
  "batch_size": 100
}}
```

## 版本历史

查看 `CHANGELOG.md`

## 技术支持

- 问题反馈: 查看 logs/ 目录
- API文档: http://localhost:8000/docs
'''
        with open(os.path.join(package_dir, 'docs', 'README.md'), 'w', encoding='utf-8') as f:
            f.write(readme)

    def _generate_examples(self, package_dir: str):
        """生成示例代码"""
        # Python示例
        example = '''"""
特征计算API调用示例
"""
import requests
import json

API_BASE = "http://localhost:8000"

def single_calculate():
    """单样本计算"""
    # 加载测试数据
    with open('examples/test_sample.json', 'r') as f:
        sample = json.load(f)

    response = requests.post(
        f"{API_BASE}/api/v1/calculate",
        json={
            "order_id": sample.get("orderId"),
            "apply_time": None,
            "raw_data": sample
        }
    )

    print(f"Status: {response.status_code}")
    print(f"Features: {json.dumps(response.json()['features'], indent=2)}")


def batch_calculate():
    """批量计算"""
    samples = []
    for i in range(10):
        with open('examples/test_sample.json', 'r') as f:
            sample = json.load(f)
        samples.append({
            "order_id": f"test_{i}",
            "raw_data": sample
        })

    response = requests.post(
        f"{API_BASE}/api/v1/calculate_batch",
        json={"samples": samples, "batch_size": 5}
    )

    job_id = response.json()["job_id"]
    print(f"Job ID: {job_id}")

    # 轮询进度
    import time
    while True:
        status_resp = requests.get(f"{API_BASE}/api/v1/batch_status/{job_id}")
        status = status_resp.json()
        print(f"Progress: {status['progress']}%")

        if status["status"] == "completed":
            break
        time.sleep(1)

    # 获取结果
    result_resp = requests.get(f"{API_BASE}/api/v1/batch_results/{job_id}")
    print(f"Results: {len(result_resp.json()['results'])} samples")


if __name__ == "__main__":
    single_calculate()
    # batch_calculate()
'''
        with open(os.path.join(package_dir, 'examples', 'api_usage.py'), 'w') as f:
            f.write(example)

    def deploy_local(self, version: str):
        """本地部署（启动Docker容器）"""
        print(f"\n  Deploying {version} locally...")

        package_dir = os.path.join(self.deployment_dir, version)

        try:
            # 构建Docker镜像
            print("   Building Docker image...")
            result = subprocess.run(
                ['docker', 'build', '-t', f'feature-calc:{version}', '.'],
                cwd=package_dir,
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode != 0:
                print(f"   ⚠️  Docker build failed: {result.stderr[:200]}")
                return False

            print("   ✓ Image built")

            # 启动容器
            print("   Starting container...")
            subprocess.run(
                ['docker', 'compose', 'up', '-d'],
                cwd=os.path.join(package_dir, 'deploy'),
                check=True,
                timeout=60
            )

            print("   ✓ Service running at http://localhost:8000")
            return True

        except Exception as e:
            print(f"   ⚠️  Deployment failed: {e}")
            return False

    def _rollback_version(self, target_version: str) -> bool:
        """回滚到指定版本

        Args:
            target_version: 目标版本号，如 "v2"

        Returns:
            是否成功回滚
        """
        print(f"\n  Rolling back to {target_version}...")

        target_path = os.path.join(self.deployment_dir, target_version)
        if not os.path.exists(target_path):
            print(f"   ⚠️  Version {target_version} not found")
            return False

        # 更新latest软链接
        latest_link = os.path.join(self.deployment_dir, 'latest')
        if os.path.exists(latest_link) or os.path.islink(latest_link):
            os.remove(latest_link)
        os.symlink(target_version, latest_link)
        print(f"   ✓ Latest -> {target_version}")

        # 读取目标版本信息
        version_file = os.path.join(target_path, 'config', 'version.json')
        if os.path.exists(version_file):
            with open(version_file, 'r', encoding='utf-8') as f:
                info = json.load(f)
            print(f"   ✓ Version info: {info.get('version', 'unknown')}")
            print(f"   ✓ Features: {info.get('total_features', 0)}")

        return True

    def print_versions(self):
        """打印所有版本信息"""
        versions = self.list_versions()
        if not versions:
            print("   No versions found")
            return

        print(f"\n  {'Version':<10} {'Timestamp':<25} {'Features':<10} {'Path':<40}")
        print("  " + "-" * 85)
        for v in versions:
            print(f"  {v['version']:<10} {v['timestamp']:<25} {v['features']:<10} {v['path']:<40}")

    def run(self, auto_deploy: bool = True, rollback_version: str = None):
        """主执行流程

        Args:
            auto_deploy: 是否自动部署
            rollback_version: 回滚到指定版本（如"v2"），为None则创建新版本
        """
        print("=" * 70)
        print("特征部署Agent - 开始执行")
        print("=" * 70)

        # 0. 如果指定了回滚版本，执行回滚
        if rollback_version:
            if self._rollback_version(rollback_version):
                print(f"\n✅ Successfully rolled back to {rollback_version}")
            else:
                print(f"\n❌ Failed to rollback to {rollback_version}")
            return

        # 1. 加载通过的特征
        self.load_passed_features()

        # 2. 加载完整代码
        self.load_full_code()

        # 3. 生成版本信息
        version = self.generate_version_info()
        print(f"\n  Version: {version}")

        # 4. 裁剪代码
        trimmed_code = self.trim_feature_code(self.passed_features)

        # 5. 创建部署包
        package_dir = self.create_deployment_package(version, trimmed_code)

        print(f"\n  📦 Package created: {package_dir}")

        # 6. 打印版本号
        self.print_versions()

        # 7. 自动部署（可选）
        if auto_deploy:
            self.deploy_local(version)

        print("\n" + "=" * 70)
        print("特征部署Agent - 执行完成")
        print("=" * 70)
        print(f"\n✅ 部署包: {package_dir}")
        print(f"✅ 压缩包: {package_dir}.tar.gz")
        print(f"✅ 版本: {version}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='特征部署Agent')
    parser.add_argument('--auto-deploy', type=bool, default=True, help='是否自动部署')
    parser.add_argument('--list-versions', action='store_true', help='列出所有版本')
    parser.add_argument('--rollback', type=str, help='回滚到指定版本')

    args = parser.parse_args()

    agent = FeatureDeploymentAgent()

    if args.list_versions:
        agent.print_versions()
    elif args.rollback:
        agent.run(rollback_version=args.rollback)
    else:
        agent.run(auto_deploy=args.auto_deploy)
