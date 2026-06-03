"""
特征计算示例: FDC查询近3天机构数
防穿越约束: 只使用 loan_date 之前的数据
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any


def calc_fdc_inquiry_3d(params: Dict[str, Any], loan_date: str) -> int:
    """
    计算近3天的FDC查询机构数量。

    Args:
        params: 订单参数 (包含 FDC.history_inquiry)
        loan_date: 申请时间字符串 (YYYY-MM-DD)

    Returns:
        近3天查询机构数
    """
    loan_dt = datetime.strptime(loan_date, "%Y-%m-%d")
    cutoff = loan_dt - timedelta(days=3)

    history = params.get("FDC", {}).get("history_inquiry", [])
    unique_orgs = set()

    for inquiry in history:
        inquiry_time = inquiry.get("time", "")
        if not inquiry_time:
            continue
        try:
            t = datetime.strptime(inquiry_time, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                t = datetime.strptime(inquiry_time, "%Y-%m-%d")
            except ValueError:
                continue

        # 防穿越: 只统计申请时间之前的查询
        if cutoff <= t <= loan_dt:
            unique_orgs.add(inquiry.get("organization", ""))

    return len(unique_orgs)


def calc_app_gambling_ratio(params: Dict[str, Any], app_categories: Dict[str, str]) -> float:
    """
    计算赌博类APP占总安装APP的比例。

    Args:
        params: 订单参数 (包含 appList)
        app_categories: APP分类映射 {package_name: category}

    Returns:
        赌博类APP占比 (0.0 ~ 1.0)
    """
    app_list = params.get("appList", [])
    if not app_list:
        return 0.0

    total = len(app_list)
    gambling_count = sum(
        1 for app in app_list
        if app_categories.get(app.get("packageName", "")) == "gambling"
    )

    return round(gambling_count / total, 6)
