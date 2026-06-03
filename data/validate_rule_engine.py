"""
验证规则引擎分类准确性

使用生成的LLM规则对11,850个已分类APP进行重新分类验证
计算准确率、精确率、召回率等指标
生成混淆矩阵和验证报告
"""

import json
import os
import sys
from collections import defaultdict
from typing import Dict, List, Tuple
import pandas as pd

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from data.rule_engine_classifier import RuleEngineClassifier


def load_ground_truth() -> Dict[str, str]:
    """加载Ground Truth（原始分类结果）"""
    cache_file = 'outputs/app_analysis/classification_complete_11850.json'
    with open(cache_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    classifications = data['classifications']
    ground_truth = {
        pkg: info['category']
        for pkg, info in classifications.items()
    }

    return ground_truth


def load_rule_engine() -> RuleEngineClassifier:
    """加载规则引擎"""
    rules_file = 'outputs/risk_rules/online_app_classification_rules_llm.json'
    cache_file = 'outputs/app_analysis/classification_complete_11850.json'

    engine = RuleEngineClassifier(rules_file, cache_file)
    return engine


def get_rule_categories_count(engine: RuleEngineClassifier) -> int:
    """获取规则类别数量"""
    # rules属性是一个字典，键是类别名，值是规则
    return len(engine.rules)


def validate_rule_engine(ground_truth: Dict[str, str], engine: RuleEngineClassifier) -> Tuple[Dict, pd.DataFrame]:
    """验证规则引擎准确性"""

    total = len(ground_truth)
    predicted = {}
    correct = 0

    # 按类别统计
    category_stats = defaultdict(lambda: {
        'tp': 0,  # True Positives
        'fp': 0,  # False Positives
        'fn': 0,  # False Negatives
    })

    # 所有类别
    all_categories = set(ground_truth.values())

    print(f"开始验证 {total} 个APP的分类结果...")
    print("=" * 70)

    # 逐条验证
    for i, (pkg, true_category) in enumerate(ground_truth.items(), 1):
        # 使用规则引擎分类
        result = engine._rule_classify(pkg)
        pred_category = result['category']

        predicted[pkg] = pred_category

        # 统计准确性
        if pred_category == true_category:
            correct += 1
            category_stats[true_category]['tp'] += 1
        else:
            category_stats[true_category]['fn'] += 1
            category_stats[pred_category]['fp'] += 1

        # 进度显示
        if i % 1000 == 0:
            acc = correct / i * 100
            print(f"  处理进度: {i}/{total} ({i/total*100:.1f}%) - 当前准确率: {acc:.2f}%")

    print("=" * 70)
    print(f"✅ 验证完成\n")

    # 计算总体指标
    overall_accuracy = correct / total * 100

    # 计算每个类别的指标
    metrics = {}
    for category in sorted(all_categories):
        tp = category_stats[category]['tp']
        fp = category_stats[category]['fp']
        fn = category_stats[category]['fn']

        precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        # 该类别的总样本数
        total_in_category = tp + fn

        metrics[category] = {
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'precision_count': tp,
            'recall_count': tp,
            'total': total_in_category,
            'count_predicted': tp + fp
        }

    # 生成混淆矩阵
    confusion_matrix = generate_confusion_matrix(ground_truth, predicted, all_categories)

    return {
        'overall_accuracy': overall_accuracy,
        'category_metrics': metrics,
        'total_samples': total,
        'correct_predictions': correct,
        'category_stats': dict(category_stats)
    }, confusion_matrix


def generate_confusion_matrix(ground_truth: Dict[str, str],
                              predicted: Dict[str, str],
                              categories: set) -> pd.DataFrame:
    """生成混淆矩阵"""

    # 按字母顺序排序类别
    sorted_categories = sorted(categories)

    # 初始化混淆矩阵
    matrix_data = defaultdict(lambda: defaultdict(int))

    for pkg in ground_truth:
        true_cat = ground_truth[pkg]
        pred_cat = predicted.get(pkg, 'unknown')
        matrix_data[true_cat][pred_cat] += 1

    # 转换为DataFrame
    df_data = []
    for true_cat in sorted_categories:
        row = {'Category': true_cat}
        for pred_cat in sorted_categories:
            row[pred_cat] = matrix_data[true_cat][pred_cat]
        df_data.append(row)

    df = pd.DataFrame(df_data)
    df = df.set_index('Category')

    return df


def generate_validation_report(results: Dict, confusion_matrix: pd.DataFrame,
                                output_file: str):
    """生成验证报告"""

    lines = []
    lines.append("# 规则引擎分类准确性验证报告\n")
    lines.append("-" * 70)
    lines.append("")

    # 总体指标
    lines.append("## 总体指标\n")
    lines.append(f"- 总样本数: {results['total_samples']}")
    lines.append(f"- 正确分类: {results['correct_predictions']}")
    lines.append(f"- 总体准确率: {results['overall_accuracy']:.2f}%\n")
    lines.append("---\n")

    # 按类别详细指标
    lines.append("## 各类别详细指标\n")

    for category in sorted(results['category_metrics'].keys()):
        metrics = results['category_metrics'][category]

        lines.append(f"### {category}\n")
        lines.append(f"- 样本数: {metrics['total']}")
        lines.append(f"- 预测数: {metrics['count_predicted']}")
        lines.append(f"- 精确率 (Precision): {metrics['precision']:.2f}% ({int(metrics['precision_count'])}/{metrics['count_predicted']})")
        lines.append(f"- 召回率 (Recall): {metrics['recall']:.2f}% ({int(metrics['recall_count'])}/{metrics['total']})")
        lines.append(f"- F1分数: {metrics['f1']:.2f}\n")

        lines.append("---\n")

    # 混淆矩阵
    lines.append("## 混淆矩阵（前20个主要类别）\n")
    lines.append("```")

    # 只展示前20个类别
    top_categories = confusion_matrix.index[:20].tolist()
    top_matrix = confusion_matrix.loc[top_categories, top_categories]

    # 表头
    header = "True \\ Pred".ljust(20) + " | " + " | ".join([cat.ljust(15) for cat in top_categories[:10]])
    lines.append(header)
    lines.append("-" * len(header))

    # 数据行
    for true_cat in top_categories:
        row = true_cat.ljust(20) + " | "
        for pred_cat in top_categories[:10]:
            count = top_matrix.loc[true_cat, pred_cat]
            if count > 0:
                row += f"{count:4d}   ".ljust(15) + " | "
            else:
                row += " -     ".ljust(15) + " | "
        lines.append(row)

    lines.append("```\n")
    lines.append("---\n")

    # 分析结论
    lines.append("## 分析结论\n")

    accuracy = results['overall_accuracy']
    if accuracy >= 95:
        lines.append(f"- ✅ **优秀**: 规则引擎准确率达到{accuracy:.2f}%，可以投入生产使用")
    elif accuracy >= 90:
        lines.append(f"- ✅ **良好**: 规则引擎准确率达到{accuracy:.2f}%，建议优化低精度类别后上线")
    elif accuracy >= 80:
        lines.append(f"- ⚠️ **中等**: 规则引擎准确率为{accuracy:.2f}%，需要继续优化规则质量")
    else:
        lines.append(f"- ❌ **较低**: 规则引擎准确率为{accuracy:.2f}%，建议检查规则或重新训练")

    lines.append("")

    # 找出表现最差的5个类别
    worst_categories = sorted(
        results['category_metrics'].items(),
        key=lambda x: x[1]['f1']
    )[:5]

    if worst_categories:
        lines.append("### 需要优化的类别（F1最低的5个）\n")
        for category, metrics in worst_categories:
            lines.append(f"- **{category}**: F1={metrics['f1']:.2f}, 精确率={metrics['precision']:.2f}%, 召回率={metrics['recall']:.2f}%")

    lines.append("")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"📝 验证报告已保存: {output_file}")


