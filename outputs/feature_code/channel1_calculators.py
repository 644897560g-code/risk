"""
通道1 DSL Python计算函数骨架

15个计算函数（T001-T015），业务无关的纯计算逻辑。
所有函数接受 apply_time_dt 作为防穿越基准时间。
"""

import math
import numpy as np
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable


# ============================================================
# 辅助函数
# ============================================================

def _filter_by_time(data: Dict, source: str, apply_time_dt: datetime, window_days: int) -> List:
    """按时间和数据源过滤记录（防穿越）"""
    cutoff = apply_time_dt - timedelta(days=window_days)
    cutoff_ms = int(cutoff.timestamp() * 1000)

    if source == 'applist':
        items = data.get('params', {}).get('appList', [])
        apply_ms = int(apply_time_dt.timestamp() * 1000)
        cutoff_ms = int(cutoff.timestamp() * 1000)
        return [i for i in items if cutoff_ms <= i.get('inTime', 0) <= apply_ms
                and (i.get('upTime', 0) <= apply_ms or i.get('upTime', 0) == 0)]

    elif source.startswith('fdc_'):
        fdc = data.get('params', {}).get('FDC', {})
        if source == 'fdc_pinjaman':
            items = fdc.get('pinjaman', [])
            filtered = []
            for loan in items:
                disburse_str = loan.get('tgl_penyaluran_dana', '')
                if disburse_str:
                    try:
                        disburse_date = datetime.strptime(disburse_str, '%Y-%m-%d')
                        if cutoff <= disburse_date <= apply_time_dt:
                            filtered.append(loan)
                    except:
                        pass
            return filtered
        elif source == 'fdc_inquiry':
            inquiries = fdc.get('history_inquiry', {})
            # 从 statistic 的预聚合值构造虚拟记录，使 calc_count 能正确计数
            # key 映射: "30_hari" → 30天, "90_hari" → 90天, 等
            stat = inquiries.get('statistic', {})
            window_key_map = {
                3: '3_hari', 7: '7_hari', 30: '30_hari',
                90: '90_hari', 180: '180_hari', 360: '360_hari'}
            target_key = window_key_map.get(window_days)
            count_val = stat.get(target_key, 0) if target_key else 0

            # 构造虚拟记录，使 calc_count 能正确返回统计值
            virtual_records = [{'stat_inquiry_count': count_val}] * count_val if count_val > 0 else []
            return virtual_records
        return []

    return []


def _get_event_time(item: Dict) -> datetime:
    """获取记录的事件时间

    支持多种时间字段：
    - inTime (applist, 毫秒时间戳)
    - tgl_penyaluran_dana (fdc_pinjaman贷款, 'YYYY-MM-DD' 字符串)
    """
    in_time = item.get('inTime', 0)
    if in_time:
        return datetime.fromtimestamp(in_time / 1000)

    disburse = item.get('tgl_penyaluran_dana', '')
    if disburse:
        try:
            return datetime.strptime(disburse, '%Y-%m-%d')
        except:
            pass

    return datetime.now()


def _get_event_day(item: Dict) -> str:
    """获取记录的事件日期（YYYY-MM-DD）"""
    dt = _get_event_time(item)
    return dt.strftime('%Y-%m-%d')


def _eval_cond(item: Dict, cond: Optional[Dict]) -> bool:
    """评估过滤条件"""
    if not cond:
        return True
    for key, value in cond.items():
        item_val = item.get(key)
        if isinstance(value, list):
            if item_val not in value:
                return False
        elif item_val != value:
            return False
    return True


def _get_category(app: Dict) -> str:
    """获取APP分类（从缓存中）"""
    # 此函数在特征计算器中由外部注入的cache覆盖
    return 'other'


def _get_nested(data: Dict, path: str) -> Any:
    """从嵌套字典中取值，如 'base.salary'"""
    parts = path.split('.')
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _filter_apps_by_category(items: List, allowed_categories: set,
                             category_cache: Dict[str, Dict]) -> List:
    """基于外部分类缓存过滤APP列表

    Args:
        items: applist items (每个含 packageX 字段)
        allowed_categories: 允许的类别集合 (如 {'gambling'})
        category_cache: 分类缓存 {packageX: {category: str}}

    Returns:
        匹配类别的APP列表
    """
    if not items or not allowed_categories:
        return []
    return [i for i in items
            if category_cache.get(i.get('packageX', ''), {}).get('category') in allowed_categories]


def calc_proportion_by_category(data: Dict, allowed_categories: set,
                                 apply_time_dt: datetime, window_days: int = 30,
                                 min_denominator: int = 0,
                                 category_cache: Dict[str, Dict] = None) -> float:
    """基于外部分类缓存的占比计算（用于applist的gambling/loan等类别比例）

    DSL: count_by_category(allowed_categories, window) / count(all, window)

    Args:
        data: 订单数据
        allowed_categories: 允许的类别集合
        apply_time_dt: 申请时间
        window_days: 回溯窗口天数
        min_denominator: 分母最小阈值（低于此值返回0）
        category_cache: 分类缓存 {packageX: {category: str}}

    Returns:
        占比 (0.0-1.0)
    """
    items = _filter_by_time(data, 'applist', apply_time_dt, window_days)
    if not isinstance(items, list):
        return 0.0

    total = len(items)
    if total <= min_denominator:
        return 0.0

    if not category_cache:
        return 0.0

    target_count = len(_filter_apps_by_category(items, allowed_categories, category_cache))
    return float(target_count / total if total > 0 else 0.0)


