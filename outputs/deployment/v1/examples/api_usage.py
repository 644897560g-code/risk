"""
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
