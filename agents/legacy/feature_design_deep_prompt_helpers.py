"""
特征设计Prompt辅助方法 - 用于动态格式化年龄段描述
"""

def format_age_risk_dynamic(age_bins: list) -> str:
    """
    动态格式化年龄风险分布

    Args:
        age_bins: [{'bin': '36-40', 'overdue_rate': 0.6667}, ...]

    Returns:
        描述文本
    """
    if not age_bins:
        return "年龄风险数据暂缺"

    # 找出高风险和低风险年龄段
    high_risk_bins = [b for b in age_bins if b.get('overdue_rate', 0) > 0.5]
    low_risk_bins = [b for b in age_bins if 0 < b.get('overdue_rate', 0) < 0.3]

    desc_parts = []

    if high_risk_bins:
        high_desc = ", ".join([f"{b['bin']}({b['overdue_rate']*100:.1f}%)" for b in high_risk_bins])
        desc_parts.append(f"高风险年龄段: {high_desc}")

    if low_risk_bins:
        low_desc = ", ".join([f"{b['bin']}({b['overdue_rate']*100:.1f}%)" for b in low_risk_bins])
        desc_parts.append(f"低风险年龄段: {low_desc}")

    return "；".join(desc_parts) if desc_parts else "年龄与风险相关性不明显"


def extract_risk_patterns(risk_rules: list) -> list:
    """
    从数据分析结果中提取风险模式

    Args:
        risk_rules: [{'rule': '...', 'description': '...', 'risk_level': '...'}, ...]

    Returns:
        风险模式描述列表
    """
    patterns = []
    for rule in risk_rules:
        patterns.append({
            'rule': rule.get('rule', ''),
            'description': rule.get('description', ''),
            'level': rule.get('risk_level', 'medium')
        })
    return patterns


def build_risk_context_prompt(knowledge_base) -> str:
    """
    构建纯业务逻辑的风险上下文（不依赖具体数据值）

    这个Prompt关注**印尼现金贷的业务逻辑**，而非当前数据的快照
    """

    return """# 印尼现金贷风控的业务逻辑（通用知识，不随数据变化）

## 核心风险模式

### 1. 多头借贷（Co-lending Risk）

**业务逻辑**:
- 客户在多个平台同时借款 = 资金极度紧张
- 拆东墙补西墙 = 最终必然违约
- 这是印尼现金贷**最主要**的风险来源

**可观测信号**:
- FDC查询频率短期内激增（3天内>5次，7天内>10次）
- 活跃贷款平台数>3个
- 在贷余额/月收入比值>5

**对应特征方向**:
- FDC查询频率类（时间窗口化）
- 活跃平台数统计
- 查询vs贷款的时滞分析

---

### 2. 高风险偏好（High Risk Appetite）

**业务逻辑**:
- 安装赌博APP/克隆应用/虚拟定位 = 投机倾向
- 这类用户通常风险意识差，对利率不敏感
- 一旦资金断裂，还款优先级最低

**可观测信号**:
- 安装2个以上高风险APP（赌博、现金贷、克隆应用）
- 高风险APP占比>10%
- 近期新增高风险APP安装

**对应特征方向**:
- 高风险APP安装数量
- 高风险APP占比
- 高风险新增趋势

---

### 3. 收入不稳定（Income Instability）

**业务逻辑**:
- 低收入/无固定工作/年轻人群 = 收入波动大
- 一旦失业或减薪，立即违约
- 这部分客户对经济周期高度敏感

**可观测信号**:
- 薪资低于行业平均水平
- 工作年限<1年或无工作
- 年龄<25岁（刚工作，稳定性差）

**对应特征方向**:
- 收入水平分层
- 职业类型分类
- 年龄×收入交叉

---

### 4. 信用历史恶化（Credit Deterioration）

**业务逻辑**:
- 历史有逾期记录 = 还款意愿/能力有问题
- 逾期天数越长，再次逾期的概率越高
- DPD>90天基本等于坏账

**可观测信号**:
- 最大DPD>30天
- 历史逾期比例>20%
- 最近6个月有新增逾期

**对应特征方向**:
- 历史逾期严重度统计
- 逾期时间窗口分布
- 逾期vs还款比例

---

### 5. 数字足迹单一（Digital Footprint Narrow）

**业务逻辑**:
- 只安装借贷类APP，没有生活/社交/工作应用
- 可能是新户、白户或欺诈用户
- 缺乏交叉验证的数据维度

**可观测信号**:
- APP安装总数<10个
- 借贷/金融类APP占比>50%
- 缺少社交/工作/生活类应用

**对应特征方向**:
- APP安装多样性指数
- 金融类APP集中度
- 应用类别熵值

---

## 特征设计框架

基于以上5大风险模式，设计特征时应：

1. **覆盖所有模式**: 每个风险模式对应一类特征
2. **量化可观测信号**: 将业务逻辑转化为可计算的指标
3. **多时间窗口**: 短期（3-7天）、中期（30天）、长期（90天+）
4. **交叉验证**: Base×FDC、Base×Applist、FDC×Applist
5. **系统化生成**: 模板化+参数组合，不是拍脑袋

"""
