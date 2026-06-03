"""
ParamDesignSkill - 参数设计Skill

职责：
1. 读取通道1模板库（15个模板的parameter_space类型描述）
2. 调用LLM，为每个模板生成2-4个合理的具体参数组合
3. 输出兼容 feature_design_doc.json 格式的结果

为什么需要这个Skill：
- 原有流程中LLM一次性生成15-25个特征，数量不稳定
- 缺少系统化的参数设计环节
- 批量生成30-60个特征后，可通过IV/PSI自动筛选

输出示例：
[
  {
    "feature_name": "count_gambling_apps_7d",
    "feature_type": "count",
    "data_source": "applist",
    "template_id": "T001",
    "params": {"source": "applist", "window": 7},
    "business_explanation_cn": "近7天安装的赌博类APP数量",
    "design_reason": "赌博APP数量是重要的多头借贷和欺诈信号",
    "expected_risk_correlation": "positive"
  },
  ...
]
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from utils.llm_client import LLMClient

logger = logging.getLogger(__name__)

# 通道1模板库路径
CHANNEL1_TEMPLATES_PATH = 'outputs/feature_templates/channel1_templates.json'


class ParamDesignSkill:
    """参数设计Skill — 系统化生成参数组合"""

    def __init__(self):
        self.llm_client = LLMClient()

    def load_templates(self) -> List[Dict]:
        """加载通道1模板"""
        with open(CHANNEL1_TEMPLATES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('templates', [])

    def design_params(self, data_summary: Optional[Dict] = None,
                      previous_feedback: Optional[str] = None) -> List[Dict]:
        """调用LLM为所有模板生成参数组合

        Args:
            data_summary: 数据特征摘要（如标签分布、缺失率等）
            previous_feedback: 历史IV/PSI反馈

        Returns:
            特征列表 [feature_name, template_id, params, ...]
        """
        templates = self.load_templates()
        if not templates:
            logger.error("  未加载到通道1模板")
            return []

        # 构建模板摘要（去掉examples，保持简洁）
        tmpl_summaries = []
        for t in templates:
            tmpl_summaries.append({
                'template_id': t['template_id'],
                'template_name': t['template_name'],
                'template_name_cn': t['template_name_cn'],
                'dimension': t['dimension'],
                'complexity': t['complexity'],
                'dsl': t['dsl'],
                'dsl_description': t['dsl_description'],
                'parameter_space': t['parameter_space'],  # type/description
                'formula_template': t['formula_template'],
            })

        prompt = self._build_prompt(tmpl_summaries, data_summary, previous_feedback)
        response = self.llm_client.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=16000
        )

        features = self._parse_response(response)
        if features:
            logger.info(f"  ✅ 参数设计完成: {len(features)}个特征")
            # 验证每个特征的必要字段
            valid = []
            for f in features:
                if f.get('feature_name') and f.get('template_id') and f.get('params'):
                    # 后处理：替换泛化的 'fdc' 为具体数据源名
                    self._fix_source_names(f)
                    valid.append(f)
            logger.info(f"  ✅ 有效特征: {len(valid)}/{len(features)}")
            return valid
        else:
            logger.warning("  LLM返回解析失败，使用模板参数自动生成")
            return self._fallback_design(templates)

    def _build_prompt(self, templates: List[Dict], data_summary: Optional[Dict],
                      previous_feedback: Optional[str]) -> str:
        """构建参数设计prompt"""
        prompt = """# 任务：通道1 DSL模板 → 参数设计（系统性批量生成）

## 背景
你是印尼现金贷风控特征工程师。请根据以下15个DSL模板的 parameter_space 类型描述，
为每个模板选择2-4组合理的具体参数值，生成完整的业务特征定义。

## 数据源约定
fdc_inquiry = FDC征信机构的查询记录（含 hit_by, jml_data, tgl_inquiry）
fdc_pinjaman = FDC征信机构的贷款记录（含 tgl_penyaluran_dana, nilai_pendanaan, tipe_pinjaman 等）
applist = 用户手机安装的应用列表（含 inTime, upTime, packageX, appName 等）
base = 用户基本信息（含 salary, birthday, workYears, gender, marita 等）

重要 — 数据源命名必须精确：
- **绝对不能使用泛化的 'fdc'**（代码中完全不识别，导致特征值恒为0！），必须用 'fdc_inquiry' 或 'fdc_pinjaman'
- 'applist' 和 'base' 保持原样
- **`data_source` 字段也严禁使用 'fdc'**，同样必须用 'fdc_inquiry' 或 'fdc_pinjaman'

