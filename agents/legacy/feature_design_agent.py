"""
特征设计Agent - 基于业务知识和FDC变量清单设计新增特征（升级版：支持12类别框架）

职责：
1. 加载业务知识库JSON
2. 加载FDC4710变量清单
3. 基于3步Chain-of-Thought设计新特征：
   - Step 1: 印尼现金贷业务逻辑分析
   - Step 2: 12类别特征体系设计
   - Step 3: 特征模板生成（含few-shot）
4. 特征去重检查（不与现有4710个FDC特征重复）
5. 输出特征设计文档（JSON格式）

特征类型：
- 计数特征（Count）：应用安装数量、查询次数等
- 比例特征（Ratio）：各类应用占比、逾期比例等
- 极值特征（Max/Min）：最大逾期天数、最高额度等
- 时间间隔特征（Time Gap）：最近查询时间、应用更新时间等
- 交叉特征（Cross）：多数据源组合特征

升级说明：
- 支持12类别特征生命周期框架（pre-application → application → during loan → post-loan）
- 基于24个高质量模板系统化生成1000+特征
- 动态传入数据分析结果，不写死数字
"""

import json
import os
import sys
import re
from typing import List, Dict, Tuple
import pandas as pd

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.llm_client import LLMClient


class FeatureDesignAgent:
    """特征设计Agent"""

    def __init__(self):
        """初始化特征设计Agent"""
        self.knowledge_base = None
        self.fdc_variables = []
        self.fdc_variable_names = set()  # 用于快速去重检查
        self.llm_client = LLMClient()
        self.designed_features = []

    def load_knowledge_base(self, kb_path: str = 'outputs/knowledge_base/knowledge_base.json'):
        """加载业务知识库"""
        print(f"📖 加载业务知识库: {kb_path}")
        with open(kb_path, 'r', encoding='utf-8') as f:
            self.knowledge_base = json.load(f)
        print(f"   ✅ 知识库加载完成")

        # 打印摘要
        summary = self.knowledge_base.get('knowledge_base', {}).get('summary', {})
        print(f"   - 样本数: {summary.get('total_samples', 'N/A')}")
        print(f"   - 逾期率: {summary.get('overdue_rate', 'N/A')}")

    def load_fdc_variables(self, fdc_path: str = 'FDC4710变量.xlsx'):
        """加载FDC变量清单"""
        print(f"\n📊 加载FDC变量清单: {fdc_path}")
        df = pd.read_excel(fdc_path)
        self.fdc_variables = df['Feature Name'].tolist()
        self.fdc_variable_names = set(self.fdc_variables)
        print(f"   ✅ 加载了 {len(self.fdc_variables)} 个FDC变量")

        # 分析变量类型分布
        self._analyze_fdc_patterns()

    def _analyze_fdc_patterns(self):
        """分析FDC变量的命名模式"""
        pattern_counts = {}
        for var in self.fdc_variables:
            # 提取变量模式
            parts = var.split('_')
            if len(parts) >= 4:
                # 提取关键部分：fdc_[范围]_[指标类型]_[时间窗口]
                prefix = '_'.join(parts[:3])  # fdc_all_avg 等
                pattern_counts[prefix] = pattern_counts.get(prefix, 0) + 1

        print(f"\n📈 FDC变量模式Top10:")
        for pattern, count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"   - {pattern}: {count}个变量")

    def check_feature_uniqueness(self, feature_name: str) -> Tuple[bool, List[str]]:
        """
        检查特征名称是否与现有FDC特征重复

        Args:
            feature_name: 新特征名称

        Returns:
            (是否唯一, 相似特征列表)
        """
        # 精确匹配
        if feature_name in self.fdc_variable_names:
            return False, [feature_name]

        # 模糊匹配：找出相似特征
        similar_features = []
        feature_lower = feature_name.lower()

        for fdc_var in self.fdc_variables:
            # 检查相似性（包含关系或编辑距离较近）
            if (feature_lower in fdc_var.lower() or
                fdc_var.lower() in feature_lower or
                self._edit_distance(feature_lower, fdc_var.lower()) <= 3):
                similar_features.append(fdc_var)

        is_unique = len(similar_features) == 0
        return is_unique, similar_features[:5]  # 最多返回5个相似特征

    def _edit_distance(self, s1: str, s2: str) -> int:
        """计算编辑距离"""
        if len(s1) < len(s2):
            return self._edit_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # 插入、删除、替换
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def design_features_with_llm(self) -> List[Dict]:
        """
        使用LLM基于业务知识设计新特征

        Returns:
            特征设计列表
        """
        print("\n🧠 使用LLM设计新特征...")

        # 构建Prompt
        prompt = self._build_design_prompt()

        # 调用LLM
        messages = [{"role": "user", "content": prompt}]
        response = self.llm_client.chat(messages, temperature=0.3)

        # 解析响应
        try:
            # 尝试提取JSON
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                features_data = json.loads(json_str)
                features = features_data.get('features', [])
                print(f"   ✅ LLM设计了 {len(features)} 个新特征")
                return features
            else:
                print(f"   ⚠️  无法从响应中提取JSON")
                return []
        except Exception as e:
            print(f"   ❌ JSON解析失败: {e}")
            print(f"   响应预览: {response[:500]}...")
            return []

    def _build_design_prompt(self) -> str:
        """构建设计特征的Prompt"""

        # 提取知识库摘要
        kb = self.knowledge_base.get('knowledge_base', {})
        summary = kb.get('summary', {})
        base_analysis = kb.get('base_analysis', {})
        app_analysis = kb.get('app_analysis', {})
        fdc_analysis = kb.get('fdc_analysis', {})
        risk_rules = kb.get('risk_rules', [])

        # 统计高风险应用类别
        llm_class = app_analysis.get('llm_classification', {})
        high_risk_summary = llm_class.get('high_risk_summary', {})
        category_dist = llm_class.get('category_distribution', {})

        prompt = f"""# 任务：为印尼短期现金贷业务设计新的风控特征

## 一、业务背景

### 1.1 数据集概况
- 样本数: {summary.get('total_samples', 'N/A')}
- 逾期率: {summary.get('overdue_rate', 0) * 100:.2f}%
- 已分类应用总数: {app_analysis.get('llm_classification', {}).get('total_classified_apps', 'N/A')}

### 1.2 关键业务洞察

**客户画像风险**:
- 性别风险: 男性逾期率{base_analysis.get('gender_risk', {}).get('male_overdue_rate', 0) * 100:.2f}%，女性{base_analysis.get('gender_risk', {}).get('female_overdue_rate', 0) * 100:.2f}%
- 年龄风险分布:
{self._format_age_risk(base_analysis.get('age_risk_bins', []))}
- 收入风险相关系数: {base_analysis.get('income_risk_correlation', 'N/A')}
- 职业风险分布:
{self._format_job_risk(base_analysis.get('job_risk_distribution', {}))}
- 婚姻风险分布:
{self._format_marriage_risk(base_analysis.get('marriage_risk', {}))}
- 子女风险: {base_analysis.get('children_risk', {}).get('0', 'N/A')} 无子女客户逾期率
- 工作年限风险相关系数: {base_analysis.get('work_years_risk_correlation', 'N/A')}

**应用行为风险**:
- 平均安装应用数: {app_analysis.get('avg_app_count', 'N/A')}
- 最大安装应用数: {app_analysis.get('max_app_count', 'N/A')}
- 最小安装应用数: {app_analysis.get('min_app_count', 'N/A')}
- 金融应用占比: {app_analysis.get('finance_app_ratio', 0) * 100:.2f}%
- 高风险应用分布:
{self._format_high_risk_categories(high_risk_summary)}
- 应用类别分布（16个标准类别）:
{self._format_category_distribution(category_dist)}

**FDC信用报告风险**:
- 查询频率: 近3天{fdc_analysis.get('query_freq_risk', {}).get('last_3days_avg', 'N/A')}次，近7天{fdc_analysis.get('query_freq_risk', {}).get('last_7days_avg', 'N/A')}次，近30天{fdc_analysis.get('query_freq_risk', {}).get('last_30days_avg', 'N/A')}次
- 贷款记录统计: 平均{fdc_analysis.get('loan_record_stats', {}).get('avg_loan_count', 'N/A')}笔，最大{fdc_analysis.get('loan_record_stats', {}).get('max_loan_count', 'N/A')}笔，平均未还余额{fdc_analysis.get('loan_record_stats', {}).get('avg_outstanding_balance', 0):,.0f}印尼盾，平均活跃平台数{fdc_analysis.get('loan_record_stats', {}).get('avg_active_platforms', 'N/A')}个
- DPD分析: 平均最大逾期天数{fdc_analysis.get('dpd_analysis', {}).get('avg_max_dpd', 'N/A')}天，逾期30天+比例{fdc_analysis.get('dpd_analysis', {}).get('dpd_30plus_ratio', 0) * 100:.2f}%，60天+比例{fdc_analysis.get('dpd_analysis', {}).get('dpd_60plus_ratio', 0) * 100:.2f}%，90天+比例{fdc_analysis.get('dpd_analysis', {}).get('dpd_90plus_ratio', 0) * 100:.2f}%

### 1.3 业务风险规则
{self._format_risk_rules(risk_rules)}

## 二、现有FDC特征清单（共{len(self.fdc_variables)}个）

**你不能重复设计以下类型的特征**：
{self._format_fdc_examples()}

## 三、设计新特征的指导原则

### 3.1 特征生成策略（重要：请采用系统化生成）

**不要仅凭经验设计单个特征！请按以下系统化方法生成特征：**

#### 模板1: 时间窗口比例特征
```
模板: ratio_{{source}}_{{metric}}_{{period}}d
参数:
  - source: [fdc_loan, applist_gambling, applist_cashloan, applist_fintech]
  - metric: [count, avg, sum]
  - period: [3, 7, 30, 90]

示例生成:
  ratio_fdc_loan_count_3d, ratio_fdc_loan_count_7d, ratio_fdc_loan_count_30d, ...
  ratio_applist_gambling_count_3d, ratio_applist_gambling_avg_7d, ...

请按此模式生成所有参数组合！
```

#### 模板2: 交叉特征
```
模板: cross_{{base_field}}_{{source_metric}}
参数:
  - base_field: [gender, age_bin, salary_bin, marriage, job_work_years]
  - source_metric: [fdc_loan_count, gambling_ratio, inquiry_7d, overdue_rate]

示例生成:
  cross_gender_gambling_ratio
  cross_age_bin_fdc_loan_count
  ...

请按此模式生成所有组合！
```

### 3.2 特征方向
请从以下维度设计新特征：

1. **应用行为特征** (基于applist):
   - 高风险应用类别的统计特征（安装数、占比、更新频率等）
   - 应用使用模式（是否安装多个同类应用、是否安装克隆应用等）
   - 应用安装时间特征（新安装 vs 老旧应用）
   - 应用类型多样性

2. **FDC信用报告特征** (基于FDC数据):
   - 查询行为模式（查询频率变化、近期查询激增等）
   - 贷款行为模式（贷款笔数变化、平台数量变化等）
   - 逾期行为模式（历史逾期严重程度、当前逾期占比等）
   - 多平台借贷行为

3. **客户画像特征** (基于base信息):
   - 客户稳定性（工作年限、婚姻状况等）
   - 客户还款能力（收入水平、抚养人数等）
   - 客户年龄与客户行为交叉特征

4. **时间序列特征**:
   - 最近N天的行为变化
   - 时间窗口对比（近7天 vs 近30天）
   - 行为趋势（递增/递减）

5. **交叉特征**:
   - applist × FDC交叉
   - base × FDC交叉
   - 多维度组合

### 3.3 特征设计要求

每个特征必须包含：
- **特征名称**: 英文，遵循 `{{类型}}_{{数据源}}_{{描述}}_{{时间窗口}}` 命名规范
- **特征类型**: count/ratio/max/min/avg/time_gap/cross
- **数据源**: applist/fdc/base
- **业务解释**: 中文，说明该特征的业务含义
- **设计理由**: 为什么这个特征对风控有用
- **计算逻辑**: 简要说明如何计算

### 3.3 重要约束

❌ **不能设计**:
- 与现有{len(self.fdc_variables)}个FDC特征重复的特征
- 需要未来数据才能计算的特征（防穿越）

✅ **应该设计**:
- 业务解释清晰、可追溯的特征
- 计算简单、数据源可靠的特征
- 能有效区分好坏客户的特征
- 针对首贷客户的特征

## 四、输出格式

请输出JSON格式（不要有其他文字）：

```json
{{
  "features": [
    {{
      "feature_name": "特征名称（英文）",
      "feature_type": "count/ratio/max/min/avg/time_gap/cross",
      "data_source": "applist/fdc/base",
      "business_explanation_cn": "中文业务解释",
      "design_reason": "为什么设计这个特征",
      "calculation_logic": "计算逻辑简述",
      "expected_risk_correlation": "positive/negative"
    }}
  ]
}}
```

**请设计至少20个新特征**。

现在请开始设计特征：
"""
        return prompt

    def _format_high_risk_categories(self, high_risk_summary: Dict) -> str:
        """格式化高风险应用类别"""
        if not high_risk_summary:
            return "   （无数据）"

        categories = high_risk_summary.get('categories', {})
        lines = []
        for cat, info in categories.items():
            count = info.get('count', 0)
            desc = info.get('description', '')
            lines.append(f"   - {cat}: {count}个应用，{desc}")
        return '\n'.join(lines)

    def _format_age_risk(self, age_bins: List[Dict]) -> str:
        """格式化年龄风险分布"""
        if not age_bins:
            return "   （无数据）"

        lines = []
        for bin in age_bins:
            bin_name = bin.get('bin', 'N/A')
            rate = bin.get('overdue_rate', 0) * 100
            lines.append(f"   - {bin_name}: 逾期率{rate:.2f}%")
        return '\n'.join(lines)

    def _format_job_risk(self, job_distribution: Dict) -> str:
        """格式化职业风险分布"""
        if not job_distribution:
            return "   （无数据）"

        lines = []
        # 职业代码映射（基于印尼现金贷常见职业代码）
        job_map = {
            '1': '公务员/政府机构',
            '2': '军人/警察',
            '3': '教师',
            '4': '医护人员',
            '5': 'IT/互联网从业者',
            '6': '金融/保险从业者',
            '7': '销售/客服',
            '8': '制造/工厂工人',
            '9': '建筑/装修工人',
            '10': '司机/运输工人',
            '11': '餐饮/服务业',
            '12': '自由职业/个体户',
            '13': '农民/渔业',
            '14': '艺术/媒体/娱乐',
            '15': '律师/会计师',
            '16': '无业/失业'
        }

        for job_code, overdue_rate in sorted(job_distribution.items(), key=lambda x: x[1], reverse=True):
            job_name = job_map.get(job_code, f'其他({job_code})')
            lines.append(f"   - {job_name}(代码{job_code}): 逾期率{overdue_rate * 100:.2f}%")
        return '\n'.join(lines)

    def _format_marriage_risk(self, marriage_risk: Dict) -> str:
        """格式化婚姻风险分布"""
        if not marriage_risk:
            return "   （无数据）"

        marriage_map = {
            '1': '已婚',
            '2': '未婚',
            '3': '离异',
            '4': '丧偶'
        }

        lines = []
        for status, rate in marriage_risk.items():
            status_name = marriage_map.get(status, f'其他({status})')
            lines.append(f"   - {status_name}(代码{status}): 逾期率{rate * 100:.2f}%")
        return '\n'.join(lines)

    def _format_category_distribution(self, category_dist: Dict) -> str:
        """格式化应用类别分布"""
        if not category_dist:
            return "   （无数据）"

        # 16个标准类别的中文说明
        category_desc = {
            'cash_loan': '现金贷',
            'fintech_lending': '金融科技借贷',
            'gambling': '赌博/棋牌',
            'fake_gps': '虚拟定位',
            'app_store': '第三方商店',
            'clone_app': '克隆工具',
            'banking': '银行',
            'ewallet': '电子钱包',
            'installment': '分期消费',
            'shopping': '购物',
            'transportation': '交通出行',
            'food_delivery': '外卖订餐',
            'utility': '工具',
            'productivity': '办公效率',
            'religious': '宗教',
            'social_entertainment': '社交娱乐',
            'other': '其他'
        }

        lines = []
        for cat, count in sorted(category_dist.items(), key=lambda x: x[1], reverse=True):
            desc = category_desc.get(cat, cat)
            lines.append(f"   - {desc}({cat}): {count}个应用")
        return '\n'.join(lines)

    def _format_risk_rules(self, risk_rules: List[Dict]) -> str:
        """格式化业务风险规则"""
        if not risk_rules:
            return "   （无数据）"

        lines = []
        for rule in risk_rules:
            rule_text = rule.get('rule', '')
            desc = rule.get('description', '')
            level = rule.get('risk_level', '')
            lines.append(f"   - {rule_text}: {desc} (风险等级: {level})")
        return '\n'.join(lines)

    def _format_fdc_examples(self) -> str:
        """格式化FDC特征示例"""
        # 展示前50个变量作为示例
        examples = self.fdc_variables[:50]
        lines = []
        lines.append("   **以下特征已存在，请勿重复设计**:\n")
        for var in examples:
            lines.append(f"   - {var}")
        lines.append(f"\n   ... 还有{len(self.fdc_variables) - 50}个其他特征")
        return '\n'.join(lines)

    def validate_features(self, features: List[Dict]) -> List[Dict]:
        """
        验证设计的特征（去重、格式检查等）

        Args:
            features: LLM设计的特征列表

        Returns:
            验证通过的特征列表
        """
        print("\n🔍 验证特征设计...")
        valid_features = []
        rejected_features = []

        for feature in features:
            feature_name = feature.get('feature_name', '')

            # 检查必填字段
            required_fields = ['feature_name', 'feature_type', 'data_source',
                             'business_explanation_cn', 'design_reason']
            missing_fields = [f for f in required_fields if not feature.get(f)]

            if missing_fields:
                print(f"   ❌ 特征 '{feature_name}' 缺少字段: {missing_fields}")
                rejected_features.append(feature)
                continue

            # 检查特征名称唯一性
            is_unique, similar = self.check_feature_uniqueness(feature_name)
            if not is_unique:
                print(f"   ❌ 特征 '{feature_name}' 与现有特征重复或过于相似")
                print(f"      相似特征: {similar[:3]}")
                rejected_features.append(feature)
                continue

            # 检查特征类型合法性
            valid_types = ['count', 'ratio', 'max', 'min', 'avg', 'time_gap', 'cross']
            if feature.get('feature_type') not in valid_types:
                print(f"   ❌ 特征 '{feature_name}' 类型不合法: {feature.get('feature_type')}")
                rejected_features.append(feature)
                continue

            # 通过验证
            valid_features.append(feature)
            print(f"   ✅ 特征 '{feature_name}' 通过验证")

        print(f"\n📊 验证结果: {len(valid_features)} 个通过, {len(rejected_features)} 个被拒绝")
        return valid_features

    def save_feature_design(self, features: List[Dict],
                           output_path: str = 'outputs/feature_design/feature_design_doc.json'):
        """保存特征设计文档"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        design_doc = {
            'meta': {
                'total_features': len(features),
                'design_date': '2026-05-04',
                'knowledge_base_version': 'v1',
                'fdc_variable_count': len(self.fdc_variables)
            },
            'features': features
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(design_doc, f, ensure_ascii=False, indent=2)

        print(f"\n💾 特征设计文档已保存: {output_path}")

    def run_stepwise_design(self) -> List[Dict]:
        """
        运行3步Chain-of-Thought特征设计框架

        Returns:
            特征设计列表（从step3模板展开）
        """
        print("\n" + "=" * 70)
        print("特征设计Agent - 3步Chain-of-Thought框架")
        print("=" * 70)

        # 加载知识库和FDC变量
        self.load_knowledge_base()
        self.load_fdc_variables()

        # 调用stepwise框架设计脚本
        import subprocess
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'stepwise_framework_design.py')
        result = subprocess.run(['python', script_path], capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            print(f"\n❌ Stepwise框架设计失败: {result.stderr[:500]}")
            return []

        # 加载step3模板系统
        template_path = 'outputs/feature_design/stepwise/step3_template_system.json'
        if not os.path.exists(template_path):
            print(f"\n❌ 未找到模板文件: {template_path}")
            return []

        with open(template_path, 'r', encoding='utf-8') as f:
            template_system = json.load(f)

        # 从模板展开为具体特征
        features = self._expand_templates_to_features(template_system)

        return features

    def _expand_templates_to_features(self, template_system: Dict) -> List[Dict]:
        """
        将模板系统展开为具体特征列表

        Args:
            template_system: step3_template_system.json内容

        Returns:
            特征设计列表
        """
        print("\n🔧 展开模板为具体特征...")
        features = []
        template_count = 0

        categories = template_system.get('template_system', {}).get('categories_with_templates', [])
        for category in categories:
            category_name = category.get('category_name', '')
            templates = category.get('templates', [])

            for template in templates:
                template_count += 1
                template_name = template.get('template_name', '')
                param_space = template.get('parameter_space', {})
                formula_template = template.get('formula_template', '')
                business_meaning = template.get('business_meaning', '')
                risk_interpretation = template.get('risk_interpretation', '')
                anti_penetration = template.get('anti_penetration', True)

                # 从参数空间生成具体组合
                param_combinations = self._generate_param_combinations(param_space)
                print(f"   模板 '{template_name}': {len(param_combinations)}个特征")

                for params in param_combinations:
                    # 替换模板中的占位符
                    feature_name = self._replace_template_vars(template_name, params)
                    formula = self._replace_template_vars(formula_template, params)
                    meaning = self._replace_template_vars(business_meaning, params)
                    interpretation = self._replace_template_vars(risk_interpretation, params)

                    feature = {
                        'feature_name': feature_name,
                        'feature_type': 'cross' if 'cross' in feature_name else 'ratio',
                        'data_source': 'fdc' if 'fdc' in feature_name or 'fcd' in feature_name else ('applist' if 'app' in feature_name else 'base'),
                        'business_explanation_cn': meaning,
                        'design_reason': f"基于12类别框架-{category_name}，模板{template_name}",
                        'calculation_logic': formula,
                        'expected_risk_correlation': 'positive' if '逾期' in interpretation or '风险' in interpretation else 'negative',
                        'category': category_name,
                        'template_name': template_name,
                        'risk_interpretation': interpretation,
                        'anti_penetration': anti_penetration
                    }
                    features.append(feature)

        print(f"\n   ✅ 共生成 {len(features)} 个特征（来自{template_count}个模板）")
        return features

    def _generate_param_combinations(self, param_space: Dict) -> List[Dict]:
        """
        从参数空间生成交叉组合

        Args:
            param_space: {'short_windows': ['3d', '7d'], 'long_windows': ['30d', '90d'], ...}

        Returns:
            参数字典列表
        """
        if not param_space:
            return [{}]  # 返回一个空字典，代表单个组合

        # 获取所有参数维度
        keys = list(param_space.keys())
        values = list(param_space.values())

        # 生成笛卡尔积
        import itertools
        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(keys, combo)))

        return combinations

    def _replace_template_vars(self, template: str, params: Dict) -> str:
        """
        替换模板中的 {{param}} 占位符

        Args:
            template: 模板字符串
            params: 参数字典

        Returns:
            替换后的字符串
        """
        result = template
        for key, value in params.items():
            result = result.replace('{{' + key + '}}', str(value))
            # 处理不带括号的占位符（兼容旧格式）
            result = result.replace('{' + key + '}', str(value))
        return result

    def run(self):
        """主执行流程（支持3步Chain-of-Thought框架）"""
        print("=" * 70)
        print("特征设计Agent - 开始执行")
        print("=" * 70)

        # 使用3步Chain-of-Thought框架
        features = self.run_stepwise_design()

        if not features:
            print("\n❌ 特征设计失败")
            return

        # 验证特征（去重、格式检查）
        valid_features = self.validate_features(features)

        if not valid_features:
            print("\n❌ 没有特征通过验证")
            return

        # 保存特征设计文档
        self.save_feature_design(valid_features)

        # 打印摘要
        print("\n" + "=" * 70)
        print("特征设计Agent - 执行完成")
        print("=" * 70)
        print(f"\n📊 设计特征统计:")
        print(f"   - 总数: {len(valid_features)}个")

        # 按类型统计
        type_counts = {}
        source_counts = {}
        category_counts = {}
        for f in valid_features:
            ftype = f.get('feature_type', 'unknown')
            source = f.get('data_source', 'unknown')
            category = f.get('category', 'unknown')
            type_counts[ftype] = type_counts.get(ftype, 0) + 1
            source_counts[source] = source_counts.get(source, 0) + 1
            category_counts[category] = category_counts.get(category, 0) + 1

        print(f"\n   按类型分布:")
        for ftype, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"     - {ftype}: {count}个")

        print(f"\n   按数据源分布:")
        for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"     - {source}: {count}个")

        print(f"\n   按类别分布 (Top 5):")
        for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"     - {cat}: {count}个")

        print(f"\n✅ 特征设计完成")
        print(f"   下一环节: 特征工程Agent将基于此设计开发代码")


if __name__ == '__main__':
    agent = FeatureDesignAgent()
    agent.run()