def calc_concentration_by_category(data: Dict, apply_time_dt: datetime,
                                    window_days: int = 30,
                                    category_cache: Dict[str, Dict] = None,
                                    method: str = 'entropy') -> float:
    """基于外部分类缓存的类别分布集中度计算

    DSL: entropy|gini|cv(category_from_cache, applist, window)

    使用分类缓存确定每个APP的类别，然后计算类别分布的集中度。

    Args:
        data: 订单数据
        apply_time_dt: 申请时间
        window_days: 回溯窗口天数
        category_cache: 分类缓存 {packageX: {category: str}}
        method: 计算方法（entropy/gini/cv）

    Returns:
        集中度指数
    """
    items = _filter_by_time(data, 'applist', apply_time_dt, window_days)
    if not isinstance(items, list) or not items or not category_cache:
        return 0.0

    from collections import Counter
    counts = Counter()
    for item in items:
        cat = category_cache.get(item.get('packageX', ''), {}).get('category', 'unknown')
        counts[cat] += 1

    import math
    total = sum(counts.values())
    if total == 0:
        return 0.0

    if method == 'entropy':
        probs = [c / total for c in counts.values()]
        entropy_val = -sum(p * math.log2(p + 1e-10) for p in probs)
        n_cats = len(counts)
        max_entropy = math.log2(max(n_cats, 2))
        return entropy_val / max_entropy if max_entropy > 0 else 0.0
    elif method == 'gini':
        sorted_counts = sorted(counts.values())
        n = len(sorted_counts)
        cumsum = sum((i + 1) * c for i, c in enumerate(sorted_counts))
        gini_val = (2 * cumsum - total * (n + 1)) / (total * n) if total * n > 0 else 0
        return float(gini_val)
    elif method == 'cv':
        values = list(counts.values())
        mean_val = total / len(counts) if counts else 0
        if mean_val == 0:
            return 0.0
        variance = sum((v - mean_val) ** 2 for v in values) / len(values)
        return float(math.sqrt(variance) / mean_val)
    return 0.0


# ============================================================
# 维度一：存量 (Volume) — T001 to T003
# ============================================================

def calc_count(data: Dict, field_set: str, apply_time_dt: datetime,
               window_days: int = 30, cond: Optional[Dict] = None) -> float:
    """
    DSL: count(field_set, window, cond)
    计算指定数据源在时间窗口内的记录数

    Args:
        data: 订单数据
        field_set: 数据源标识（applist/fdc_pinjaman/fdc_inquiry）
        apply_time_dt: 申请时间（防穿越基准）
        window_days: 回溯窗口天数
        cond: 过滤条件

    Returns:
        记录数
    """
    items = _filter_by_time(data, field_set, apply_time_dt, window_days)
    if isinstance(items, dict):
        # 预聚合数据，直接取值
        return float(items.get(str(window_days) + 'days', 0))
    if cond:
        # 对 fdc_inquiry 跳过 cond 过滤（虚拟记录不支持条件过滤）
        if field_set != 'fdc_inquiry':
            items = [i for i in items if _eval_cond(i, cond)]
    return float(len(items))


def calc_distinct_count(data: Dict, dedup_field: str, field_set: str,
                        apply_time_dt: datetime, window_days: int = 30) -> float:
    """
    DSL: distinct(dedup_field, field_set, window)
    计算某数据源在窗口内的去重记录数

    Args:
        data: 订单数据
        dedup_field: 去重字段名
        field_set: 数据源标识
        apply_time_dt: 申请时间
        window_days: 回溯窗口天数

    Returns:
        去重计数
    """
    items = _filter_by_time(data, field_set, apply_time_dt, window_days)
    if not isinstance(items, list):
        return 0.0
    unique_values = set()
    for item in items:
        val = item.get(dedup_field)
        if val is not None:
            unique_values.add(val)
    return float(len(unique_values))


def calc_decayed_sum(data: Dict, field_set: str, apply_time_dt: datetime,
                     window_days: int = 90, decay_func: str = 'linear',
                     decay_rate: float = 0.7, value_field: str = None) -> float:
    """
    DSL: decayed_sum(field_set, window, decay_func, decay_rate, value_field)
    按时间衰减加权计算累计值

    Args:
        data: 订单数据
        field_set: 数据源标识
        apply_time_dt: 申请时间
        window_days: 回溯窗口天数
        decay_func: 衰减函数（linear/exponential）
        decay_rate: 衰减率
        value_field: 要加权的数值字段名（如 'nilai_pendanaan'；None时只计权重）

    Returns:
        衰减加权累计值
    """
    items = _filter_by_time(data, field_set, apply_time_dt, window_days)
    if not isinstance(items, list):
        return 0.0

    total = 0.0
    for item in items:
        event_time = _get_event_time(item)
        days_ago = (apply_time_dt - event_time).days
        if days_ago < 0:
            continue
        if decay_func == 'linear':
            weight = max(0.0, 1.0 - days_ago / window_days)
        elif decay_func == 'exponential':
            weight = decay_rate ** (days_ago / 30.0)
        else:
            weight = 1.0

        if value_field:
            field_val = item.get(value_field, 0)
            try:
                field_val = float(field_val)
            except (ValueError, TypeError):
                field_val = 0.0
            total += weight * field_val
        else:
            total += weight
    return total


