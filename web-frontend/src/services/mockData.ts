import type { Project, ProjectListResponse, ProjectTemplate } from '@/types/project';
import type { Task, TaskListResponse, TaskResultResponse } from '@/types/task';
import type { FeatureMetric, FeatureVersion, TopFeature } from '@/types/feature';
import type { Channel1Template, PendingTemplateItem } from '@/services/api';

export const demoProjects: Project[] = [
  {
    id: 1,
    name: '印尼现金贷首贷特征生产',
    business_line: '短期现金贷',
    country: 'INDO',
    product: 'FlexRupiah / TemanPinjam',
    description: '围绕首贷客户的 APP、FDC、基础画像进行风险特征挖掘。',
    config: { customer_scope: 'first_loan', iv_threshold: 0.02, psi_threshold: 0.25 },
    status: 'active',
    is_default: true,
    created_at: '2026-06-10T10:00:00',
    updated_at: '2026-06-12T09:30:00',
  },
  {
    id: 2,
    name: '印尼复贷稳定性观察',
    business_line: '短期现金贷',
    country: 'INDO',
    product: 'Repeat Loan',
    description: '用于沉淀复贷客群稳定性和漂移观察口径。',
    config: { customer_scope: 'repeat_loan' },
    status: 'active',
    is_default: false,
    created_at: '2026-06-11T11:00:00',
    updated_at: '2026-06-11T11:00:00',
  },
];

export const demoTemplates: Channel1Template[] = [
  { template_id: 'T001', template_name: 'category_count', template_name_cn: '分类计数', dimension: '计数统计', description: '按指定分类字段统计记录数量。', dsl: 'count(entity.category)', python_function: 'category_count' },
  { template_id: 'T002', template_name: 'category_ratio', template_name_cn: '分类占比', dimension: '比例计算', description: '计算指定分类数量在总体数量中的占比。', dsl: 'ratio(count(category), count(total))', python_function: 'category_ratio' },
  { template_id: 'T006', template_name: 'window_count', template_name_cn: '时间窗口计数', dimension: '时间窗口', description: '在指定时间窗口内统计事件次数。', dsl: 'count(event, window)', python_function: 'window_count' },
  { template_id: 'T010', template_name: 'distribution_distance', template_name_cn: '分布距离', dimension: '分布比较', description: '计算当前样本值与参考分布之间的距离。', dsl: 'distance(value, reference)', python_function: 'distribution_distance' },
  { template_id: 'T016', template_name: 'derived_arithmetic', template_name_cn: '衍生算术', dimension: '算术衍生', description: '对已有指标进行差值、比值、求和等衍生加工。', dsl: 'derive(a,b,op)', python_function: '' },
];

export const demoPendingTemplates: PendingTemplateItem[] = [
  {
    template_id: 'T017',
    template_name: 'conditional_combo_flag',
    template_name_cn: '条件组合标记',
    dimension: '条件组合',
    description: '当多个输入条件同时满足时输出二值标记。',
    dsl: 'if condition_a and condition_b then 1 else 0',
    python_function: 'conditional_combo_flag',
  },
  {
    template_id: 'T018',
    template_name: 'weighted_score',
    template_name_cn: '加权评分',
    dimension: '加权评分',
    description: '对多个数值输入按配置权重进行加权汇总。',
    dsl: 'sum(value_i * weight_i)',
    python_function: 'weighted_score',
  },
];

export const demoTasks: Task[] = [
  {
    id: 108,
    name: '印尼首贷6月批量特征生产',
    mode: 'normal',
    status: 'completed',
    progress: 100,
    project_id: 1,
    total_features: 267,
    passed_features: 147,
    deployed_version: 'v14',
    created_at: '2026-06-12T09:00:00',
    started_at: '2026-06-12T09:01:00',
    completed_at: '2026-06-12T09:38:00',
  },
  {
    id: 107,
    name: 'GPS防欺诈模板生成评审',
    mode: 'template_task',
    status: 'completed',
    progress: 100,
    project_id: 1,
    linked_task_id: 108,
    created_at: '2026-06-11T17:20:00',
    completed_at: '2026-06-11T17:36:00',
  },
  {
    id: 106,
    name: '5月首贷样本复盘',
    mode: 'normal',
    status: 'failed',
    progress: 70,
    project_id: 1,
    total_features: 251,
    passed_features: 119,
    error_message: '样本标签缺失率超过业务确认阈值',
    created_at: '2026-06-10T14:10:00',
  },
];

export const demoFeatureVersions: FeatureVersion[] = [
  { id: 14, version: 'v14', task_id: 108, total_features: 267, passed_features: 147, created_at: '2026-06-12T09:38:00' },
  { id: 13, version: 'v13', task_id: 104, total_features: 251, passed_features: 132, created_at: '2026-06-11T16:45:00' },
  { id: 12, version: 'v12', task_id: 99, total_features: 231, passed_features: 98, created_at: '2026-06-10T18:20:00' },
];

