"""
基于已分类的2,000个应用，让LLM总结15个类别的判定规则和关键词

目的：建立可扩展的分类规则库，应对新包名的识别
"""

import json
import os
from collections import defaultdict, Counter
from utils.llm_client import LLMClient
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_classified_apps(result_file: str):
    """加载已分类的应用数据"""
    with open(result_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    classifications = data.get('classifications', data)
    logger.info(f"加载 {len(classifications)} 个已分类应用")

    # 按类别分组
    apps_by_category = defaultdict(list)
    for app, info in classifications.items():
        category = info['category']
        apps_by_category[category].append({
            'package': app,
            'confidence': info['confidence'],
            'reason': info['reason']
        })

    return apps_by_category


def create_rule_extraction_prompt(apps_by_category: dict, target_category: str):
    """创建规则提取prompt"""

    apps = apps_by_category[target_category]
    packages = [app['package'] for app in apps[:50]]  # 最多取50个样本
    reasons = [app['reason'] for app in apps if app['reason']][:30]

    system_prompt = """你是印尼应用分类专家。请基于已分类的应用样本，总结该类别的判定规则。

任务：分析应用包名和分类理由，提取出**可复用的判定规则**。

输出要求：
1. 关键词模式：包名中常见的关键词（如loan/kredit/cash→cash_loan）
2. 域名模式：常见域名特征（如com.xxx.loan）
3. 品牌名模式：常见品牌名称
4. 置信度判断标准：什么情况下置信度应该为high/medium/low
5. 误判风险：可能与其他类别混淆的情况
6. **新型包名识别规则**：总结规律而非穷举

请返回JSON格式：
{
  "category": "类别名",
  "sample_size": 样本数,
  "keyword_patterns": ["关键词1", "关键词2", ...],
  "domain_patterns": ["域名模式1", "域名模式2", ...],
  "brand_patterns": ["品牌名模式1", "品牌名模式2", ...],
  "confidence_rules": {
    "high": "高置信度判断标准",
    "medium": "中置信度判断标准",
    "low": "低置信度判断标准"
  },
  "confusion_risk": "可能混淆的类别及区分方法",
  "general_rules": "通用判定规律（可用于新包名识别）"
}"""

    user_prompt = f"""请分析以下{target_category}类别的应用样本：

**包名样本**（{len(packages)}个）:
{json.dumps(packages, ensure_ascii=False, indent=2)}

**分类理由**（部分样本）:
{json.dumps(reasons, ensure_ascii=False, indent=2)}

请总结该类别的判定规则，以便识别未来出现的新包名。"""

    return system_prompt, user_prompt


def extract_rules_for_all_categories(apps_by_category: dict, client: LLMClient):
    """为所有类别提取规则"""

    categories = list(apps_by_category.keys())
    all_rules = {}

    logger.info(f"\n开始为{len(categories)}个类别提取规则...")

    for category in categories:
        logger.info(f"\n{'='*60}")
        logger.info(f"处理类别: {category} ({len(apps_by_category[category])}个应用)")
        logger.info(f"{'='*60}")

        try:
            system_prompt, user_prompt = create_rule_extraction_prompt(apps_by_category, category)

            response = client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0
            )

            # 解析JSON
            json_text = response
            if "```json" in response:
                json_text = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_text = response.split("```")[1].split("```")[0].strip()

            last_brace = json_text.rfind('}')
            if last_brace != -1:
                json_text = json_text[:last_brace + 1]

            rule = json.loads(json_text)
            all_rules[category] = rule

            logger.info(f"  ✓ 成功提取规则")
            logger.info(f"  关键词模式: {len(rule.get('keyword_patterns', []))}个")
            logger.info(f"  域名模式: {len(rule.get('domain_patterns', []))}个")
            logger.info(f"  品牌模式: {len(rule.get('brand_patterns', []))}个")

        except Exception as e:
            logger.error(f"  ✗ 提取失败: {e}")
            all_rules[category] = {"error": str(e)}

        # 等待一下，避免过快调用
        import time
        time.sleep(2)

    return all_rules


def save_rules(all_rules: dict, output_path: str):
    """保存规则到文件"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_rules, f, ensure_ascii=False, indent=2)

    logger.info(f"\n✓ 规则已保存到: {output_path}")


def generate_readable_summary(all_rules: dict, summary_path: str):
    """生成可读的摘要报告"""
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("# 印尼应用分类规则库\n\n")
        f.write(f"生成时间: {json.dumps(__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ensure_ascii=False)}\n\n")
        f.write(f"基于样本: 2,000个已分类应用\n\n")
        f.write("---\n\n")

        for category, rule in all_rules.items():
            if "error" in rule:
                f.write(f"## {category} - ❌ 提取失败: {rule['error']}\n\n")
                continue

            f.write(f"## {category}\n\n")
            f.write(f"- 样本数: {rule.get('sample_size', 'N/A')}\n")
            f.write(f"- 关键词模式: {', '.join(rule.get('keyword_patterns', []))}\n")
            f.write(f"- 域名模式: {', '.join(rule.get('domain_patterns', []))}\n")
            f.write(f"- 品牌模式: {', '.join(rule.get('brand_patterns', []))}\n\n")

            f.write(f"**置信度规则**:\n")
            confidence = rule.get('confidence_rules', {})
            f.write(f"- High: {confidence.get('high', 'N/A')}\n")
            f.write(f"- Medium: {confidence.get('medium', 'N/A')}\n")
            f.write(f"- Low: {confidence.get('low', 'N/A')}\n\n")

            f.write(f"**混淆风险**: {rule.get('confusion_risk', 'N/A')}\n\n")
            f.write(f"**通用规则**: {rule.get('general_rules', 'N/A')}\n\n")
            f.write("---\n\n")

    logger.info(f"✓ 可读摘要已保存到: {summary_path}")


if __name__ == '__main__':
    # 加载第10批分类结果
    result_file = 'outputs/app_analysis/classification_intermediate_batch10.json'

    if not os.path.exists(result_file):
        logger.error(f"错误: 文件 {result_file} 不存在")
        logger.info("请先等待第10批完成或手动指定其他批次文件")
        exit(1)

    # 1. 加载数据
    apps_by_category = load_classified_apps(result_file)

    # 2. 初始化LLM客户端
    client = LLMClient()

    # 3. 提取规则
    all_rules = extract_rules_for_all_categories(apps_by_category, client)

    # 4. 保存结果
    output_path = 'outputs/app_analysis/category_rules.json'
    save_path = 'outputs/app_analysis/category_rules_summary.md'

    save_rules(all_rules, output_path)
    generate_readable_summary(all_rules, save_path)

    logger.info("\n" + "="*80)
    logger.info("规则提取完成！")
    logger.info("="*80)