def main():
    """主函数"""

    print("=" * 70)
    print("规则引擎分类准确性验证")
    print("=" * 70)
    print()

    # 1. 加载Ground Truth
    print("1. 加载原始分类结果...")
    ground_truth = load_ground_truth()
    print(f"   ✅ 加载了 {len(ground_truth)} 个已分类APP")

    # 2. 加载规则引擎
    print("\n2. 加载规则引擎...")
    engine = load_rule_engine()
    print(f"   ✅ 规则引擎加载完成")
    print(f"   - 缓存APP数: {len(engine.cache)}")
    rule_count = get_rule_categories_count(engine)
    print(f"   - 规则类别数: {rule_count}")

    # 3. 验证规则引擎
    print("\n3. 开始验证规则引擎...")
    results, confusion_matrix = validate_rule_engine(ground_truth, engine)

    # 4. 生成报告
    report_file = 'outputs/risk_rules/rule_engine_validation_report.md'
    print("\n4. 生成验证报告...")
    generate_validation_report(results, confusion_matrix, report_file)

    # 5. 保存JSON格式的验证结果
    validation_json = {
        'results': results,
        'confusion_matrix': confusion_matrix.to_dict()
    }

    json_file = 'outputs/risk_rules/rule_engine_validation_results.json'
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(validation_json, f, ensure_ascii=False, indent=2)

    print(f"📊 JSON验证结果已保存: {json_file}")

    # 6. 打印总结
    print("\n" + "=" * 70)
    print("验证总结")
    print("=" * 70)
    print(f"总体准确率: {results['overall_accuracy']:.2f}%")
    print(f"正确分类: {results['correct_predictions']}/{results['total_samples']}")
    print()

    # 打印各类型指标
    print("各类别指标（Top 10）：")
    print("-" * 70)

    # 按F1排序
    sorted_categories = sorted(
        results['category_metrics'].items(),
        key=lambda x: x[1]['f1'],
        reverse=True
    )[:10]

    for category, metrics in sorted_categories:
        print(f"  {category:20s} | F1: {metrics['f1']:6.2f} | Precision: {metrics['precision']:6.2f}% | Recall: {metrics['recall']:6.2f}%")

    print("\n" + "=" * 70)
    print(f"完整报告: {report_file}")
    print("=" * 70)


if __name__ == '__main__':
    main()