# ============================================================
# 维度二：结构 (Structure) — T004 to T006
# ============================================================

def calc_proportion(data: Dict, target_cond: Dict, apply_time_dt: datetime,
                    total_cond: Optional[Dict] = None,
                    window_days: int = 30,
                    min_denominator: int = 0, source: str = 'applist') -> float:
    """
    DSL: count(target_set, window) / count(total_set, window)
    计算目标子集占总体的比例

    Args:
        data: 订单数据
        target_cond: 目标子集过滤条件
        total_cond: 全集范围（已弃用，使用 source 参数替代）
        apply_time_dt: 申请时间
        window_days: 回溯窗口天数
        min_denominator: 分母最小阈值（低于此值返回0）
        source: 数据源标识（applist/fdc_pinjaman/fdc_inquiry）

    Returns:
        占比（0.0-1.0）
    """
    all_items = _filter_by_time(data, source, apply_time_dt, window_days)
    if not isinstance(all_items, list):
        return 0.0

    total = len(all_items)
    if total <= min_denominator:
        return 0.0

    # 目标子集过滤（对 fdc_inquiry 跳过 cond，因为虚拟记录不支持条件过滤）
    if source == 'fdc_inquiry':
        return float(1.0 if total > 0 else 0.0)
    target_items = [i for i in all_items if _eval_cond(i, target_cond)]
    return float(len(target_items) / total if total > 0 else 0.0)


def calc_concentration(data: Dict, method: str, category_field: str,
                       field_set: str, apply_time_dt: datetime,
                       window_days: int = 30) -> float:
    """
    DSL: entropy|gini|cv(category_field, field_set, window)
    计算类别分布的集中度/分散度指标

    Args:
        data: 订单数据
        method: 计算方法（entropy/gini/cv）
        category_field: 分类字段名
        field_set: 数据源标识
        apply_time_dt: 申请时间
        window_days: 回溯窗口天数

    Returns:
        集中度指数
    """
    items = _filter_by_time(data, field_set, apply_time_dt, window_days)
    if not isinstance(items, list) or not items:
        return 0.0

    counts = Counter()
    for item in items:
        val = item.get(category_field)
        if val is not None:
            counts[val] += 1

    total = sum(counts.values())
    if total == 0:
        return 0.0

    if method == 'entropy':
        probs = [c / total for c in counts.values()]
        entropy_val = -sum(p * math.log2(p + 1e-10) for p in probs)
        # 归一化到0-1（除以max entropy）
        n_cats = len(counts)
        max_entropy = math.log2(max(n_cats, 2))
        return entropy_val / max_entropy if max_entropy > 0 else 0.0

    elif method == 'gini':
        sorted_counts = sorted(counts.values())
        n = len(sorted_counts)
        cumsum = 0
        for i, c in enumerate(sorted_counts):
            cumsum += (i + 1) * c
        gini_val = (2 * cumsum - total * (n + 1)) / (total * n) if total * n > 0 else 0
        return float(gini_val)

    elif method == 'cv':
        values = list(counts.values())
        mean_val = total / len(counts) if counts else 0
        if mean_val == 0:
            return 0.0
        variance = sum((v - mean_val) ** 2 for v in values) / len(values)
        std_val = math.sqrt(variance)
        return float(std_val / mean_val)

    return 0.0


def calc_overlap(data: Dict, source_a: str, field_a: str,
                 source_b: str, field_b: str,
                 apply_time_dt: datetime, window_days: int = 30) -> float:
    """
    DSL: overlap(field_a, field_b, source_a, source_b, window)
    计算两个数据源在指定字段上的重叠度（Jaccard相似度）

    Args:
        data: 订单数据
        source_a: 数据源A
        field_a: 数据源A的字段
        source_b: 数据源B
        field_b: 数据源B的字段
        apply_time_dt: 申请时间
        window_days: 回溯窗口天数

    Returns:
        Jaccard重叠度（0.0-1.0）
    """
    items_a = _filter_by_time(data, source_a, apply_time_dt, window_days)
    items_b = _filter_by_time(data, source_b, apply_time_dt, window_days)
    if not isinstance(items_a, list) or not isinstance(items_b, list):
        return 0.0

    set_a = set()
    for item in items_a:
        val = item.get(field_a)
        if val is not None:
            set_a.add(str(val))

    set_b = set()
    for item in items_b:
        val = item.get(field_b)
        if val is not None:
            set_b.add(str(val))

    if not set_a or not set_b:
        return 0.0

    intersection = set_a & set_b
    union = set_a | set_b
    return float(len(intersection) / len(union) if union else 0.0)


# ============================================================
# 维度三：变化 (Change) — T007 to T009
# ============================================================

def calc_period_compare(data: Dict, field_set: str, short_window: int,
                        long_window: int, apply_time_dt: datetime) -> float:
    """
    DSL: (count(field, short_w) / count(field, long_w)) - 1
    计算短窗口与长窗口的变化率（日均归一化）

    Args:
        data: 订单数据
        field_set: 数据源标识
        short_window: 短窗口天数
        long_window: 长窗口天数
        apply_time_dt: 申请时间

    Returns:
        变化率（正=加速，负=减速，0=平稳）
    """
    short_count = calc_count(data, field_set, apply_time_dt, short_window)
    long_count = calc_count(data, field_set, apply_time_dt, long_window)

    short_daily = short_count / short_window
    long_daily = long_count / long_window

    if long_daily == 0:
        return 0.0
    return float((short_daily - long_daily) / long_daily)