## 实际数据字段（重要：cond参数必须使用真实存在的字段）
- **applist 数据项不含 `category` 或 `app_category` 字段**！
  applist 每项包含: inTime, upTime, packageX, appName 等
  分类信息在外部缓存中，无法通过 cond 参数过滤
  如需按APP类别过滤，必须使用 `allowed_categories` 参数
- **fdc_pinjaman 每项包含**: tipe_pinjaman, nilai_pendanaan, kualitas_pinjaman, status_pinjaman, id_penyelenggara, tgl_penyaluran_dana 等
  可以通过 cond 过滤，如 `cond: {"tipe_pinjaman": "Multiguna"}`
- **fdc_inquiry 是预聚合统计值**（不支持 cond 过滤）
  建议只用 count/trend/period_compare，不要加 cond 参数
- **base 数据字段**: salary, birthday, workYears, gender, marita, children, job 等

## 参数设计原则
1. **每个模板至少2个、最多4个参数组合**
2. **参数值要合理**：
   - window 取值建议：applist源用 7/30；fdc源用 90/180（FDC贷款记录通常更旧）
   - threshold 用 2.0/3.0/5.0 等
3. **特征名命名规范**：{template}_{source}_{window}，如 count_applist_install_7d
4. **不同模板的参数组合要有所区分**，覆盖不同的业务角度
5. **优先聚焦高风险信号**：多头借贷、以贷养贷、共债、欺诈团伙
6. **每个参数组合都要有业务意义**，不能为了凑数而生成
7. **重要 — T004(占比)和T005(集中度)的APP分类过滤**：
   - 当需要按APP类别过滤时，使用 `allowed_categories` 参数（数组类型），如 `"allowed_categories": ["gambling"]`
   - 不要使用 `target_cond` 参数
   - `allowed_categories` 取值参考：gambling(赌博类), cash_loan(现金贷), fintech_lending(金融科技)
8. **重要 — 特殊模板参数限制**：
   - T010(percentile)、T011(deviation)、T012(anomaly)：这些函数不需要 `source` 和 `window` 参数，params 只包含描述性参数（如 method, reference_type, target_metric 等）
   - T013(declared_vs_actual)：使用 declared_field 和 actual_field，不需要 source/window
   - T014(cross_source_discrepancy)：使用 field_pairs_config，不需要 source/window
   - T015(identity_cluster)：使用 identity_field, shared_field, min_threshold，不需要 source/window

## 输出格式
返回JSON数组，每个元素包含：

```json
{
  "feature_name": "英文特征名",
  "feature_type": "模板类型名",
  "data_source": "数据源",
  "template_id": "对应模板ID",
  "params": {"参数字典，含source、window等"},
  "business_explanation_cn": "中文业务解释",
  "design_reason": "设计理由",
  "expected_risk_correlation": "positive/negative"
}
```

"""
        prompt += f"\n## 通道1模板清单（共{len(templates)}个）\n\n"
        for t in templates:
            ps = t.get('parameter_space', {})
            ps_str = json.dumps(ps, ensure_ascii=False, indent=4)
            prompt += f"### {t['template_id']} {t['template_name_cn']} ({t['template_name']})\n"
            prompt += f"- **DSL**: {t['dsl']}\n"
            prompt += f"- **维度/复杂度**: {t['dimension']}/{t['complexity']}\n"
            prompt += f"- **描述**: {t['dsl_description']}\n"
            prompt += f"- **参数空间**: \n```json\n{ps_str}\n```\n\n"

        if previous_feedback:
            prompt += f"\n## IV/PSI历史反馈\n{previous_feedback}\n\n"

        prompt += """## 要求
1. 总共生成 **30-60个** 特征（每个模板2-4个参数组合 × 15个模板 ≈ 30-60个）
2. feature_name 不能重复（如需可加参数后缀区分）
3. **CRITICAL — source 取值规则**（违反将导致特征 IV=0）：
   - **绝对禁止使用泛化的 'fdc'**！代码中不识别这个值
   - source 只能从以下取值中选择：`applist`, `fdc_pinjaman`, `fdc_inquiry`, `base`
   - FDC数据相关特征：
     * **查询次数/行为相关 → `fdc_inquiry`**（对应 history_inquiry 统计值）
     * **贷款记录/金额/期限相关 → `fdc_pinjaman`**（对应 pinjaman 数组）
   - `data_source` 字段同理，不能使用 'fdc'
