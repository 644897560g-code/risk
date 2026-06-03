/* Feature Design Framework constants
 *
 * These describe the static architecture of the feature generation system —
 * the 16 DSL templates, their business meanings, and the risk-driven design
 * philosophy. The descriptions are derived from feature_mass_producer.py
 * and are stable across tasks (only change when the system architecture evolves).
 *
 * Source references:
 *   - agents/feature_mass_producer.py: _build_param_combos() and PARAM_COMBOS
 *   - outputs/feature_templates/channel1_templates.json: 16 template definitions
 *
 * param_combo_count values: base combos + extension combos from the mass producer.
 * Update these when _build_param_combos() changes.
 */

export interface TemplateDefinition {
  template_id: string;
  template_name: string;
  dimension: string;
  description: string;
  param_combo_count: number;
  business_meaning: string;
}

export const FRAMEWORK_DESCRIPTION =
  '本系统的特征体系基于"三阶段风险驱动"方法论设计，从 ' +
  'APP安装行为、FDC征信记录、借贷历史 三个数据维度出发，' +
  '覆盖多头借贷、高风险偏好、收入不稳定、欺诈风险、共债风险 ' +
  '五大核心风险模式。' +
  '系统通过 16 个确定性 DSL 模板对原始数据进行结构化特征提取，' +
  '每个模板定义了一种数学计算模式（如计数、去重计数、衰减求和、占比、集中度等），' +
  '并配合多组时间窗口、条件筛选和衍生变换参数，' +
  '最终枚举生成 542 个特征（418 个主特征 + 124 个衍生特征），' +
  '形成完整的风控特征矩阵。';

export const TEMPLATE_DEFINITIONS: TemplateDefinition[] = [
  {
    template_id: 'T001',
    template_name: 'count',
    dimension: 'APP安装行为, FDC征信记录, 借贷历史',
    description: '按时间窗口统计事件数量（FDC查询次数、APP安装数、贷款笔数）',
    param_combo_count: 97,
    business_meaning: '衡量客户近期活跃程度和申请频率，捕捉多头借贷信号',
  },
  {
    template_id: 'T002',
    template_name: 'distinct_count',
    dimension: 'FDC征信记录, 借贷历史',
    description: '去重统计活跃机构数、查询方数、贷款类型数',
    param_combo_count: 29,
    business_meaning: '识别客户同时在多少家机构有借贷记录，多头借贷核心指标',
  },
  {
    template_id: 'T003',
    template_name: 'decayed_sum',
    dimension: '借贷历史',
    description: '带时间衰减的资金流、在贷余额、收入时间序列聚合',
    param_combo_count: 48,
    business_meaning: '近因效应：近期行为比远期行为权重更高，反映最新风险趋势',
  },
  {
    template_id: 'T004',
    template_name: 'proportion',
    dimension: 'APP安装行为, 借贷历史',
    description: '高风险APP安装占比、特定贷款类型（伊斯兰/非伊斯兰）占比',
    param_combo_count: 107,
    business_meaning: '衡量客户风险偏好：高风险APP比例高 → 违约倾向上升',
  },
  {
    template_id: 'T005',
    template_name: 'concentration',
    dimension: 'APP安装行为, 借贷历史',
    description: '贷款机构/应用类别的集中度（基尼系数、熵、CV变异系数、HHI指数）',
    param_combo_count: 44,
    business_meaning: '集中度越低（多头分散）→ 共债风险越高',
  },
  {
    template_id: 'T006',
    template_name: 'overlap',
    dimension: 'APP安装行为, FDC征信记录',
    description: '已安装APP列表与FDC借贷机构的重叠程度（共现率）',
    param_combo_count: 4,
    business_meaning: '重叠度高 → 多头借贷特征明显；重叠度低 → 使用非正规渠道借款',
  },
  {
    template_id: 'T007',
    template_name: 'period_compare',
    dimension: 'APP安装行为, FDC征信记录, 借贷历史',
    description: '短期vs长期行为对比（近7天vs近90天、近30天vs近180天等）',
    param_combo_count: 24,
    business_meaning: '新增借款/查询行为激增 → 近期资金链紧张信号',
  },
  {
    template_id: 'T008',
    template_name: 'trend',
    dimension: 'APP安装行为, FDC征信记录, 借贷历史',
    description: '多窗口事件量的线性趋势斜率（近7天→15天→30天→60天）',
    param_combo_count: 14,
    business_meaning: '斜率为正且持续增大 → 风险正在累积上升',
  },
  {
    template_id: 'T009',
    template_name: 'spike',
    dimension: 'APP安装行为, 借贷历史',
    description: '近期事件量突增检测（近7天vs更长期窗口的倍数阈值）',
    param_combo_count: 24,
    business_meaning: '短期内事件量突增至数倍 → 突发性资金需求（风险急升信号）',
  },
  {
    template_id: 'T010',
    template_name: 'percentile',
    dimension: '全局分布',
    description: '用户薪资/贷款额/查询数在全体样本中的百分位排名',
    param_combo_count: 4,
    business_meaning: '处于群体尾部（高百分位）→ 极端借贷行为，风险显著偏高',
  },
  {
    template_id: 'T011',
    template_name: 'deviation',
    dimension: '全局分布',
    description: '用户指标与同群体均值的偏离程度（Z-Score标准化偏差）',
    param_combo_count: 4,
    business_meaning: '偏离度大 → 用户行为模式异常，可能为欺诈或极端风险客户',
  },
  {
    template_id: 'T012',
    template_name: 'anomaly',
    dimension: 'APP安装行为, 借贷历史',
    description: '多维特征的马氏距离异常检测（综合多个维度的异常评分）',
    param_combo_count: 2,
    business_meaning: '综合异常得分高 → 存在多维度的行为模式偏离',
  },
  {
    template_id: 'T013',
    template_name: 'declared_vs_actual',
    dimension: '申报信息',
    description: '用户申报薪资与FDC实际收入/在贷金额的偏差比、绝对差值',
    param_combo_count: 6,
    business_meaning: '申报与实际情况偏差大 → 收入造假或隐瞒负债，强欺诈信号',
  },
  {
    template_id: 'T014',
    template_name: 'cross_discrepancy',
    dimension: '跨源对比',
    description: '申报薪资与FDC贷款额/征信数据的跨源不一致性评分',
    param_combo_count: 1,
    business_meaning: '多源数据不一致 → 信息真实性存疑，需要人工审核介入',
  },
  {
    template_id: 'T015',
    template_name: 'identity_cluster',
    dimension: 'APP安装行为, FDC征信记录',
    description: '设备共享APP安装/共贷机构的聚类分析（团伙欺诈识别）',
    param_combo_count: 2,
    business_meaning: '与已知欺诈团伙共享APP/机构 → 团伙欺诈风险',
  },
  {
    template_id: 'T016',
    template_name: 'derived',
    dimension: '跨模板特征组合',
    description: '衍生特征：比值/密度/加权组合/对数/平方/差分/速度变化/高值标记',
    param_combo_count: 124,
    business_meaning: '对主特征进行数学变换，挖掘非线性关系和隐藏风险模式',
  },
];