def calc_trend(data: Dict, field_set: str, windows: List[int],
               apply_time_dt: datetime) -> float:
    """
    DSL: slope(count(w1), count(w2), count(w3))
    计算三段窗口的趋势斜率（线性拟合）

    Args:
        data: 订单数据
        field_set: 数据源标识
        windows: 三个窗口天数 [w1, w2, w3]
        apply_time_dt: 申请时间

    Returns:
        趋势斜率（正=增长，负=下降，绝对值越大趋势越强）
    """
    counts = []
    for w in windows:
        c = calc_count(data, field_set, apply_time_dt, w)
        counts.append(c / w)  # 日均归一化

    n = len(counts)
    if n < 2:
        return 0.0

    # 线性拟合 y = a + bx, 求斜率b
    x_vals = list(range(n))
    x_mean = sum(x_vals) / n
    y_mean = sum(counts) / n

    numerator = sum((x_vals[i] - x_mean) * (counts[i] - y_mean) for i in range(n))
    denominator = sum((x_vals[i] - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return 0.0
    return float(numerator / denominator)


def calc_spike(data: Dict, field_set: str, window_days: int,
               threshold: float, apply_time_dt: datetime) -> float:
    """
    DSL: max_daily(field, window) > threshold * avg_daily(field, window)
    检测是否存在某天的指标异常爆发

    Args:
        data: 订单数据
        field_set: 数据源标识
        window_days: 回溯窗口天数
        threshold: 爆发阈值（倍数）
        apply_time_dt: 申请时间

    Returns:
        最大爆发倍数（>=threshold时返回倍数，否则返回0）
    """
    # 对 fdc_inquiry 不适用（预聚合统计值，无单日明细）
    # 应使用 applist 或 fdc_pinjaman（有逐条记录+时间戳）
    if field_set == 'fdc_inquiry':
        return 0.0

    items = _filter_by_time(data, field_set, apply_time_dt, window_days)
    if not isinstance(items, list) or not items:
        return 0.0

    daily = defaultdict(int)
    for item in items:
        day_key = _get_event_day(item)
        daily[day_key] += 1

    if not daily:
        return 0.0

    avg_daily = sum(daily.values()) / max(len(daily), 1)
    max_daily = max(daily.values())

    if avg_daily == 0:
        return 0.0

    spike_ratio = max_daily / avg_daily
    return float(spike_ratio if spike_ratio >= threshold else 0.0)


# ============================================================
# 维度四：定位 (Position) — T010 to T012
# ============================================================

def calc_percentile(value: float, reference_distribution: List[float]) -> float:
    """
    DSL: percent_rank(value, reference_distribution)
    计算一个值在参考分布中的百分位排名

    Args:
        value: 目标值
        reference_distribution: 参考分布（数值列表）

    Returns:
        百分位排名（0.0-1.0）
    """
    if not reference_distribution:
        return 0.5

    count_less = sum(1 for v in reference_distribution if v < value)
    count_equal = sum(1 for v in reference_distribution if v == value)
    total = len(reference_distribution)

    return float((count_less + 0.5 * count_equal) / total)


def calc_deviation(value: float, ref_mean: float, ref_std: float) -> float:
    """
    DSL: (value - mean) / std
    计算一个值偏离参考分布均值的标准差倍数（Z-Score）

    Args:
        value: 目标值
        ref_mean: 参考分布均值
        ref_std: 参考分布标准差

    Returns:
        Z-Score
    """
    if ref_std == 0 or ref_std is None:
        return 0.0
    return float((value - ref_mean) / ref_std)


def calc_anomaly(feature_vector: List[float], reference_matrix: List[List[float]],
                 method: str = 'mahalanobis') -> float:
    """
    DSL: isolation_score(feature_vector, reference_matrix)
    计算用户的特征向量是否异常离群

    Args:
        feature_vector: 目标用户特征向量
        reference_matrix: 参考矩阵（行=样本，列=特征）
        method: 异常检测方法

    Returns:
        异常度（0.0-1.0，越大越异常）
    """
    vec = np.array(feature_vector, dtype=float)
    ref = np.array(reference_matrix, dtype=float)

    if len(ref) < 2 or ref.shape[1] != len(vec):
        return 0.0

    if method == 'mahalanobis':
        mean = np.mean(ref, axis=0)
        cov = np.cov(ref.T)
        try:
            inv_cov = np.linalg.inv(cov)
            diff = vec - mean
            d = float(np.sqrt(np.dot(np.dot(diff, inv_cov), diff)))
            return min(d / 10.0, 1.0)
        except np.linalg.LinAlgError:
            return 0.0

    return 0.0


# ============================================================
# 维度五：一致性 (Consistency) — T013 to T015
# ============================================================

def calc_declared_vs_actual(data: Dict, declared_field: str, actual_field: str,
                            method: str = 'ratio') -> float:
    """
    DSL: ratio(declared / actual)
    比较用户申报值和实际值的差异

    注意：actual_field 可能指向 FDC pinjaman 数组中的字段（如 nilai_pendanaan），
    这种情况下会取数组中所有记录该字段的最大值作为实际值。

    字段路径说明：
    - 'base.salary' → data['params']['base']['salary']
    - 'fdc_pinjaman.nilai_pendanaan' → data['params']['FDC']['pinjaman'][i]['nilai_pendanaan']
    - 'params.base.salary' → data['params']['base']['salary']（兼容完整路径）

    Args:
        data: 订单数据
        declared_field: 用户申报字段路径（如 'base.salary'）
        actual_field: 实际字段路径（如 'fdc_pinjaman.nilai_pendanaan'）
        method: 计算方法（ratio/abs_diff/year_diff/gap）

    Returns:
        差异度
    """
    # 字段路径前缀映射：简写 → 完整路径
    path_prefix_map = {
        'base.': 'params.base.',
        'fdc_pinjaman.': 'params.FDC.pinjaman.',
    }

    # 处理 declared_field
    declared_path = declared_field
    for short_prefix, full_prefix in path_prefix_map.items():
        if declared_path.startswith(short_prefix):
            # 避免重复前缀（如 params.params.base.salary）
            if not declared_path.startswith('params.'):
                declared_path = full_prefix + declared_path[len(short_prefix):]
            break
    declared = _get_nested(data, declared_path)

    # 特殊处理：FDC pinjaman 数组字段（如 fdc_pinjaman.nilai_pendanaan）
    # 实际数据在 data.params.FDC.pinjaman[].nilai_pendanaan
    actual = None
    if actual_field and actual_field.startswith('fdc_pinjaman.'):
        field_name = actual_field.split('.', 1)[1]
        pinjaman = data.get('params', {}).get('FDC', {}).get('pinjaman', [])
        values = []
        for loan in pinjaman:
            val = loan.get(field_name)
            if val is not None:
                try:
                    values.append(float(val))
                except (ValueError, TypeError):
                    pass
        if values:
            # 取最大值作为实际值（最保守估计）
            actual = max(values)
    else:
        actual = _get_nested(data, actual_field)

    if declared is None or actual is None:
        return 0.0

    try:
        declared = float(declared)
        actual = float(actual)
    except (ValueError, TypeError):
        return 0.0

    if method == 'ratio':
        if actual == 0:
            return 0.0
        return float(declared / actual)

    elif method == 'abs_diff':
        return float(abs(declared - actual))

    elif method == 'year_diff':
        # 计算年份差（用于年龄验证）
        try:
            if isinstance(declared, str):
                birth_date = datetime.strptime(declared, '%d-%m-%Y')
                declared_years = birth_date.year
            else:
                declared_years = declared
            return float(abs(declared_years - actual))
        except:
            return 0.0

    elif method == 'gap':
        # 绝对差距 / 申报值（归一化差率）
        return float(abs(declared - actual) / max(declared, 1))

    return 0.0


def _band_salary(value) -> str:
    """将薪资/贷款金额离散化为档位字符串（用于跨源比较，避免无效的逐字对比）

    Args:
        value: 数值金额（IDR）

    Returns:
        档位标记: 'very_low', 'low', 'medium', 'high', 'very_high', 'unknown'
    """
    try:
        v = float(value)
        if v <= 0:
            return 'unknown'
        # 印尼最低月薪约300万IDR，以此为标准
        if v < 3_000_000:
            return 'very_low'
        elif v < 5_000_000:
            return 'low'
        elif v < 10_000_000:
            return 'medium'
        elif v < 20_000_000:
            return 'high'
        else:
            return 'very_high'
    except (ValueError, TypeError):
        return 'unknown'


def calc_cross_discrepancy(data: Dict, field_pairs: List[Dict]) -> float:
    """
    DSL: mismatch_count(field_pairs)
    计算多数据源之间同一语义字段的不一致数

    field_pairs 格式支持两种:
    1. 旧格式: [{"source_a": "params.base.job", "source_b": "params.base.marita"}]
    2. 新格式: [{"src": "base", "field": "job"}, {"src": "fdc_pinjaman", "field": "tipe_pinjaman"}]

    **语义一致性校验**: 对于数值型字段（如salary vs nilai_pendanaan），
    会自动离散化为档位后比较，避免"数字 vs 文字"的无意义比较。

    Args:
        data: 订单数据
        field_pairs: 字段对列表

    Returns:
        不一致的数量
    """
    mismatch_count = 0
    prev_val = None
    has_prev = False

    for pair in field_pairs:
        src = pair.get('src', '')
        field = pair.get('field', '')
        source_a = pair.get('source_a', '')
        source_b = pair.get('source_b', '')

        # 旧格式：直接对比两个路径
        if source_a and source_b:
            val_a = _get_nested(data, source_a)
            val_b = _get_nested(data, source_b)
            if val_a is not None and val_b is not None and str(val_a) != str(val_b):
                mismatch_count += 1
            continue

        # 新格式：从src+field提取值
        val = None
        if src == 'base':
            val = _get_nested(data, f'params.base.{field}')
        elif src == 'fdc_pinjaman':
            pinjaman = data.get('params', {}).get('FDC', {}).get('pinjaman', [])
            if field == 'nilai_pendanaan' and pinjaman:
                # 从所有贷款记录中取最大 nilai_pendanaan
                amounts = [r.get('nilai_pendanaan', 0) for r in pinjaman if r.get('nilai_pendanaan')]
                val = max(amounts) if amounts else None
            else:
                val = pinjaman[0].get(field) if pinjaman else None
        elif src in ('fdc_inquiry', 'fdc'):
            inquiries = data.get('params', {}).get('FDC', {}).get('history_inquiry', {})
            val = inquiries.get(field)
        elif src == 'applist':
            applist = data.get('params', {}).get('appList', [])
            val = applist[0].get(field) if applist else None

        if val is None:
            continue

        # ====== 语义智能比较 ======
        # 对于数值型金额字段（salary vs nilai_pendanaan），先离散化为档位再比较
        # 避免直接比较数字和文本导致的无意义不匹配
        curr_val = str(val)

        # 检测是否为金额相关的数值比较
        if field in ('salary', 'nilai_pendanaan'):
            curr_val = _band_salary(val)

        # 将第一个值作为基线，后续值与基线对比
        if not has_prev:
            prev_val = curr_val
            has_prev = True
        elif curr_val != prev_val:
            mismatch_count += 1
            prev_val = curr_val

    return float(mismatch_count)


def calc_identity_cluster(data: Dict, identity_field: str,
                          shared_field: str,
                          cluster_lookup: Optional[Dict[str, Dict]] = None) -> float:
    """
    DSL: shared_value_count(identity_field, other_field)
    计算同一身份字段关联的共享字段聚集数（>1=疑似聚集信号）

    支持三种模式：
    1. 跨样本查表：传入预聚合的 cluster_lookup
    2. FDC贷款记录：按 identity_field/shared_field 名称从 pinjaman 数组提取
    3. 单样本降级：返回1.0（无法跨样本检测）

    Args:
        data: 订单数据
        identity_field: 身份/分类字段名（如 id_penyelenggara, tipe_pinjaman）
        shared_field: 共享/关联字段名（如 packageX）
        cluster_lookup: 跨样本预聚合查表 {identity_value: {shared_field: count}}

    Returns:
        关联数（>1=疑似聚集信号）
    """
    # 模式1：跨样本查表
    if cluster_lookup:
        identity_value = _get_nested(data, f'params.base.{identity_field}')
        if not identity_value:
            identity_value = data.get('params', {}).get(identity_field)
        if identity_value and str(identity_value) in cluster_lookup:
            return float(cluster_lookup[str(identity_value)].get(shared_field, 1))
        return 1.0

    # 模式2：从FDC pinjaman记录提取
    fdc = data.get('params', {}).get('FDC', {})
    loans = fdc.get('pinjaman', [])
    if loans:
        id_set = set()
        shared_set = set()
        for loan in loans:
            id_val = loan.get(identity_field)
            shared_val = loan.get(shared_field)
            if id_val:
                id_set.add(str(id_val))
            if shared_val:
                shared_set.add(str(shared_val))
        cluster_size = max(len(id_set), len(shared_set))
        return float(cluster_size) if cluster_size > 1 else 1.0

    return 1.0




# [晋升自通道2] T016 - event_velocity
# 晋升时间: 2026-06-02T13:29:30.916331
def calc_event_velocity(data: Dict, apply_time_dt: datetime,
                            window_days: int = 30,
                            event_filter: str = 'all',
                            source: str = 'fdc_pinjaman') -> float:
    """计算指定窗口内的事件发生速率（次/天）

    DSL: count(field_set, window) / window_days

    Args:
        data: 订单数据
        apply_time_dt: 申请时间（防穿越基准）
        window_days: 回溯窗口天数
        event_filter: 事件类型过滤条件
        source: 数据源标识

    Returns:
        事件速率 (float)
    """
    from channel1_calculators import _filter_by_time
    
    # 严格防穿越：仅提取 apply_time_dt 之前且落在窗口内的事件
    events = _filter_by_time(data, source, apply_time_dt, window_days)
    if not isinstance(events, list):
        return 0.0
        
    filtered = [e for e in events if event_filter == 'all' or e.get('type') == event_filter]
    count = len(filtered)
    return float(count / window_days) if window_days > 0 else 0.0


# [晋升自通道2] T018 - event_interval_cv
# 晋升时间: 2026-06-02T13:29:45.299342
def calc_event_interval_cv(data: Dict, apply_time_dt: datetime,
                               window_days: int = 60,
                               min_events: int = 3,
                               source: str = 'fdc_pinjaman') -> float:
    """计算连续事件时间间隔的变异系数（CV）

    DSL: std(intervals) / mean(intervals)

    Args:
        data: 订单数据
        apply_time_dt: 申请时间（防穿越基准）
        window_days: 回溯窗口天数
        min_events: 计算所需的最小事件数
        source: 数据源标识

    Returns:
        间隔变异系数 (float)，事件不足返回0.0
    """
    from channel1_calculators import _filter_by_time
    import statistics
    
    events = _filter_by_time(data, source, apply_time_dt, window_days)
    if not isinstance(events, list) or len(events) < min_events:
        return 0.0
        
    # 提取并排序时间戳，严格防穿越
    times = sorted([
        e.get('timestamp') or e.get('event_time') 
        for e in events 
        if (e.get('timestamp') or e.get('event_time')) and (e.get('timestamp') or e.get('event_time')) <= apply_time_dt
    ])
    
    if len(times) < 2:
        return 0.0
        
    # 计算相邻间隔（转换为天）
    intervals = [(times[i+1] - times[i]).total_seconds() / 86400.0 for i in range(len(times)-1)]
    if len(intervals) < 2:
        return 0.0
        
    mean_val = statistics.mean(intervals)
    if mean_val <= 0:
        return 0.0
        
    std_val = statistics.stdev(intervals)
    return float(std_val / mean_val)


# [晋升自通道2] T019 - recency_days
# 晋升时间: 2026-06-02T15:48:25.017666
from datetime import datetime
from typing import Dict

# 辅助函数需从 channel1_calculators 导入
# from channel1_calculators import _filter_by_time, _get_event_time

def calc_recency_days(data: Dict, apply_time_dt: datetime,
                      window_days: int = 90,
                      time_field: str = 'event_time',
                      default_value: int = 180,
                      source: str = 'fdc_inquiry') -> float:
    """计算窗口内最近一次事件距今的天数（Recency）

    DSL: apply_time_dt - max(time_field, window)

    Args:
        data: 订单数据字典
        apply_time_dt: 申请时间（防穿越基准）
        window_days: 回溯窗口天数
        time_field: 事件时间字段名
        default_value: 无事件时的默认返回值
        source: 数据源标识

    Returns:
        距今天数 (float)，最小为0.0
    """
    # 1. 按窗口过滤数据（自动处理 apply_time_dt 防穿越）
    events = _filter_by_time(data, source, apply_time_dt, window_days)
    if not events or not isinstance(events, list):
        return float(default_value)

    # 2. 提取有效时间戳并严格防穿越（仅保留 <= apply_time_dt 的记录）
    valid_times = []
    for evt in events:
        evt_time = _get_event_time(evt, time_field)
        if evt_time and evt_time <= apply_time_dt:
            valid_times.append(evt_time)

    if not valid_times:
        return float(default_value)

    # 3. 计算最近时间与申请时间的差值
    latest_time = max(valid_times)
    delta_seconds = (apply_time_dt - latest_time).total_seconds()
    delta_days = delta_seconds / 86400.0

    return max(0.0, delta_days)


# [晋升自模板库] T019 - value_stats
# 晋升时间: 2026-06-11T02:55:56.208318
from channel1_calculators import _filter_by_time
from typing import Dict, Optional
import math

def calc_value_stats(data: Dict, apply_time_dt: datetime, source: str = 'fdc_pinjaman',
                     window_days: int = 90, value_field: str = 'amount', method: str = 'mean',
                     cond: Optional[str] = None, min_count: int = 1) -> float:
    """对窗口内数值字段进行基础聚合统计

    DSL: value_stats(source, window, value_field, method, cond?, min_count)

    Args:
        data: 订单数据字典
        apply_time_dt: 申请时间基准点
        source: 数据源标识
        window_days: 回溯窗口天数
        value_field: 目标数值字段名
        method: 统计方法
        cond: 过滤条件
        min_count: 最小有效样本数

    Returns:
        统计结果浮点数，样本不足时返回0.0
    """
    items = _filter_by_time(data, source, apply_time_dt, window_days)
    if not isinstance(items, list):
        return 0.0

    values = []
    for item in items:
        if cond and not _eval_cond(item, cond):
            continue
        val = item.get(value_field)
        if val is not None:
            try:
                values.append(float(val))
            except (ValueError, TypeError):
                continue

    if len(values) < min_count:
        return 0.0

    if method == 'sum':
        return round(sum(values), 2)
    elif method == 'mean':
        return round(sum(values) / len(values), 2)
    elif method == 'max':
        return round(max(values), 2)
    elif method == 'min':
        return round(min(values), 2)
    elif method == 'std':
        mean_val = sum(values) / len(values)
        variance = sum((x - mean_val) ** 2 for x in values) / len(values)
        return round(math.sqrt(variance), 2)
    return 0.0


# [晋升自模板库] T023 - event_gap
# 晋升时间: 2026-06-11T02:57:51.822671
from channel1_calculators import _filter_by_time, _get_event_time

def calc_event_gap(data: Dict, apply_time_dt: datetime, window_days: int = 30,
                   source: str = 'fdc_inquiry', method: str = 'avg',
                   cond: str = None) -> float:
    """计算指定窗口内连续事件的时间间隔统计值

    DSL: event_gap(source, window, method, cond?)

    Args:
        data: 订单数据字典
        apply_time_dt: 申请时间（防穿越基准）
        window_days: 回溯窗口天数
        source: 数据源标识
        method: 聚合方法 (min, avg, max, std, median)
        cond: 可选过滤条件

    Returns:
        间隔统计值 (单位: 天)
    """
    raw_items = data.get(source, [])
    if not isinstance(raw_items, list) or len(raw_items) < 2:
        return 0.0

    # 防穿越机制：严格基于 apply_time_dt 截断
    filtered_items = _filter_by_time(raw_items, apply_time_dt, window_days)
    if len(filtered_items) < 2:
        return 0.0

    # 提取时间戳并排序
    timestamps = sorted([_get_event_time(item) for item in filtered_items])
    if not timestamps:
        return 0.0

    # 计算相邻间隔（转换为天）
    gaps = [(timestamps[i] - timestamps[i-1]).total_seconds() / 86400.0 for i in range(1, len(timestamps))]
    if not gaps:
        return 0.0

    # 聚合计算
    if method == 'min':
        return float(min(gaps))
    elif method == 'max':
        return float(max(gaps))
    elif method == 'avg':
        return float(sum(gaps) / len(gaps))
    elif method == 'std':
        mean_val = sum(gaps) / len(gaps)
        variance = sum((x - mean_val) ** 2 for x in gaps) / len(gaps)
        return float(variance ** 0.5)
    elif method == 'median':
        sorted_gaps = sorted(gaps)
        n = len(sorted_gaps)
        mid = n // 2
        return float(sorted_gaps[mid] if n % 2 != 0 else (sorted_gaps[mid-1] + sorted_gaps[mid]) / 2)
    return 0.0


# [晋升自模板库] T021 - recency_score
# 晋升时间: 2026-06-11T07:08:08.200215
from datetime import datetime, timedelta
from typing import Dict, Optional
import math

def calc_recency_score(data: Dict, apply_time_dt: datetime, source: str = 'applist',
                       window_days: int = 30, weight_field: Optional[str] = None,
                       decay_type: str = 'exponential', half_life_days: float = 7.0) -> float:
    """基于最近事件时间的近因衰减评分计算

    DSL: recency_score(source, window, weight_field?, decay_type)

    Args:
        data: 订单数据字典
        apply_time_dt: 申请时间（防穿越基准）
        source: 数据源标识（applist/fdc_pinjaman）
        window_days: 回溯窗口天数
        weight_field: 事件权重字段名，默认1.0
        decay_type: 衰减类型 ('exponential', 'linear', 'step')
        half_life_days: 半衰期/阈值天数

    Returns:
        评分 (0.0-1.0)
    """
    valid_events = _filter_by_time(data, source, apply_time_dt, window_days)
    if not valid_events:
        return 0.0

    event_times = [t for t in (_get_event_time(e) for e in valid_events) if t]
    if not event_times:
        return 0.0

    latest_time = max(event_times)
    days_since = (apply_time_dt - latest_time).total_seconds() / 86400.0
    days_since = max(0.0, days_since)

    # 衰减计算
    if decay_type == 'exponential':
        score = math.exp(-math.log(2) * days_since / half_life_days)
    elif decay_type == 'linear':
        score = max(0.0, 1.0 - days_since / window_days)
    elif decay_type == 'step':
        score = 1.0 if days_since <= half_life_days else 0.0
    else:
        score = 0.0

    # 权重调整
    if weight_field:
        latest_event = max(valid_events, key=lambda e: _get_event_time(e) or datetime.min)
        try:
            weight = float(latest_event.get(weight_field, 1.0))
            score = min(1.0, score * math.log1p(max(weight, 0.0)))
        except (TypeError, ValueError):
            pass

    return round(float(score), 4)


# [晋升自模板库] T022 - frequency_rate
# 晋升时间: 2026-06-11T07:30:21.510945
from datetime import datetime
from typing import Dict, Optional
from channel1_calculators import _filter_by_time

def calc_frequency_rate(data: Dict, apply_time_dt: datetime, window_days: int = 30,
                        cond: Optional[Dict] = None, normalize_unit: str = "day",
                        source: str = "fdc_inquiry") -> float:
    """计算指定窗口内的事件发生频率（归一化）

    DSL: frequency_rate(source, window, cond?, normalize_unit)

    Args:
        data: 订单数据字典
        apply_time_dt: 申请时间（防穿越基准）
        window_days: 回溯窗口天数
        cond: 事件过滤条件字典
        normalize_unit: 归一化单位 (day/week/month)
        source: 数据源标识

    Returns:
        频率值 (float)
    """
    # 防穿越：严格基于 apply_time_dt 截取历史窗口数据
    items = _filter_by_time(data, source, apply_time_dt, window_days)
    if not items:
        return 0.0

    # 应用业务条件过滤
    if cond:
        items = [item for item in items if all(item.get(k) == v for k, v in cond.items())]

    count = len(items)
    if count == 0:
        return 0.0

    # 单位换算系数映射
    unit_divisors = {"day": 1.0, "week": 7.0, "month": 30.0}
    divisor = unit_divisors.get(normalize_unit, 1.0)
    
    # 频率 = 事件数 / (窗口天数 / 单位换算系数)
    return count / (window_days / divisor)

# ============================================================
# 函数映射表
# ============================================================

FUNCTION_MAP = {
    'calc_frequency_rate': calc_frequency_rate,

    'calc_recency_score': calc_recency_score,

    'calc_event_gap': calc_event_gap,

    'calc_value_stats': calc_value_stats,

    'calc_recency_days': calc_recency_days,

    'calc_event_interval_cv': calc_event_interval_cv,

    'calc_event_velocity': calc_event_velocity,

    'calc_count': calc_count,
    'calc_distinct_count': calc_distinct_count,
    'calc_decayed_sum': calc_decayed_sum,
    'calc_proportion': calc_proportion,
    'calc_proportion_by_category': calc_proportion_by_category,
    'calc_concentration': calc_concentration,
    'calc_concentration_by_category': calc_concentration_by_category,
    'calc_overlap': calc_overlap,
    'calc_period_compare': calc_period_compare,
    'calc_trend': calc_trend,
    'calc_spike': calc_spike,
    'calc_percentile': calc_percentile,
    'calc_deviation': calc_deviation,
    'calc_anomaly': calc_anomaly,
    'calc_declared_vs_actual': calc_declared_vs_actual,
    'calc_cross_discrepancy': calc_cross_discrepancy,
    'calc_identity_cluster': calc_identity_cluster,
}


def get_function(name: str):
    """通过名称获取计算函数"""
    return FUNCTION_MAP.get(name)
