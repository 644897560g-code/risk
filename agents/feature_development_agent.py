"""
Feature Development Agent - 合并特征设计与特征工程

职责：
1. 注入IV/PSI反馈（从iv_psi_feedback_rN.json读取）
2. 通道1：模板召回 → 参数填充 → dsl→python
3. 通道2：LLM推理新模板（通道1无匹配时）
4. 生成完整特征计算代码
5. self-review：生成完毕后整体审视
"""

import json
import os
import sys
import logging
from typing import Dict, List, Optional
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.llm_client import LLMClient
from agents.skill_registry import SkillResult
from backend.app.database import SessionLocal
from backend.services.template_library import (
    ACTIVE_STATUS,
    PENDING_STATUS,
    append_template_python_code,
    approve_template,
    get_template,
    list_templates,
    template_to_channel1_item,
    upsert_template_from_payload,
)

logger = logging.getLogger(__name__)


class FeatureDevelopmentAgent:
    """特征开发Agent - 合并设计+工程"""

    def __init__(self):
        self.llm_client = LLMClient()
        self.features = []            # 最终特征列表
        self.feature_doc = None        # 特征设计文档
        self.app_classification_cache = {}
        self.iv_psi_feedback = None    # IV/PSI反馈
        self.generated_code = None
        self.self_review_passed = False

        # 通道1模板库由 PostgreSQL 承载；JSON 文件仅作为 scripts/init_project_data.py 的 seed 来源。
        self.channel1_calculators_path = 'outputs/feature_code/channel1_calculators.py'
        # 旧版模板系统（用于兼容过渡）
        self.legacy_templates_path = 'outputs/feature_design/stepwise/phase3_template_system.json'
        self.feature_design_doc_path = 'outputs/feature_design/feature_design_doc.json'

        # 通道2晋升记录
        self.promoted_templates = []

        # 晋升开关（默认需人工确认）
        self.auto_promote = os.getenv('AUTO_PROMOTE_TEMPLATE', 'false').lower() == 'true'

    def load_iv_psi_feedback(self):
        """加载最近的IV/PSI反馈"""
        feedback_dir = 'outputs/evaluation'
        if not os.path.exists(feedback_dir):
            logger.info("  evaluation目录不存在，无历史反馈")
            return

        feedback_files = [f for f in os.listdir(feedback_dir)
                          if f.startswith('iv_psi_feedback_r') and f.endswith('.json')]
        if not feedback_files:
            logger.info("  无历史IV/PSI反馈")
            return

        # 按round号排序，取最近3轮
        def round_num(f):
            try:
                return int(f.replace('iv_psi_feedback_r', '').replace('.json', ''))
            except:
                return 0

        feedback_files.sort(key=round_num, reverse=True)
        recent_files = feedback_files[:3]

        feedbacks = []
        summary_patterns = []
        for f in recent_files:
            path = os.path.join(feedback_dir, f)
            with open(path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
                feedbacks.append({
                    'round': data.get('round'),
                    'template_feedback': data.get('template_feedback', [])
                })
                summary_patterns.extend(data.get('summary_patterns', []))

        # 去重summary_patterns
        seen = set()
        unique_patterns = []
        for p in summary_patterns:
            if p not in seen:
                seen.add(p)
                unique_patterns.append(p)

        self.iv_psi_feedback = {
            'recent_rounds': feedbacks,
            'summary_patterns': unique_patterns[:10]  # 最多保留10条
        }
        logger.info(f"  加载IV/PSI反馈: {len(feedbacks)}轮, {len(unique_patterns)}条总结")

    def _build_feedback_prompt_section(self) -> str:
        """构建IV/PSI反馈的prompt片段"""
        if not self.iv_psi_feedback:
            return ""

        section = "\n## 历史IV/PSI反馈（通道1模板效果总结）\n\n"
        section += "以下是从最近几轮特征评估中提取的模板效果数据，供设计参考：\n\n"

        for fb in self.iv_psi_feedback['recent_rounds']:
            section += f"### 第{fb['round']}轮\n"
            for tf in fb['template_feedback']:
                pid = tf.get('template_id', '?')
                name = tf.get('template_name', '?')
                ch = tf.get('channel', '?')
                section += f"- {pid}({name}) [{ch}]: "
                passed = tf.get('passed', {})
                failed = tf.get('failed', {})
                section += f"通过{passed.get('count', 0)}个(avg_iv={passed.get('avg_iv', 'N/A')}, avg_psi={passed.get('avg_psi', 'N/A')}), "
                section += f"失败{failed.get('count', 0)}个"
                reasons = failed.get('reasons', [])
                if reasons:
                    fail_details = []
                    for r in reasons:
                        parts = [f"{r.get('name', '?')}"]
                        if r.get('iv', 1) < 0.02:
                            parts.append(f"iv={r['iv']}")
                        if r.get('psi', 0) > 0.25:
                            parts.append(f"psi={r['psi']}")
                        if r.get('coverage', 1) <= 0.05:
                            parts.append(f"coverage={r['coverage']}")
                        fail_details.append("(".join(parts) + ")")
                    section += " [" + ", ".join(fail_details) + "]"
                section += "\n"

        if self.iv_psi_feedback['summary_patterns']:
            section += "\n### 经验总结\n"
            for p in self.iv_psi_feedback['summary_patterns']:
                section += f"- {p}\n"

        return section

    def load_app_classification_cache(self):
        """加载APP分类缓存"""
        cache_file = 'outputs/app_analysis/classification_complete_11850.json'
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.app_classification_cache = data.get('classifications', {})
                logger.info(f"  加载APP分类缓存: {len(self.app_classification_cache)}个")

    # ========== Channel 1 Skills ==========

    def skill_template_recall(self, dimension: str = None, dsl_type: str = None) -> SkillResult:
        """通道1模板召回：根据维度(dimension)和DSL类型匹配模板

        通道1模板是业务无关的纯计算模式抽象，
        从 PostgreSQL 模板库中按维度和 DSL 类型召回。

        Args:
            dimension: 维度名（volume/structure/change/position/consistency/relation/derived）
            dsl_type: DSL类型名（如 count/proportion/trend 等template_name）

        Returns:
            匹配的模板列表
        """
        db = SessionLocal()
        try:
            templates = list_templates(db, status=ACTIVE_STATUS, dimension=dimension)
            matched = []

            for tmpl in templates:
                item = template_to_channel1_item(tmpl)
                if dsl_type and item.get('template_name') != dsl_type:
                    continue
                matched.append(item)

            logger.info(f"  通道1模板召回: dimension={dimension}, dsl_type={dsl_type} → {len(matched)}个匹配")
            return SkillResult(success=True, data=matched)
        except Exception as e:
            logger.warning(f"  通道1模板召回失败: {e}")
            return SkillResult(success=False, data=[], error=str(e))
        finally:
            db.close()

    def _skill_recall_legacy(self, risk_type, feature_category, path) -> SkillResult:
        """旧版模板召回（兼容旧模板格式）"""
        with open(path, 'r', encoding='utf-8') as f:
            template_system = json.load(f)
        categories = template_system.get('categories', [])
        matched = []
        for cat in categories:
            cat_name = cat.get('category_name', '')
            cat_risk_types = cat.get('covered_risk_types', [])
            if risk_type and risk_type not in cat_risk_types:
                if feature_category and feature_category != cat_name:
                    continue
                elif not feature_category:
                    continue
            for tmpl in cat.get('templates', []):
                matched.append({
                    'template_id': tmpl.get('template_id'),
                    'template_name': tmpl.get('template_name'),
                    'category': cat_name,
                    'risk_types': cat_risk_types,
                    'parameter_space': tmpl.get('parameter_space', {}),
                    'formula_template': tmpl.get('formula_template', ''),
                    'business_meaning': tmpl.get('business_meaning', '')
                })
        logger.info(f"  旧版模板召回: {len(matched)}个匹配")
        return SkillResult(success=True, data=matched)

    def skill_param_fill(self, template: Dict, data_profile: Dict = None) -> SkillResult:
        """参数填充：根据模板parameter_space生成具体参数组合（确定性展开）

        根据 parameter_space 的 type 描述为每个模板生成2-4组合理的参数组合。
        不再依赖LLM—使用基于实际数据结构的确定性规则。

        生成的参数组合覆盖不同数据源、窗口和过滤条件，
        使后续LLM业务化时可从30+组合中选出最佳特征。
        """
        param_space = template.get('parameter_space', {})
        template_id = template.get('template_id', '')
        template_name = template.get('template_name', '')

        if not param_space:
            return SkillResult(success=True, data=[{
                'template_id': template_id,
                'params': {}
            }])

        combinations = self._generate_param_combinations(template_id, template_name, param_space)
        data = [{'template_id': template_id, 'params': combo} for combo in combinations]

        logger.info(f"  参数填充(确定性): {template_id}({template_name}) → {len(data)}个组合")
        for d in data:
            logger.info(f"    - {d['params']}")

        return SkillResult(success=True, data=data)

    def _generate_param_combinations(self, template_id: str, template_name: str,
                                      param_space: Dict) -> List[Dict]:
        """根据template_id和parameter_space类型描述，生成确定性参数组合

        每个模板2-4个组合，参数值基于实际数据字段和业务合理性选择。
        """
        combos = []

        # ========== T001: count ==========
        if template_id == 'T001':
            for src, cond in [
                ('fdc_inquiry', None),
                ('fdc_pinjaman', None),
                ('fdc_pinjaman', {'status_pinjaman': 'O'}),
                ('fdc_pinjaman', {'kualitas_pinjaman': '5'}),
                ('applist', None),
            ]:
                if src == 'fdc_inquiry':
                    wins = [7, 30]
                elif src == 'applist':
                    wins = [7, 30]
                else:
                    wins = [90, 180]
                for w in wins:
                    combo = {'source': src, 'window': w}
                    if cond:
                        combo['cond'] = cond
                    combos.append(combo)

        # ========== T002: distinct_count ==========
        elif template_id == 'T002':
            for src, dedup, w in [
                ('fdc_inquiry', 'hit_by', 30),
                ('fdc_inquiry', 'hit_by', 90),
                ('fdc_pinjaman', 'id_penyelenggara', 90),
                ('fdc_pinjaman', 'tipe_pinjaman', 180),
            ]:
                combos.append({'source': src, 'dedup_field': dedup, 'window': w})

        # ========== T003: decayed_sum ==========
        elif template_id == 'T003':
            for src, w, decay_func, rate, vf in [
                ('fdc_pinjaman', 90, 'exponential', 0.05, 'nilai_pendanaan'),
                ('fdc_pinjaman', 180, 'exponential', 0.02, 'nilai_pendanaan'),
                ('fdc_pinjaman', 90, 'exponential', 0.1, 'nilai_pendanaan'),
            ]:
                combos.append({
                    'source': src, 'window': w,
                    'decay_func': decay_func, 'decay_rate': rate,
                    'value_field': vf,
                })

        # ========== T004: proportion ==========
        elif template_id == 'T004':
            # applist-based: use allowed_categories
            for cats, w in [
                (['gambling'], 30),
                (['cash_loan'], 30),
                (['fintech_lending'], 30),
                (['cash_loan', 'fintech_lending'], 90),
            ]:
                combos.append({
                    'source': 'applist', 'window': w,
                    'allowed_categories': cats
                })
            # fdc_pinjaman-based: use target_cond
            for cond, w in [
                ({'kualitas_pinjaman': '3'}, 180),
                ({'kualitas_pinjaman': '5'}, 180),
                ({'status_pinjaman': 'O'}, 90),
            ]:
                combos.append({
                    'source': 'fdc_pinjaman', 'window': w,
                    'target_cond': cond
                })

        # ========== T005: concentration ==========
        elif template_id == 'T005':
            for method, category_field, src, w in [
                ('gini', 'id_penyelenggara', 'fdc_pinjaman', 90),
                ('entropy', 'tipe_pinjaman', 'fdc_pinjaman', 180),
                ('cv', 'id_penyelenggara', 'fdc_pinjaman', 90),
            ]:
                combos.append({
                    'source': src, 'method': method,
                    'category_field': category_field, 'window': w
                })

        # ========== T006: overlap ==========
        elif template_id == 'T006':
            for sa, fa, sb, fb, w in [
                ('applist', 'packageX', 'fdc_pinjaman', 'id_penyelenggara', 30),
                ('applist', 'packageX', 'fdc_pinjaman', 'id_penyelenggara', 90),
            ]:
                combos.append({
                    'source_a': sa, 'field_a': fa,
                    'source_b': sb, 'field_b': fb,
                    'window': w
                })

        # ========== T007: period_compare ==========
        elif template_id == 'T007':
            for src, short, long in [
                ('fdc_inquiry', 7, 30),
                ('fdc_inquiry', 3, 7),
                ('fdc_pinjaman', 30, 90),
            ]:
                combos.append({
                    'source': src, 'short_window': short, 'long_window': long
                })

        # ========== T008: trend ==========
        elif template_id == 'T008':
            for src, windows in [
                ('fdc_inquiry', [7, 15, 30]),
                ('fdc_pinjaman', [30, 60, 90]),
                ('applist', [7, 15, 30]),
            ]:
                combos.append({'source': src, 'windows': windows})

        # ========== T009: spike ==========
        elif template_id == 'T009':
            for src, w, threshold in [
                ('fdc_inquiry', 30, 2.0),
                ('fdc_inquiry', 30, 3.0),
                ('applist', 30, 3.0),
            ]:
                combos.append({
                    'source': src, 'window': w, 'threshold': threshold
                })

        # ========== T010-T012: position-type (no source/window) ==========
        elif template_id == 'T010':
            combos.append({
                'method': 'rank',
                'reference_type': 'population',
                'target_metric': 'salary'
            })

        elif template_id == 'T011':
            combos.append({
                'method': 'zscore',
                'reference_type': 'peer_group',
                'target_metric': 'loan_amount'
            })

        elif template_id == 'T012':
            combos.append({
                'method': 'isolation_forest',
                'target_metric': 'app_install_pattern',
                'window_days': 30
            })

        # ========== T013: declared_vs_actual ==========
        elif template_id == 'T013':
            for declared, actual, method in [
                ('base.salary', 'fdc_pinjaman.nilai_pendanaan', 'ratio'),
                ('base.salary', 'fdc_pinjaman.nilai_pendanaan', 'gap'),
            ]:
                combos.append({
                    'declared_field': declared,
                    'actual_field': actual,
                    'method': method
                })

        # ========== T014: cross_source_discrepancy ==========
        elif template_id == 'T014':
            # 注意: 只保留语义上可对比的跨源字段对
            # ❌ 已移除: base.job(数字编码) vs fdc_pinjaman.tipe_pinjaman(文字) — 语义不兼容
            # ✅ 保留: base.salary vs fdc_pinjaman loan amounts
            #  计算逻辑: salary按200万IDR为档位离散化，nilai_pendanaan同样离散化，比较档位是否一致
            combos.append({
                'field_pairs_config': [
                    {'src': 'base', 'field': 'salary'},
                    {'src': 'fdc_pinjaman', 'field': 'nilai_pendanaan'}
                ]
            })

        # ========== T015: identity_cluster ==========
        elif template_id == 'T015':
            for identity_field, shared_field, min_threshold in [
                ('device_id', 'packageX', 3),
                ('device_id', 'id_penyelenggara', 2),
            ]:
                combos.append({
                    'identity_field': identity_field,
                    'shared_field': shared_field,
                    'min_threshold': min_threshold
                })

        # 兜底：如果没有任何匹配，返回一个空参数组合
        if not combos:
            combos.append({})

        return combos

    def skill_dsl_to_python(self, template: Dict, params: Dict = None) -> SkillResult:
        """dsl→python：生成特征计算代码片段

        加载channel1_calculators中对应的Python函数，
        填入参数后生成可执行的调用代码。

        Args:
            template: 模板信息（含python_function字段）
            params: 参数组合

        Returns:
            包含python代码块的结果
        """
        func_name = template.get('python_function', '')
        module_name = template.get('python_module', 'channel1_calculators')

        if not func_name:
            # 降级：使用旧的代码生成模式
            return self._dsl_to_python_fallback(template, params)

        # 生成函数调用代码（含参数填充）
        param_str = ', '.join(f"{k}={repr(v)}" for k, v in (params or {}).items())
        dsl_str = template.get('dsl', '')
        formula = template.get('formula_template', '')
        if params:
            for k, v in params.items():
                formula = formula.replace('{' + k + '}', str(v))

        python_code = f"""
    # [{template.get('template_id')}] {template.get('template_name_cn', '')}
    # DSL: {dsl_str}
    # Formula: {formula}
    # Params: {json.dumps(params, ensure_ascii=False) if params else '{}'}
    from outputs.feature_code.{module_name} import {func_name}
    result = {func_name}(data, {param_str}, apply_time_dt=apply_time_dt)
"""
        return SkillResult(success=True, data={
            'template_id': template.get('template_id'),
            'params': params or {},
            'formula': formula,
            'python_code': python_code
        })

    def _dsl_to_python_fallback(self, template: Dict, params: Dict = None) -> SkillResult:
        """旧版dsl→python（当模板没有python_function字段时降级）"""
        formula = template.get('formula_template', '')
        if params:
            for k, v in params.items():
                formula = formula.replace('{{' + k + '}}', str(v))
        python_code = f"""
    # [{template.get('template_id')}] {template.get('business_meaning', '')}
    # Formula: {formula}
    # Params: {json.dumps(params, ensure_ascii=False) if params else '{}'}
    # TODO: 实现具体计算逻辑
    result = 0.0
"""
        return SkillResult(success=True, data={
            'template_id': template.get('template_id'),
            'params': params or {},
            'formula': formula,
            'python_code': python_code
        })

    def skill_channel2_reasoning(self, risk_gap: str, data_summary: Dict = None) -> SkillResult:
        """通道2推理：LLM生成新dsl+新python"""
        prompt = self._build_channel2_prompt(risk_gap, data_summary)
        response = self.llm_client.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=8000
        )
        result = self._parse_channel2_response(response)
        if result:
            logger.info(f"  通道2推理成功: {len(result)}个新模板")
            return SkillResult(success=True, data=result)
        else:
            return SkillResult(success=False, error="通道2推理结果解析失败", retryable=False)

    def _generate_feature_code(self, template: Dict, params: Dict, formula: str) -> str:
        """生成单个特征的python计算代码"""
        template_id = template.get('template_id', 'unknown')
        category = template.get('category', 'unknown')
        param_str = json.dumps(params, ensure_ascii=False) if params else '{}'

        code = f"""
    # [{template_id}] {template.get('business_meaning', '')}
    # DSL: {formula}
    # Params: {param_str}
    def _calc_{template_id.replace('-', '_')}(self, data: Dict, apply_time_dt: datetime) -> float:
        \"\"\"计算 {template.get('business_meaning', '')}\"\"\"
        try:
            # TODO: 根据具体业务逻辑实现
            return 0.0
        except Exception as e:
            return 0.0
"""
        return code

    # ========== Channel 2 Prompt ==========

    def _build_channel2_prompt(self, risk_gap: str, data_summary: Dict = None) -> str:
        """构建通道2推理的prompt"""
        prompt = f"""# 任务：推理新的特征模板（通道2）

当前通道1模板库无法覆盖以下风险模式或特征需求：

{risk_gap}

## 要求

1. 设计新的DSL模板，包含：template_name、parameter_space、formula_template、business_meaning
2. 为每个新模板生成对应的python函数代码（有防穿越机制）
3. 确保新模板不与通道1现有模板重复
4. dsl描述写入python函数注释头部

## 输出格式

请返回JSON数组，每个元素包含：
- template_id: 新编码（如T026）
- template_name: 模板名称
- parameter_space: 参数空间字典
- formula_template: 公式模板（含{{param}}占位符）
- business_meaning: 业务含义
- python_code: 对应的python函数完整代码

```json
[
  {{
    "template_id": "T026",
    "template_name": "...",
    ...
  }}
]
```
"""
        return prompt

    def _parse_channel2_response(self, response: str) -> List[Dict]:
        """解析通道2的LLM响应"""
        # 尝试提取JSON
        if '```json' in response:
            start = response.find('```json') + 7
            end = response.find('```', start)
            if end > start:
                response = response[start:end].strip()
        elif '[' in response and ']' in response:
            start = response.find('[')
            end = response.rfind(']') + 1
            response = response[start:end]

        try:
            result = json.loads(response)
            if isinstance(result, list):
                return result
            elif isinstance(result, dict):
                return [result]
        except json.JSONDecodeError:
            logger.warning("  通道2响应JSON解析失败")
            return []

        return []

    # ========== 通道2 → 通道1 晋升 ==========

    def promote_template(self, new_template: Dict) -> bool:
        """将通道2新模板晋升到通道1

        流程:
        1. 校验新模板完整性
        2. AUTO_PROMOTE=true → 自动晋升
        3. AUTO_PROMOTE=false → 打印信息，等待人工确认
        4. 晋升: 更新 PostgreSQL 模板状态 + 追加 channel1_calculators.py 函数

        Args:
            new_template: 通道2推理出的新模板（含template_id, template_name,
                          parameter_space, dsl, python_function, python_code等）

        Returns:
            是否成功晋升
        """
        required_fields = ['template_id', 'template_name', 'parameter_space', 'dsl', 'python_function']
        for field in required_fields:
            if field not in new_template:
                logger.warning(f"  晋升失败: 缺少字段 {field}")
                return False

        tid = new_template['template_id']
        name = new_template['template_name']
        logger.info(f"  → 准备晋升通道2模板 {tid}({name})")

        # 校验template_id格式
        if not tid.startswith('T') or not tid[1:].isdigit():
            logger.warning(f"  晋升失败: template_id格式错误 {tid}")
            return False

        if not self.auto_promote:
            logger.info(f"  ⚠️  需人工确认晋升: {tid}({name})")
            logger.info(f"     DSL: {new_template.get('dsl', '')}")
            logger.info(f"     参数: {json.dumps(new_template.get('parameter_space', {}), ensure_ascii=False)[:200]}")
            logger.info(f"     设置 AUTO_PROMOTE_TEMPLATE=true 可自动晋升")
            # 即使不自动晋升，也进入 PostgreSQL pending 队列供后续审核
            new_template['_promotion_status'] = 'pending_approval'
            self.promoted_templates.append(new_template)
            self._save_channel2_pending(new_template)
            return False

        return self._do_promote(new_template)

    def _do_promote(self, new_template: Dict) -> bool:
        """执行晋升操作：更新 PostgreSQL 模板库并追加模板函数。"""
        tid = new_template['template_id']
        db = SessionLocal()
        try:
            row = upsert_template_from_payload(
                db,
                new_template,
                status=PENDING_STATUS,
                source_channel=2,
                source='channel2',
                commit=True,
            )
            row = approve_template(db, row.template_id, reviewer='feature_development_agent')
            append_template_python_code(row)

            entry = template_to_channel1_item(row)
            entry['_promotion_status'] = 'promoted'
            self.promoted_templates.append(entry)

            logger.info(f"  ✅ 通道2模板 {tid} 已晋升为通道1")
            return True
        except Exception as e:
            logger.warning(f"  晋升模板失败: {tid}, error={e}")
            return False
        finally:
            db.close()

    def _get_current_round(self) -> int:
        """获取当前评估轮次"""
        feedback_dir = 'outputs/evaluation'
        if not os.path.exists(feedback_dir):
            return 0
        existing = [f for f in os.listdir(feedback_dir)
                    if f.startswith('iv_psi_feedback_r') and f.endswith('.json')]
        max_r = 0
        for f in existing:
            try:
                r = int(f.replace('iv_psi_feedback_r', '').replace('.json', ''))
                max_r = max(max_r, r)
            except:
                pass
        return max_r

    def _save_channel2_pending(self, template: Dict):
        """保存待审批的通道2模板到 PostgreSQL。"""
        db = SessionLocal()
        try:
            row = upsert_template_from_payload(
                db,
                template,
                status=PENDING_STATUS,
                source_channel=2,
                source='channel2',
                commit=True,
            )
            logger.info(f"  待审批模板已保存到 PostgreSQL: {row.template_id}")
        finally:
            db.close()

    # ========== 三阶段设计（复用stepwise_framework_design） ==========

    def run_design_phase(self) -> bool:
        """通道1+通道2特征设计流程

        流程:
        1. 加载IV/PSI反馈 + APP分类缓存
        2. 通道1：召回所有模板 → 填充参数 → 用LLM匹配业务上下文生成特征列表
        3. 通道2（可选）：LLM推理新模板（通道1覆盖不了的模式）
        """
        logger.info("  [阶段1/2] 通道1模板展开 + 通道2补充推理...")

        # 注入IV/PSI反馈
        fb_section = self._build_feedback_prompt_section()
        if fb_section:
            logger.info(f"  IV/PSI反馈已注入（{len(self.iv_psi_feedback.get('summary_patterns', []))}条总结）")

        try:
            # ---- 通道1：模板召回 ----
            logger.info("  召回通道1模板...")
            recall_result = self.skill_template_recall()
            if not recall_result.success or not recall_result.data:
                logger.warning("  通道1模板召回为空")
                return False
            templates = recall_result.data
            logger.info(f"  召回 {len(templates)} 个通道1模板")

            # ---- 通道1：参数填充 ----
            all_filled = []
            for tmpl in templates:
                fill_result = self.skill_param_fill(tmpl)
                if fill_result.success:
                    all_filled.extend(fill_result.data)
            logger.info(f"  参数填充完成，共 {len(all_filled)} 个参数组合")

            # ---- 通道1：LLM匹配业务上下文生成特征 ----
            logger.info("  LLM匹配业务上下文，生成特征列表...")
            features = self._channel1_generate_features(templates, all_filled, fb_section)
            if not features:
                logger.warning("  通道1未生成特征")
                return False

            features = self._ensure_feature_metadata(features, strict=False)
            self.features = features
            self.feature_doc = {'features': features}
            logger.info(f"  通道1生成 {len(features)} 个特征")

            # ---- 通道2：补充推理 ----
            logger.info("  通道2推理：检查是否需要补充新模板...")
            channel2_features = self._channel2_supplement(fb_section)
            if channel2_features:
                self.features.extend(channel2_features)
                self.feature_doc = {'features': self.features}
                logger.info(f"  通道2补充 {len(channel2_features)} 个特征")

            # ---- 保存特征设计文档 ----
            self.feature_doc = {'features': self.features}
            os.makedirs(os.path.dirname(self.feature_design_doc_path), exist_ok=True)
            with open(self.feature_design_doc_path, 'w', encoding='utf-8') as f:
                json.dump(self.feature_doc, f, ensure_ascii=False, indent=2)
            logger.info(f"  特征设计文档已保存: {self.feature_design_doc_path}")

            return True

        except Exception as e:
            logger.error(f"  设计阶段失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _channel1_generate_features(self, templates: List[Dict], filled_params: List[Dict],
                                     feedback_section: str) -> List[Dict]:
        """用LLM将通道1模板+确定参数组合映射到业务上下文，生成特征列表

        相比旧版（LLM自己设计参数），现在 filled_params 已包含确定性的参数组合。
        LLM的职责转变为：
        1. 为每个参数组合添加业务解释(business_explanation_cn, design_reason)
        2. 为每个参数组合生成合适的特征名
        3. 筛选掉无业务意义的组合
        4. 确保数据源命名正确
        """
        # 构建模板+参数组合摘要
        tmpl_param_pairs = []
        for tmpl in templates:
            tid = tmpl.get('template_id', '')
            # 找到这个模板对应的 filled_params
            matching = [fp for fp in filled_params if fp.get('template_id') == tid]
            if not matching:
                continue

            tmpl_param_pairs.append({
                'tid': tid,
                'name': tmpl.get('template_name', ''),
                'name_cn': tmpl.get('template_name_cn', ''),
                'dimension': tmpl.get('dimension', ''),
                'dsl': tmpl.get('dsl', ''),
                'dsl_description': tmpl.get('dsl_description', ''),
                'param_combinations': [fp['params'] for fp in matching],
            })

        has_feedback = "有" if feedback_section else "无"
        prompt = f"""# 任务：参数组合 → 业务特征命名与解释

## 背景
你是印尼现金贷风控特征工程师。以下是通道1模板及其**已经填充好的确定性参数组合**。

## 你的任务
你的职责是**精简化**：为每个参数组合生成业务特征定义（特征名+业务解释+设计理由）。
不需要设计参数值 — 参数已经由确定性规则生成。

### 具体工作
1. 为每个参数组合生成：feature_name, business_explanation_cn, design_reason, expected_risk_correlation
2. 筛选掉明显无业务意义的组合（如FDC inquiry加cond过滤）
3. 适当合并冗余的参数组合（只保留业务差异大的）
4. 在param_combinations中选择最有业务价值的2-3个组合

## 数据源说明
- **applist**: 用户手机安装的应用列表，含安装时间(inTime,毫秒时间戳)
  **重要: applist 数据项不含 category/app_category 字段**，如需按类别过滤必须用 `allowed_categories` 参数
- **fdc_pinjaman**: 征信贷款记录(pinjaman数组)，含 tipe_pinjaman, nilai_pendanaan, id_penyelenggara, status_pinjaman, kualitas_pinjaman 等
- **fdc_inquiry**: 征信查询统计(history_inquiry.statistic 预聚合值)，不支持 cond 过滤
- **base**: 用户基本信息(salary, birthday, workYears, gender, marita, children, job 等)

## **CRITICAL: 数据源命名规则**（违反将导致特征恒为0）
- params中的source/source_a/source_b取值必须精确：
  - 绝对禁止使用泛化的 'fdc'
  - 必须是 'fdc_inquiry' 或 'fdc_pinjaman' 或 'applist' 或 'base'
- data_source 字段同理

## 防穿越约束
- 所有数据过滤基于applyTime（申请时间），不能使用当前时间

## IV/PSI历史反馈（{has_feedback}）
{feedback_section}

## 通道1模板+参数组合摘要
```json
{json.dumps(tmpl_param_pairs, ensure_ascii=False, indent=2)}
```

## 输出要求
返回JSON数组，每条特征包含：

```json
[
  {{
    "feature_name": "英文特征名（如 count_fdc_inquiry_30d）",
    "feature_type": "模板类型名",
    "data_source": "数据源（如 fdc_inquiry）",
    "template_id": "模板ID",
    "params": {{"参数组合（保持原始参数不变，template_id对应参数映射由下游处理）"}},
    "business_explanation_cn": "中文业务解释",
    "design_reason": "设计理由",
    "expected_risk_correlation": "positive/negative"
  }}
]
```

**重要要求**:
1. 每个模板最多选2个最有业务价值的参数组合
2. 特征数量控制在 20-30 个左右（精选最有价值的）
3. feature_name 必须包含数据源和窗口信息，如 count_fdc_inquiry_30d
4. params 保留原始参数值（不要修改）
5. 每条特征都需要中文业务解释和设计理由
6. 确保数据源命名精确（无泛化 fdc）
"""
        response = self.llm_client.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=12000
        )

        # 提取JSON
        features = self._extract_json_array(response)
        if features:
            logger.info(f"  LLM业务化完成: {len(features)} 个特征")
            # 后处理：修复泛化的 fdc 为具体数据源名
            for feat in features:
                self._fix_feature_source(feat)
            valid_fdc = sum(1 for f in features if
                            any(f.get('params', {}).get(k, '').startswith('fdc_')
                                for k in ['source', 'source_a', 'source_b']))
            logger.info(f"  后处理完成，有效FDC特征: {valid_fdc}")

            # 语义校验：丢弃无意义的特征定义
            before = len(features)
            features = self._validate_feature_semantics(features)
            dropped = before - len(features)
            if dropped > 0:
                logger.info(f"  语义校验丢弃 {dropped} 个无意义特征")
            return features

        logger.warning("  LLM业务化失败，降级到参数组合直接生成")
        features = self._fallback_generate_features(templates, filled_params)
        # 降级路径也需要语义校验
        before = len(features)
        features = self._validate_feature_semantics(features)
        dropped = before - len(features)
        if dropped > 0:
            logger.info(f"  降级特征语义校验丢弃 {dropped} 个无意义特征")
        return features

    def _ensure_feature_metadata(self, features: List[Dict], strict: bool = False) -> List[Dict]:
        """Normalize and validate metadata needed by downstream reports.

        strict=True is used for free-form Channel 2 features: if the LLM cannot
        explain where the feature comes from and how it is calculated, the
        feature is not reportable and should not enter the mining result.
        """
        normalized = []
        required_fields = ['feature_name', 'data_source', 'calculation_logic']

        for feat in features:
            self._fix_feature_source(feat)
            params = feat.get('params') or {}

            if not feat.get('data_source'):
                feat['data_source'] = (
                    params.get('source')
                    or params.get('source_a')
                    or params.get('field_set')
                    or ''
                )

            if not feat.get('calculation_logic'):
                feat['calculation_logic'] = (
                    feat.get('formula_template')
                    or feat.get('dsl')
                    or feat.get('formula')
                    or ''
                )

            missing = [field for field in required_fields if not feat.get(field)]
            if strict and missing:
                logger.warning(
                    f"  ⚠ 通道2特征 '{feat.get('feature_name', 'unknown')}' "
                    f"缺少报告必需字段: {', '.join(missing)}，已丢弃"
                )
                continue

            normalized.append(feat)

        return normalized

    def _validate_feature_semantics(self, features: List[Dict]) -> List[Dict]:
        """语义校验：检测并丢弃无业务意义的特征定义

        常见无意义模式：
        1. T014 cross_discrepancy 中，参数 src+field 对比语义不兼容的字段
           （如数字编码 vs 文字描述，天然永远不会相等）
        2. 包含无效 cond/filter 条件的特征
        3. 不兼容的数据源组合

        Args:
            features: 特征定义列表

        Returns:
            过滤后的特征列表
        """
        valid_features = []

        for feat in features:
            tid = feat.get('template_id', '')
            fname = feat.get('feature_name', 'unknown')
            params = feat.get('params', {})
            reasons = []

            # ---- 规则1: T014 field_pairs_config 语义检查 ----
            if tid == 'T014':
                field_pairs = params.get('field_pairs_config', [])
                if isinstance(field_pairs, list) and len(field_pairs) >= 2:
                    # 检查是否有语义不兼容的对
                    for i, pair in enumerate(field_pairs):
                        fields_in_pair = []
                        if pair.get('src') and pair.get('field'):
                            fields_in_pair.append((pair['src'], pair['field']))
                        if pair.get('source_a'):
                            fields_in_pair.append(('path', pair['source_a']))
                        if pair.get('source_b'):
                            fields_in_pair.append(('path', pair['source_b']))

                        if len(fields_in_pair) >= 2:
                            # 检查组内是否有明显的语义不兼容
                            types = []
                            for src, f in fields_in_pair:
                                if src == 'base' and f == 'job':
                                    types.append('numeric_code')
                                elif src == 'fdc_pinjaman' and f == 'tipe_pinjaman':
                                    types.append('text_description')
                                else:
                                    types.append('other')

                            if 'numeric_code' in types and 'text_description' in types:
                                reasons.append(
                                    f"T014字段对语义不兼容: "
                                    f"{fields_in_pair[0][0]}.{fields_in_pair[0][1]} "
                                    f"(数字编码) vs "
                                    f"{fields_in_pair[1][0]}.{fields_in_pair[1][1]} "
                                    f"(文字描述)，天然不会相等")

            # ---- 规则2: cond 条件与实际可用数据源不匹配 ----
            cond = params.get('cond', {})
            source = params.get('source', '')
            if cond and source == 'fdc_inquiry':
                # fdc_inquiry 只有预聚合统计，不支持 cond 过滤
                reasons.append(
                    f"cond={{...}} 应用于 fdc_inquiry（预聚合统计，不支持cond过滤）")

            # ---- 规则3: 降级特征中 source 为泛化 'fdc' ----
            if feat.get('data_source') == 'fdc' or params.get('source') == 'fdc':
                # 降级构建的 'fdc' 未被正确替换
                reasons.append("data_source='fdc'未被替换为具体源名（fdc_inquiry或fdc_pinjaman）")

            # ---- 记录决策 ----
            if reasons:
                logger.warning(f"  ⚠ 特征 '{fname}' 语义校验不通过: {'; '.join(reasons)}")
                continue

            valid_features.append(feat)

        return valid_features

    def _fix_feature_source(self, feat: Dict):
        """后处理：修复特征设计文档中泛化的 source 命名

        - 'fdc' → 'fdc_inquiry'（如果 cond 不含 pinjaman 字段）或 'fdc_pinjaman'
        - applist 的 category cond → 提示（在组合时处理）
        - source_a/source_b 的 'fdc' 根据 overlap 模板的配对自动判断
        """
        params = feat.get('params', {})
        if not params:
            return

        cond = params.get('cond', {})
        template_id = feat.get('template_id', '')
        pinjaman_fields = {'tipe_pinjaman', 'kualitas_pinjaman', 'status_pinjaman',
                           'nama_platform', 'id_penyelenggara', 'nilai_pendanaan'}
        source_keys = ['source', 'source_a', 'source_b', 'data_source']
        for sk in source_keys:
            v = params.get(sk) or feat.get(sk)
            if v != 'fdc':
                continue

            # source_a/source_b: 根据模板类型和配对数据源判断
            if sk in ('source_a', 'source_b'):
                if template_id == 'T006':
                    # overlap: applist vs fdc_pinjaman 或 fdc_pinjaman vs fdc_inquiry
                    other_key = 'source_b' if sk == 'source_a' else 'source_a'
                    other_val = params.get(other_key, '')
                    if other_val in ('applist', 'base'):
                        # 另一个是 applist/base → 这个应该是 fdc_pinjaman（贷款机构数据）
                        replacement = 'fdc_pinjaman'
                    elif other_val == 'fdc_inquiry':
                        replacement = 'fdc_inquiry'
                    else:
                        replacement = 'fdc_inquiry'
                else:
                    replacement = 'fdc_inquiry'
            elif cond and any(k in cond for k in pinjaman_fields):
                replacement = 'fdc_pinjaman'
            else:
                replacement = 'fdc_inquiry'

            # 更新 params 中的 source
            if sk in params:
                params[sk] = replacement
            # 更新 feat 层的 data_source
            if feat.get('data_source') == 'fdc':
                feat['data_source'] = replacement

    def _channel2_supplement(self, feedback_section: str) -> List[Dict]:
        """通道2推理：判断是否需要补充新模板"""
        # 检查是否有充分的通道1模板
        ch1_templates = self.skill_template_recall().data or []
        has_templates = len(ch1_templates) >= 15

        prompt = f"""# 通道2补充推理

## 背景
通道1已有{len(ch1_templates)}个业务无关DSL模板（5维度×3复杂度）。
请判断对于印尼现金贷风控，是否需要补充不在通道1中的新模板。

## 通道1已有维度
- volume: 存量特征（count, distinct_count, decayed_sum）
- structure: 结构特征（proportion, concentration, overlap）
- change: 变化特征（period_compare, trend, spike）
- position: 定位特征（percentile, deviation, anomaly）
- consistency: 一致性特征（declared_vs_actual, cross_discrepancy, identity_cluster）

## IV/PSI历史反馈
{feedback_section}

## 输出要求
如果不需要补充新模板，返回空数组 []。
如果需要，返回JSON数组：

```json
[
  {{
    "feature_name": "特征名",
    "feature_type": "类型",
    "data_source": "数据源",
    "template_id": "T999",
    "params": {{}},
    "business_explanation_cn": "业务解释",
    "design_reason": "为什么通道1不满足",
    "calculation_logic": "计算逻辑",
    "expected_risk_correlation": "positive/negative"
  }}
]
```

最多返回3个通道2补充特征。
"""
        response = self.llm_client.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=6000
        )

        features = self._extract_json_array(response)
        if features:
            features = self._ensure_feature_metadata(features, strict=True)
            features = self._validate_feature_semantics(features)
        return features or []

    def _extract_json_array(self, response: str) -> List[Dict]:
        """从LLM响应中提取JSON数组"""
        # 尝试 json code block
        if '```json' in response:
            start = response.find('```json') + 7
            end = response.find('```', start)
            if end > start:
                response = response[start:end].strip()
        elif '[' in response:
            start = response.find('[')
            end = response.rfind(']') + 1
            if end > start:
                response = response[start:end]

        try:
            result = json.loads(response)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

        return []

    def _fallback_generate_features(self, templates: List[Dict], filled_params: List[Dict]) -> List[Dict]:
        """当LLM返回解析失败时，根据参数组合直接生成特征"""
        features = []
        used_sources = ['applist', 'fdc', 'base']
        source_idx = 0
        for fp in filled_params:
            tid = fp.get('template_id', 'unknown')
            params = fp.get('params', {})
            tmpl = next((t for t in templates if t.get('template_id') == tid), {})
            tmpl_name = tmpl.get('template_name', tid)
            source = used_sources[source_idx % len(used_sources)]
            source_idx += 1

            # 构造特征名
            param_suffix = '_'.join(str(v) for v in params.values() if isinstance(v, (str, int, float)))
            base_name = f"{tmpl_name}_{source}"
            if param_suffix:
                base_name += f"_{param_suffix}"
            base_name = base_name.replace(' ', '_').replace('.', '_').replace('-', '_').lower()

            # 去重
            existing_names = {f['feature_name'] for f in features}
            if base_name in existing_names:
                continue

            features.append({
                'feature_name': base_name,
                'feature_type': tmpl_name,
                'data_source': source,
                'template_id': tid,
                'params': params,
                'business_explanation_cn': f"基于{tmpl.get('template_name_cn', tmpl_name)}模板的{source}特征",
                'design_reason': '通道1模板参数组合自动生成',
                'calculation_logic': tmpl.get('dsl', ''),
                'expected_risk_correlation': 'positive',
            })

            if len(features) >= 30:
                break

        return features

    def generate_code(self) -> str:
        """生成完整特征计算代码

        Channel 1 特征：确定性代码组合（由compose_code_deterministic生成）
        Channel 2 特征：降级到LLM生成或占位
        """
        logger.info("  生成特征计算代码...")

        # 输入特征设计文档
        if not self.features and self.feature_doc:
            self.features = self.feature_doc.get('features', [])

        if not self.features:
            logger.warning("  无特征需生成代码")
            return ""

        # 分离 Channel 1 和 Channel 2
        ch1_features = [f for f in self.features
                        if f.get('template_id', '').startswith('T') and f['template_id'] != 'T999']
        ch2_features = [f for f in self.features
                        if not f.get('template_id', '').startswith('T') or f['template_id'] == 'T999']

        logger.info(f"  通道1特征: {len(ch1_features)}个（确定性组合）, 通道2特征: {len(ch2_features)}个（LLM/占位）")

        # 通道1：确定性组合
        code = self.compose_code_deterministic(ch1_features, ch2_features)
        if not code:
            logger.warning("  确定性组合失败，降级到LLM生成")
            # 降级到原有LLM生成流程
            applist = [f for f in self.features if f['data_source'] == 'applist']
            fdc = [f for f in self.features if f['data_source'] == 'fdc']
            base = [f for f in self.features if f['data_source'] == 'base']
            prompt = self._build_code_generation_prompt(applist, fdc, base)
            response = self.llm_client.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=16000
            )
            code = self._extract_code(response)

        if code:
            self.generated_code = code
            logger.info(f"  代码生成成功: {len(code)}字符, {len(code.splitlines())}行")
        else:
            logger.warning("  代码生成失败")
            self.generated_code = None

        return self.generated_code

    def _get_template_by_id(self, template_id: str) -> Optional[Dict]:
        """根据template_id查找通道1模板"""
        db = SessionLocal()
        try:
            tmpl = get_template(db, template_id)
            if tmpl:
                return template_to_channel1_item(tmpl)
        except Exception as e:
            logger.warning(f"  查找模板失败: {e}")
        finally:
            db.close()
        return None

    def _get_function_by_name(self, func_name: str):
        """根据函数名从 channel1_calculators 导入并返回函数对象"""
        try:
            import importlib
            mod = importlib.import_module('outputs.feature_code.channel1_calculators')
            return getattr(mod, func_name, None)
        except Exception:
            try:
                import sys
                sys.path.insert(0, 'outputs/feature_code')
                mod = importlib.import_module('channel1_calculators')
                return getattr(mod, func_name, None)
            except Exception:
                return None

    def _params_to_kwargs(self, feat: Dict, params: Dict,
                          template_id: str = None,
                          override_func_name: str = None) -> Dict:
        """将设计文档的params映射为模板函数的关键字参数

        设计文档用 "source" 表示数据源，但 calc_count 等函数用 "field_set"。
        此函数处理命名差异。
        """
        # 参数字段名映射（设计文档 → 模板函数）
        param_mapping = {
            'window': 'window_days',
            'threshold': 'threshold',
            'method': 'method',
            'decay_func': 'decay_func',
            'decay_rate': 'decay_rate',
            'min_denominator': 'min_denominator',
            'dedup_field': 'dedup_field',
            'category_field': 'category_field',
            'declared_field': 'declared_field',
            'actual_field': 'actual_field',
            'source_a': 'source_a',
            'field_a': 'field_a',
            'source_b': 'source_b',
            'field_b': 'field_b',
            'short_window': 'short_window',
            'long_window': 'long_window',
            'identity_field': 'identity_field',
            'shared_field': 'shared_field',
            'min_threshold': 'min_threshold',
            'windows': 'windows',
            'feature_dimensions': 'feature_dimensions',
        }

        kwargs = {}
        for k, v in params.items():
            mapped_key = param_mapping.get(k, k)
            kwargs[mapped_key] = v

        # 特殊处理：设计文档的 'source' → 模板函数的 'field_set'
        if 'source' in kwargs and template_id:
            tmpl = self._get_template_by_id(template_id) if not template_id.startswith('T999') else None
            if tmpl:
                # 使用 override_func_name（如果提供了）来检查函数签名
                # 因为模板的 python_function 可能已被替换（如 calc_proportion → calc_proportion_by_category）
                actual_func_name = override_func_name or tmpl.get('python_function', '')
                # 检查该函数是否接受 'field_set' 参数
                # 通过导入函数对象并检查其签名来判断
                func_obj = self._get_function_by_name(actual_func_name)
                if func_obj is not None:
                    import inspect
                    sig = inspect.signature(func_obj)
                    has_field_set = 'field_set' in sig.parameters
                    has_source_param = 'source' in sig.parameters
                    if has_source_param:
                        # 函数直接接受 source 参数，保留 kwargs['source']
                        pass
                    elif not has_field_set:
                        kwargs.pop('source', None)
                    else:
                        kwargs['field_set'] = kwargs.pop('source')
                elif func_name in ('calc_percentile', 'calc_deviation', 'calc_anomaly',
                                   'calc_declared_vs_actual', 'calc_cross_discrepancy',
                                   'calc_identity_cluster'):
                    kwargs.pop('source', None)
                else:
                    # source → field_set (fallback)
                    kwargs['field_set'] = kwargs.pop('source')
            else:
                # 未知模板ID，尝试猜: source → field_set
                if 'source' in kwargs:
                    kwargs['field_set'] = kwargs.pop('source')

        return kwargs

    def compose_code_deterministic(self, ch1_features: List[Dict],
                                    ch2_features: List[Dict]) -> Optional[str]:
        """确定性代码组合：根据特征设计文档+模板库直接生成Python源码

        Channel 1 特征：直接 emit 模板函数调用代码
        Channel 2 特征：占位返回 0.0

        Returns:
            完整的 Python 源码字符串，失败时返回 None
        """
        if not ch1_features and not ch2_features:
            return None

        # 收集需要用到的模板函数
        used_functions = set()
        feat_func_map = {}  # {feature_name: (func_name, kwargs)}

        for feat in ch1_features:
            name = feat['feature_name']
            tid = feat.get('template_id', '')
            params = feat.get('params', {})

            tmpl = self._get_template_by_id(tid)
            if not tmpl:
                logger.warning(f"  跳过特征 {name}: 模板 {tid} 未找到")
                continue

            if self._is_inline_template(tmpl, tid):
                inline_line = self._compose_inline_derived_line(name, params)
                feat_func_map[name] = (None, {}, feat.get('business_explanation_cn', ''), inline_line)
                logger.info(f"    {name}: inline derived arithmetic")
                continue

            func_name = tmpl.get('python_function', 'calc_count')

            # 特殊处理：当设计文档包含 allowed_categories 参数时，
            # T004(proportion) 自动切换到 calc_proportion_by_category
            # T005(concentration) 有自己的 _by_category 版本，但已通过 template_id 自动匹配
            if func_name == 'calc_proportion' and 'allowed_categories' in params:
                func_name = 'calc_proportion_by_category'
            # T005 concentration 的 _by_category 版本不需要 allowed_categories 参数
            # 它通过 category_cache 自行计算所有类别的集中度

            if func_name:
                used_functions.add(func_name)

            kwargs = self._params_to_kwargs(feat, params, tid, override_func_name=func_name)
            feat_func_map[name] = (func_name, kwargs, feat.get('business_explanation_cn', ''), None)
            logger.info(f"    {name}: {func_name}({kwargs})")

        # 构建代码
        lines = []
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        lines.append('"""')
        lines.append(f'Feature Calculator v3 - 确定性组合生成')
        lines.append(f'生成时间: {now_str}')
        lines.append(f'通道1特征: {len(ch1_features)}个, 通道2特征: {len(ch2_features)}个')
        lines.append('')
        lines.append('计算逻辑说明：')
        lines.append('- 通道1特征：调用 channel1_calculators 的模板函数')
        lines.append('- 通道2特征：暂为占位符（0.0），需后续实现')
        lines.append('"""')
        lines.append('')
        lines.append('import math')
        lines.append('import os')
        lines.append('import sys')
        lines.append('import json')
        lines.append('from datetime import datetime')
        lines.append('from typing import Dict, List, Optional')
        lines.append('')

        # 确保导入路径
        lines.append('_ch1_dir = os.path.dirname(os.path.abspath(__file__))')
        lines.append('if _ch1_dir not in sys.path:')
        lines.append('    sys.path.insert(0, _ch1_dir)')
        lines.append('')

        # 导入模板函数
        func_imports = sorted(used_functions)
        lines.append('from channel1_calculators import (')
        for i, f in enumerate(func_imports):
            comma = ',' if i < len(func_imports) - 1 else ','
            lines.append(f'    {f}{comma}')
        lines.append(')')
        lines.append('')

        # FeatureCalculator 类定义
        lines.append('')
        lines.append('')
        lines.append('class FeatureCalculator:')
        lines.append('    """基于通道1模板函数的特征计算器（确定性组合）"""')
        lines.append('')
        lines.append('    def __init__(self, app_category_cache=None):')
        lines.append('        self.app_category_cache = app_category_cache or {}')
        lines.append('        self.gambling_packages = {pkg for pkg, info in self.app_category_cache.items()')
        lines.append('                                   if info.get(\'category\') == \'gambling\'}')
        lines.append('        self.loan_packages = {pkg for pkg, info in self.app_category_cache.items()')
        lines.append('                               if info.get(\'category\') in (\'cash_loan\', \'fintech_lending\')}')
        lines.append('')
        lines.append('    def _get_apply_time(self, data):')
        lines.append('        return data.get(\'applyTime\') or data.get(\'params\', {}).get(\'base\', {}).get(\'applyTime\', 0)')
        lines.append('')
        lines.append('    def calculate_all(self, data, apply_time=None) -> dict:')
        lines.append('        if apply_time is None:')
        lines.append('            apply_time = self._get_apply_time(data)')
        lines.append('        if apply_time == 0:')
        lines.append('            return {}')
        lines.append('')
        lines.append('        apply_dt = datetime.fromtimestamp(apply_time / 1000)')
        lines.append('')
        lines.append('        params = data.get(\'params\', {})')
        lines.append('        fdc = params.get(\'FDC\', {})')
        lines.append('')

        # 为每个通道1特征 emit 模板函数调用
        ch1_vars = []  # 按顺序记录变量名
        for feat in ch1_features:
            name = feat['feature_name']
            if name not in feat_func_map:
                continue

            func_name, kwargs, biz_explain_cn, inline_line = feat_func_map[name]
            ch1_vars.append(name)

            if inline_line:
                lines.append(f'        # {name}: {biz_explain_cn}')
                lines.append(inline_line)
                lines.append('')
                continue

            # 构建函数调用参数列表
            # 获取函数签名，用于过滤无效参数
            func_obj = self._get_function_by_name(func_name)
            valid_params = None
            accept_data = True
            accept_apply_dt = True
            if func_obj is not None:
                import inspect
                sig = inspect.signature(func_obj)
                valid_params = set(sig.parameters.keys())
                accept_data = 'data' in valid_params
                accept_apply_dt = 'apply_time_dt' in valid_params
                # 过滤出 kwargs 中函数接受的参数
                valid_kwargs = valid_params - {'data', 'args', 'kwargs'}

            call_parts = ['data'] if accept_data else []

            # 对 calc_proportion_by_category 和 calc_concentration_by_category 的特殊处理
            if func_name in ('calc_proportion_by_category', 'calc_concentration_by_category'):
                # 注入 app_category_cache
                pass  # category_cache 会在后面添加

            for k, v in kwargs.items():
                # 跳过函数不接受的参数（签名字段校验）
                if valid_kwargs and k not in valid_kwargs:
                    continue
                # category-based 函数不需要 category_field/field_set
                if func_name in ('calc_proportion_by_category',) and k in ('field_set', 'category_field'):
                    continue
                # fdc_inquiry 的 cond 参数会过滤掉虚拟记录，跳过
                if k == 'cond' and any(cp.startswith("field_set='fdc_inquiry'") or cp.startswith('field_set="fdc_inquiry"') for cp in call_parts):
                    continue
                if k == 'field_set' and isinstance(v, str):
                    call_parts.append(f"field_set='{v}'")
                elif isinstance(v, str):
                    # 使用 repr 安全处理可能含特殊字符的字符串
                    call_parts.append(f"{k}={repr(v)}")
                elif isinstance(v, list):
                    call_parts.append(f"{k}={repr(v)}")
                elif isinstance(v, set):
                    call_parts.append(f"{k}={repr(v)}")
                elif isinstance(v, bool):
                    call_parts.append(f"{k}={str(v)}")
                elif v is None:
                    call_parts.append(f"{k}=None")
                else:
                    call_parts.append(f"{k}={v}")

            if accept_apply_dt:
                call_parts.append('apply_time_dt=apply_dt')

            # 对 category-based 函数，注入 category_cache=self.app_category_cache
            if func_name in ('calc_proportion_by_category', 'calc_concentration_by_category'):
                # 确保 allowed_categories 是集合类型（将列表转为集合文字）
                for i, cp in enumerate(call_parts):
                    if cp.startswith('allowed_categories='):
                        val = cp.split('=', 1)[1]
                        # 如果值是列表 ['x', 'y'] → 转为 {'x', 'y'}
                        if val.startswith('[') and val.endswith(']'):
                            inner = val[1:-1]
                            call_parts[i] = f"allowed_categories={{{inner}}}"
                        # 如果值是字符串，转为集合
                        elif val.startswith("'") or val.startswith('"'):
                            call_parts[i] = f"allowed_categories={{{val}}}"
                        break
                call_parts.append('category_cache=self.app_category_cache')

            call_str = ', '.join(call_parts)
            # 检查所有必需的参数是否都有默认值或已被提供
            has_required = True
            if func_obj is not None:
                import inspect
                sig = inspect.signature(func_obj)
                provided_names = set()
                for cp in call_parts:
                    if '=' in cp:
                        provided_names.add(cp.split('=')[0])
                    else:
                        # positional arg (like 'data')
                        pass
                for pname, param in sig.parameters.items():
                    if pname == 'data':
                        continue
                    if param.default is inspect.Parameter.empty and pname not in provided_names:
                        has_required = False
                        break

            if not call_str or not has_required:
                # 没有任何有效参数，降级为占位符
                logger.warning(f'    {name}: 无有效参数，降级为占位符')
                lines.append(f'        # {name}: [占位] {biz_explain_cn}')
                lines.append(f'        {name} = 0.0  # 占位（无有效调用参数）')
            else:
                lines.append(f'        # {name}: {biz_explain_cn}')
                lines.append(f'        {name} = {func_name}({call_str})')
            lines.append('')

        # 通道2特征：占位
        for feat in ch2_features:
            name = feat['feature_name']
            ch1_vars.append(name)
            biz = feat.get('business_explanation_cn', '')
            lines.append(f'        # [CH2] {name}: {biz}')
            lines.append(f'        {name} = 0.0  # 通道2占位')
            lines.append('')

        # Return dict
        lines.append('        return {')
        for name in ch1_vars:
            lines.append(f"            '{name}': {name},")
        lines.append('        }')
        lines.append('')

        return '\n'.join(lines)

    def _is_inline_template(self, template: Dict, template_id: str) -> bool:
        return (
            template.get('execution_mode') == 'inline'
            or template.get('requires_external_function') is False
            or template_id == 'T016'
            or template.get('template_name') == 'derived'
            or template.get('python_function') == 'derived_arithmetic'
            or str(template.get('dsl', '')).strip().startswith('derived(')
        )

    def _compose_inline_derived_line(self, feature_name: str, params: Dict) -> str:
        dtype = params.get('derived_type')

        if dtype == 'ratio_density':
            ref = params.get('ref_feature_name', '0.0')
            window = params.get('window', params.get('window_days', 1))
            return f"        {feature_name} = {ref} / {float(window):g} if {ref} > 0 else 0.0"

        if dtype == 'ratio_cross':
            a = params.get('ref_feature_a', '0.0')
            b = params.get('ref_feature_b', '0.0')
            return f"        {feature_name} = {a} / {b} if {b} != 0 else 0.0"

        if dtype == 'weighted_combo':
            a = params.get('ref_feature_a', '0.0')
            b = params.get('ref_feature_b', '0.0')
            weight_a = params.get('weight_a', 1.0)
            weight_b = params.get('weight_b', 1.0)
            return f"        {feature_name} = ({a} * {float(weight_a):g}) * ({b} * {float(weight_b):g})"

        if dtype == 'extended_velocity':
            short_feat = params.get('ref_feature_short', '0.0')
            long_feat = params.get('ref_feature_long', '0.0')
            short_window = params.get('short_window', 1)
            long_window = params.get('long_window', 1)
            return (
                f"        {feature_name} = (({short_feat} / {float(short_window):g}) / "
                f"({long_feat} / {float(long_window):g}) - 1.0) if {long_feat} > 0 else 0.0"
            )

        if dtype == 'squared':
            ref = params.get('ref_feature_name', '0.0')
            return f"        {feature_name} = {ref} ** 2"

        if dtype == 'log_transform':
            ref = params.get('ref_feature_name', '0.0')
            return f"        {feature_name} = math.log({ref} + 1) if {ref} >= 0 else 0.0"

        if dtype == 'difference':
            a = params.get('ref_feature_a', '0.0')
            b = params.get('ref_feature_b', '0.0')
            return f"        {feature_name} = {a} - {b}"

        if dtype == 'is_high':
            ref = params.get('ref_feature_name', '0.0')
            threshold = params.get('threshold', 0.0)
            return f"        {feature_name} = 1.0 if {ref} > {float(threshold):g} else 0.0"

        return f"        {feature_name} = 0.0  # unknown inline derived type: {dtype}"

    def _build_code_generation_prompt(self, applist: List[Dict], fdc: List[Dict], base: List[Dict]) -> str:
        """构建代码生成prompt — 包含精确的字段映射"""
        # 加载APP分类缓存用于包名匹配
        category_packages = self._load_category_packages()

        prompt = f"""# Task: Generate feature calculation code for Indonesian cash loan risk

## CRITICAL: Real Field Names (MUST use these EXACT field names)

### applyTime (Anti-time-travel baseline — NEVER use datetime.now())
- `data.get('applyTime')` or `data['params']['base']['applyTime']`
- Format: Millisecond timestamp

### applist — Access via `data['params']['appList']`
Each app dict has these EXACT keys (verified from real data):
```python
app['inTime']       # Install timestamp (ms) — use for time window filtering
app['upTime']       # Update timestamp (ms)
app['appName']      # App display name
app['appType']      # App type string
app['versionName']  # Version string
app['packageX']     # Package name (e.g., 'com.whatsapp.w4a') — use for category matching
app['versionCode']  # Version code (int)
```

### APP Category Cache (for gambling/loan etc matching)
```python
# Load once in __init__:
# self.app_category_cache = json.load(open('outputs/app_analysis/classification_complete_11850.json'))['classifications']
# Then match by packageX:
# cat = self.app_category_cache.get(app['packageX'], {{}}).get('category', 'unknown')
```

### base — Access via `data['params']['base']`
EXACT field names from real data:
```python
base['salary']         # Monthly income (int) — NOT 'monthly_income'
base['birthday']       # Birthday string 'DD-MM-YYYY' — parse to calculate age
base['workYears']      # Years of work (int) — NOT 'work_tenure'
base['gender']         # Gender (0/1)
base['marita']         # Marital status
base['children']       # Number of children
base['job']            # Job code (string)
base['applyTime']      # Application timestamp (ms)
```

### FDC — Access via `data['params']['FDC']`
REAL field names (verified from raw data):
```python
fdc = data.get('params', {{}}).get('FDC', {{}})

# history_inquiry: DICT (not list)
hi = fdc.get('history_inquiry', {{}})
hi.get('statistic', {{}})                # e.g. {{'360_hari': 40, '30_hari': 23, ...}}
# IMPORTANT: last3DaysInquiry items ONLY have these 3 fields:
hi.get('last3DaysInquiry', [])           # list of {{'hit_by': str, 'jml_data': int, 'tgl_inquiry': 'YYYY-MM-DD HH:MM:SS'}}
#   WARNING: tgl_inquiry has TIME component, e.g. '2026-03-08 15:32:23' — use _date_to_ms_v2()
#   WARNING: NO fields like 'institution_name', 'platform_name', 'loan_purpose', 'type', 'jenis', 'result', 'status'
#   For unique institution/platform counts: use 'hit_by' field (it's the institution name)

# pinjaman: LIST of loan records
pj = fdc.get('pinjaman', [])
# Each loan record key fields:
#   tgl_penyaluran_dana: 'YYYY-MM-DD'  (disburse date — use for time window)
#   tgl_jatuh_tempo_pinjaman: 'YYYY-MM-DD'  (due date)
#   nilai_pendanaan: int  (loan amount)
#   dpd_max: int  (max overdue days)
#   dpd_terakhir: int  (latest overdue days)
#   status_pinjaman: str  (e.g. 'O'=outstanding, 'L'=settled)
#   kualitas_pinjaman_ket: str  (e.g. 'Lancar'=current, 'Macet'=default)
#   sisa_pinjaman_berjalan: int  (outstanding balance)
#   tipe_pinjaman: str  (e.g. 'Multiguna')
# NOTE: dates are 'YYYY-MM-DD' strings, NOT timestamps. Convert: time.mktime(datetime.strptime(d, '%Y-%m-%d').timetuple()) * 1000

pa = fdc.get('platform_aktif', {{}})       # Dict keys: jumlahPlatformAktif(int), platform(list)
```

## Category Package Lists (pre-computed in __init__)
```python
# From app classification cache:
gambling_packages = set()  # packages with category='gambling'
loan_packages = set()      # packages with category='cash_loan' or 'fintech_lending'
known_categories = {{}}    # packageX -> category mapping
```

## Features to Generate

"""
        for group_name, group_features in [('Applist', applist), ('FDC', fdc), ('Base', base)]:
            prompt += f"### {group_name} Features ({len(group_features)}):\n"
            for f in group_features[:20]:
                calc = f.get('calculation_logic', '')[:200]
                prompt += f"- **{f['feature_name']}**: {calc}\n"
            if len(group_features) > 20:
                prompt += f"  ... and {len(group_features) - 20} more\n"
            prompt += "\n"

        prompt += """## Requirements
1. CRITICAL: Use EXACT field names from the data structure reference above — do NOT guess field names
2. CRITICAL: Anti-time-travel — use applyTime, NEVER datetime.now()
3. For applist features: use app_category_cache by packageX to identify gambling/loan apps
4. Handle missing/empty FDC gracefully (return 0.0)
5. Parse birthday to get age: (applyTime_year - birth_year)
6. Use `_safe_div(numerator, denominator)` for division
7. Chinese comments for each feature
8. Output complete `class FeatureCalculator` class ONLY (no example usage)

## IMPORTANT: Use Template Functions from channel1_calculators
Instead of hand-writing every calculation from scratch, you MUST import and call
the pre-built template functions from `channel1_calculators`. This ensures:
- Consistent anti-time-travel logic
- Proper error handling and edge cases
- No duplicate code

Available template functions (import from `channel1_calculators`):
```python
from channel1_calculators import (
    calc_count,          # count(field_set, window, cond)
    calc_distinct_count, # distinct(dedup_field, field_set, window)
    calc_proportion,     # cnt(target) / cnt(total)
    calc_concentration,  # entropy|gini|cv(category_field, field_set, window)
    calc_period_compare, # (short/long) - 1
    calc_trend,          # slope(w1, w2, w3)
    calc_spike,          # max_daily > threshold * avg_daily
    calc_declared_vs_actual,  # ratio(declared / actual)
    calc_decayed_sum,    # decayed_sum(field_set, window, decay_func, decay_rate)
)
```

Usage pattern:
```python
# Instead of writing your own filter + count logic:
result = calc_count(data, 'applist', apply_dt, window_days=7)

# For proportions from applist (using app_category_cache's category filter):
# Use _filter_window + manual filter for category-based proportion

# For FDC inquiry distinct counts:
result = calc_distinct_count(data, 'hit_by', 'fdc_inquiry', apply_dt, window_days=30)

# For period comparison:
result = calc_period_compare(data, 'fdc_inquiry', short_window=7, long_window=90, apply_time_dt=apply_dt)

# For trend:
result = calc_trend(data, 'fdc_pinjaman', windows=[7, 30, 90], apply_time_dt=apply_dt)

# For spike detection:
result = calc_spike(data, 'fdc_inquiry', window_days=30, threshold=3.0, apply_time_dt=apply_dt)

# For declared vs actual comparison:
result = calc_declared_vs_actual(data, 'base.salary', method='ratio')
```

## IMPORTANT: Real Inquiry Field Limitations
The `last3DaysInquiry` items ONLY have these 3 fields:
- `hit_by` (str) — the institution name (use this for counting unique institutions)
- `jml_data` (int) — number of data records
- `tgl_inquiry` (str) — date string like '2026-03-08 15:32:23'

There are NO fields named: institution_name, platform_name, loan_purpose, type, jenis, result, status, inquiry_time
- For "unique institutions": use `hit_by` field
- For "unique platforms": use `hit_by` field (in practice, hit_by = institution name)
- For "unique loan purposes": use `hit_by` field (fallback — no loan_purpose field exists)
- For "hard inquiries" / "rejected": use `jml_data > 0` as a proxy or just count all inquiries
- For `_filter_window` on inquiries: add inquiry_time ms conversion first, then use _filter_window


```python
class FeatureCalculator:
    def __init__(self, app_category_cache=None):
        self.app_category_cache = app_category_cache or {}
        self.gambling_packages = {pkg for pkg, info in self.app_category_cache.items()
                                   if info.get('category') == 'gambling'}
        self.loan_packages = {pkg for pkg, info in self.app_category_cache.items()
                               if info.get('category') in ('cash_loan', 'fintech_lending')}

    def _get_apply_time(self, data):
        return data.get('applyTime') or data.get('params', {}).get('base', {}).get('applyTime', 0)

    def _safe_div(self, a, b):
        return a / b if b != 0 else 0.0

    def _date_to_ms(self, date_str: str) -> int:
        \"\"\"Convert date string to millisecond timestamp. Handles 'YYYY-MM-DD' and 'YYYY-MM-DD HH:MM:SS'\"\"\"
        if not date_str or '-' not in str(date_str):
            return 0
        try:
            # Handle 'YYYY-MM-DD HH:MM:SS' by stripping time part
            clean = str(date_str).strip()
            if ' ' in clean:
                clean = clean.split(' ')[0]
            dt = __import__('datetime').datetime.strptime(clean, '%Y-%m-%d')
            return int(dt.timestamp() * 1000)
        except:
            return 0

    def _filter_window(self, items, time_key, apply_time, days):
        if not items:
            return []
        start = apply_time - days * 86400000
        return [i for i in items if start <= i.get(time_key, 0) <= apply_time]

    def _filter_window_date(self, items, date_key, apply_time, days):
        \"\"\"Filter loan records by date string field (YYYY-MM-DD)\"\"\"
        if not items:
            return []
        start = apply_time - days * 86400000
        result = []
        for item in items:
            ts = self._date_to_ms(item.get(date_key, ''))
            if start <= ts <= apply_time:
                result.append(item)
        return result

    def calculate_all(self, data, apply_time=None) -> dict:
        if apply_time is None:
            apply_time = self._get_apply_time(data)
        if apply_time == 0:
            return {}
        params = data.get('params', {})
        # CORRECT FDC path: params.FDC (NOT data.FDC)
        fdc = params.get('FDC', {})
        hi = fdc.get('history_inquiry', {})     # dict (not list)
        loans = fdc.get('pinjaman', [])          # list of loan records
        pa = fdc.get('platform_aktif', {})       # dict
        ...
```

Generate the complete code:
"""
        return prompt

    def _load_category_packages(self) -> Dict[str, set]:
        """从APP分类缓存中加载各类别包名集合"""
        cache_file = 'outputs/app_analysis/classification_complete_11850.json'
        result = {}
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                classifications = data.get('classifications', data)
                for pkg, info in classifications.items():
                    cat = info.get('category', 'unknown') if isinstance(info, dict) else 'unknown'
                    if cat not in result:
                        result[cat] = set()
                    result[cat].add(pkg)
            except Exception as e:
                logger.warning(f"  加载APP分类缓存失败: {e}")
        return result

    def _extract_code(self, response: str) -> str:
        """从LLM响应提取python代码"""
        if '```python' in response:
            start = response.find('```python') + 9
            end = response.find('```', start)
            if end > start:
                return response[start:end].strip()
        if 'class FeatureCalculator' in response:
            return response[response.find('class FeatureCalculator'):]
        return None

    # ========== Self-Review ==========

    def self_review(self) -> bool:
        """生成完毕后整体审视"""
        if not self.generated_code:
            logger.warning("  无可审阅的代码")
            self.self_review_passed = False
            return False

        logger.info("  执行 self-review...")

        review_prompt = f"""# Self-Review: 特征计算代码审查

## 审查项

1. **防穿越检查**: 是否所有数据过滤都使用了applyTime（不是datetime.now()）？
2. **完整性检查**: 是否所有{len(self.features)}个特征都有对应的计算代码？
3. **健壮性检查**: 是否有除零保护、缺失值处理？
4. **一致性检查**: 特征名是否与设计文档一致？

请逐项检查并给出结论：PASS 或 FAIL（附具体问题）

```python
{self.generated_code[:6000]}
```
"""
        response = self.llm_client.chat(
            [{"role": "user", "content": review_prompt}],
            temperature=0,
            max_tokens=2000
        )

        if 'PASS' in response.upper() and 'FAIL' not in response.upper().split('PASS')[0]:
            self.self_review_passed = True
            logger.info("  ✅ Self-review 通过")
            return True
        else:
            self.self_review_passed = False
            logger.warning(f"  ⚠️ Self-review 发现问题，请查看反馈")
            logger.info(f"  Review反馈: {response[:500]}")
            return False

    def save_code(self, path='outputs/feature_code/features_calculator_v2.py'):
        """保存生成代码"""
        if not self.generated_code:
            logger.warning("  无可保存的代码")
            return

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.generated_code)
        logger.info(f"  代码已保存: {path}")

    def save_promoted_templates(self):
        """晋升记录已进入 PostgreSQL；此方法保留为旧调用点兼容。"""
        if self.promoted_templates:
            logger.info(f"  晋升模板记录已写入 PostgreSQL: {len(self.promoted_templates)}个")

    # ========== 主入口 ==========

    def run(self, skip_design: bool = False) -> bool:
        """
        运行特征开发Agent

        Args:
            skip_design: 是否跳过设计阶段（用于审核重做时仅重新生成代码）

        Returns:
            是否成功
        """
        logger.info("=" * 60)
        logger.info("特征开发Agent - 启动")
        logger.info("=" * 60)

        # 1. 加载IV/PSI反馈
        self.load_iv_psi_feedback()

        # 2. 加载APP分类缓存
        self.load_app_classification_cache()

        # 3. 设计阶段（含通道1+通道2）
        if not skip_design:
            success = self.run_design_phase()
            if not success:
                logger.error("  设计阶段失败，终止")
                return False

        # 4. 生成代码（确定性组合）
        code = self.generate_code()
        if not code:
            logger.error("  代码生成失败")
            return False

        # 5. AST验证：检查生成的代码是否全部使用模板函数
        logger.info("  AST验证：检查代码质量...")
        try:
            from agents.code_ast_verifier import verify_code
            verify_result = verify_code(code, self.feature_doc)
            logger.info(f"  AST验证: {verify_result['details'].replace(chr(10), ' | ')}")

            # 记录违反项，但不断流（仅记录+警告）
            actual_violations = [v for v in verify_result.get('violations', [])
                                 if v.get('severity') == 'violation']
            if actual_violations:
                logger.warning(f"  ⚠️ 发现 {len(actual_violations)} 个手写代码/非模板函数特征:")
                for v in actual_violations:
                    logger.warning(f"     - {v['feature_name']}: {v['problem']}")
            else:
                logger.info(f"  ✅ AST验证全部通过（{verify_result['compliant']}/{verify_result['total_features']}个特征使用模板函数）")
        except ImportError as e:
            logger.warning(f"  ⚠️ AST验证模块导入失败: {e}，跳过验证")
        except Exception as e:
            logger.warning(f"  ⚠️ AST验证异常: {e}，跳过验证")

        # 6. Self-review
        self.self_review()
        # self-review 不阻断流程，仅记录

        # 7. 保存
        self.save_code()
        if self.promoted_templates:
            self.save_promoted_templates()

        logger.info("=" * 60)
        logger.info(f"特征开发Agent - 完成 ({len(self.features)}个特征)")
        logger.info("=" * 60)
        return True


# 便捷函数
def create_feature_development_agent() -> FeatureDevelopmentAgent:
    """创建特征开发Agent实例"""
    return FeatureDevelopmentAgent()


if __name__ == '__main__':
    agent = FeatureDevelopmentAgent()
    agent.run()
