"""
JSON工具类
处理numpy类型序列化等问题
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime, date
from decimal import Decimal


class CustomJSONEncoder(json.JSONEncoder):
    """自定义JSON编码器，支持numpy、pandas等类型"""

    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (pd.Timestamp, pd.DatetimeTZDtype)):
            return obj.isoformat()
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, pd.Series):
            return obj.to_dict()
        elif isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient='records')
        return super().default(obj)


def custom_json_dumps(obj, **kwargs) -> str:
    """自定义JSON序列化函数"""
    kwargs.setdefault('cls', CustomJSONEncoder)
    return json.dumps(obj, **kwargs)