4. 避免生成无业务意义的特征
5. 每条特征都需要中文业务解释和设计理由
6. data_source 取简写（applist/fdc_pinjaman/fdc_inquiry/base）
"""
        return prompt

    def _parse_response(self, response: str) -> List[Dict]:
        """解析LLM返回的JSON"""
        # 尝试json code block
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
                # 可能是 {"features": [...]} 格式
                return result.get('features', [result])
        except json.JSONDecodeError:
            logger.warning("  LLM响应JSON解析失败")
            return []

        return []

    def _fallback_design(self, templates: List[Dict]) -> List[Dict]:
        """当LLM返回解析失败时的备用方案"""
        features = []
        source_choices = {
            'T001': ['applist', 'fdc_pinjaman', 'fdc_inquiry'],
            'T002': ['fdc_inquiry', 'fdc_pinjaman'],
            'T003': ['applist', 'fdc_inquiry', 'fdc_pinjaman'],
            'T004': ['applist', 'fdc_pinjaman'],
            'T005': ['applist', 'fdc_inquiry', 'fdc_pinjaman'],
            'T006': [('applist', 'fdc_pinjaman')],
            'T007': ['fdc_inquiry', 'fdc_pinjaman', 'applist'],
            'T008': ['fdc_inquiry', 'fdc_pinjaman', 'applist'],
            'T009': ['fdc_inquiry', 'applist', 'fdc_pinjaman'],
            'T010': ['all'],
            'T011': ['all'],
            'T012': ['all'],
            'T013': ['base_vs_fdc'],
            'T014': ['base_vs_fdc'],
            'T015': ['identity'],
        }
        windows = [7, 30, 90, 180]
        used_names = set()

        for t in templates:
            tid = t['template_id']
            name = t['template_name']
            sources = source_choices.get(tid, ['applist'])
            for src in sources[:3]:  # 最多3个数据源
                for w in windows[:2]:  # 最多2个窗口
                    if isinstance(src, tuple):
                        # T006 交叉重叠
                        base_name = f"{name}_{src[0]}_vs_{src[1]}"
                    else:
                        base_name = f"{name}_{src}_{w}d"

                    if base_name in used_names:
                        continue
                    used_names.add(base_name)

                    params = {'source': src, 'window': w} if not isinstance(src, tuple) else {}
                    features.append({
                        'feature_name': base_name,
                        'feature_type': name,
                        'data_source': src if not isinstance(src, tuple) else src[0],
                        'template_id': tid,
                        'params': params,
                        'business_explanation_cn': f"基于{name}模板的{src}特征(window={w})",
                        'design_reason': '自动生成',
                        'expected_risk_correlation': 'positive',
                    })

        logger.info(f"  备用方案生成: {len(features)}个特征")
        return features

    def _fix_source_names(self, feat: Dict):
        """后处理：将泛化的 'fdc' source 替换为具体的 'fdc_inquiry' 或 'fdc_pinjaman'"""
        params = feat.get('params', {})
        tid = feat.get('template_id', '')
        fixed = False

        # 处理 source/source_a/source_b 字段
        source_keys = ['source', 'source_a', 'source_b']
        for sk in source_keys:
            if sk in params and params[sk] == 'fdc':
                # 判断应替换为 inquiry 还是 pinjaman
                # 默认用 fdc_inquiry（查询次数是更常见的FDC特征）
                # 如果 cond 包含 pinjaman 相关字段，则用 fdc_pinjaman
                cond = params.get('cond', {})
                if cond and any(k in cond for k in ('tipe_pinjaman', 'kualitas_pinjaman', 'status_pinjaman', 'nama_platform')):
                    params[sk] = 'fdc_pinjaman'
                elif sk == 'source_a' or sk == 'source_b':
                    # overlap/compare 等模板，如果其中一个源是 applist/base，另一个用 fdc_inquiry
                    other_key = 'source_b' if sk == 'source_a' else 'source_a'
                    other_val = params.get(other_key)
                    if other_val in ('applist', 'base'):
                        params[sk] = 'fdc_inquiry'
                    else:
                        params[sk] = 'fdc_inquiry'
                else:
                    params[sk] = 'fdc_inquiry'
                fixed = True

        if fixed:
            logger.debug(f"    {feat.get('feature_name')}: source 已从 'fdc' 修正为 '{params.get(sk, '?')}'")

    def save_features(self, features: List[Dict], path: str = 'outputs/feature_design/feature_design_doc.json'):
        """保存特征设计文档"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        doc = {
            'channel': 'channel1',
            'generated_at': datetime.now().isoformat(),
            'total_features': len(features),
            'features': features,
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        logger.info(f"  特征设计文档已保存: {path} ({len(features)}个特征)")


def run(data_summary: Optional[Dict] = None,
        previous_feedback: Optional[str] = None) -> List[Dict]:
    """便捷入口"""
    skill = ParamDesignSkill()
    features = skill.design_params(data_summary, previous_feedback)
    if features:
        skill.save_features(features)
    return features


if __name__ == '__main__':
    features = run()
    print(f"\n完成: {len(features)}个特征")