export const demoFeatureMetrics: FeatureMetric[] = [
  {
    id: 1,
    version: 'v14',
    task_id: 108,
    feature_name: 'ratio_applist_highrisk_apps_all',
    template_type: '比例计算',
    source_fields: ['appList.packageName', 'app_category_cache'],
    feature_logic: '高风险APP数量 / 用户申请时点前可识别APP总数；高风险类别包含 gambling、cash_loan、fake_gps、clone_app。',
    iv: 0.0821,
    psi: 0.083,
    coverage: 0.942,
    is_passed: true,
  },
  {
    id: 2,
    version: 'v14',
    task_id: 108,
    feature_name: 'cnt_fdc_query_7d_platforms',
    template_type: '时间窗口计数',
    source_fields: ['FDC.history_inquiry.7_hari'],
    feature_logic: '统计申请时间前7天内发生FDC查询的平台去重数量，用于识别短期多头查询强度。',
    iv: 0.0614,
    psi: 0.119,
    coverage: 0.718,
    is_passed: true,
  },
  {
    id: 3,
    version: 'v14',
    task_id: 108,
    feature_name: 'flag_app_cashloan_recent_install',
    template_type: '条件组合标记',
    source_fields: ['appList.inTime', 'app_category_cache'],
    feature_logic: '若申请时间前30天内新安装现金贷或金融借贷类APP，则记为1，否则记为0。',
    iv: 0.0452,
    psi: 0.148,
    coverage: 0.404,
    is_passed: true,
  },
  {
    id: 4,
    version: 'v14',
    task_id: 108,
    feature_name: 'cross_age_marital_gambling',
    template_type: '条件组合',
    source_fields: ['base.birthday', 'base.marita', 'app_category_cache'],
    feature_logic: '年龄段、婚姻状态与赌博类APP安装标记交叉组合，输出组合风险分桶编号。',
    iv: 0.0377,
    psi: 0.091,
    coverage: 0.227,
    is_passed: true,
  },
  {
    id: 5,
    version: 'v14',
    task_id: 108,
    feature_name: 'ratio_bank_app_to_loan_app',
    template_type: '比例计算',
    source_fields: ['app_category_cache'],
    feature_logic: '银行类APP数量 / 借贷类APP数量；当借贷类APP数量为0时按安全缺省值处理。',
    iv: 0.0298,
    psi: 0.206,
    coverage: 0.612,
    is_passed: true,
  },
  {
    id: 6,
    version: 'v14',
    task_id: 108,
    feature_name: 'cnt_unknown_apps_30d',
    template_type: '时间窗口计数',
    source_fields: ['appList.inTime', 'app_category_cache'],
    feature_logic: '统计申请时间前30天内安装且未能归类的APP数量，用于观察新包名和长尾应用噪声。',
    iv: 0.0181,
    psi: 0.122,
    coverage: 0.931,
    is_passed: false,
  },
  {
    id: 7,
    version: 'v14',
    task_id: 108,
    feature_name: 'fdc_active_platform_shift',
    template_type: '分布比较',
    source_fields: ['FDC.platform_aktif', 'reference_distributions'],
    feature_logic: '比较当前活跃平台数量与训练样本参考分布的偏离程度，偏离越高代表稳定性越弱。',
    iv: 0.0262,
    psi: 0.312,
    coverage: 0.669,
    is_passed: false,
  },
  {
    id: 8,
    version: 'v14',
    task_id: 108,
    feature_name: 'low_coverage_installment_signal',
    template_type: '条件组合标记',
    source_fields: ['app_category_cache'],
    feature_logic: '识别分期消费类APP安装信号；当前样本覆盖率不足，暂不进入推荐交付。',
    iv: 0.0418,
    psi: 0.077,
    coverage: 0.031,
    is_passed: false,
  },
];

export const demoProjectTemplates: ProjectTemplate[] = demoTemplates.map((template, index) => ({
  id: index + 1,
  project_id: 1,
  template_db_id: index + 1,
  template_id: template.template_id,
  template_name: template.template_name || '',
  template_name_cn: template.template_name_cn,
  dimension: template.dimension,
  enabled: true,
  selected_at: '2026-06-12T09:00:00',
}));

export const demoTaskResult: TaskResultResponse = {
  task: demoTasks[0],
  logs: [
    { id: 1, task_id: 108, level: 'info', message: '开始数据准备', timestamp: '2026-06-12T09:01:00' },
    { id: 2, task_id: 108, level: 'info', message: '批量特征生产完成，共267个候选特征', timestamp: '2026-06-12T09:12:00' },
    { id: 3, task_id: 108, level: 'info', message: '评估完成，通过147个特征', timestamp: '2026-06-12T09:32:00' },
  ],
  result: { passed_features: demoFeatureMetrics.filter((item) => item.is_passed), failed_features: demoFeatureMetrics.filter((item) => !item.is_passed) },
};

export const demoTopFeatures: TopFeature[] = demoFeatureMetrics
  .filter((item) => item.is_passed)
  .map((item) => ({ feature_name: item.feature_name, iv: item.iv, psi: item.psi, coverage: item.coverage, version: item.version }));

export const demoProjectListResponse: ProjectListResponse = {
  items: demoProjects,
  total: demoProjects.length,
};

export const demoTaskListResponse: TaskListResponse = {
  items: demoTasks,
  total: demoTasks.length,
};
