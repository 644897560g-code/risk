"""
夜间批量分类新APP任务

功能：
1. 扫描未分类的APP列表（未知APP）
2. 批量调用LLM进行分类（与历史11,850个APP相同的Prompt）
3. 分类结果回写缓存
4. 发送分类报告

调用方式：
- 定时任务：每天凌晨2点执行
- 手动调用：python batch_classify_new_apps.py --input unknown_apps.json
"""

import json
import os
import sys
import logging
from datetime import datetime
from typing import List, Dict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append('/Users/apple/Desktop/agents/risk-agent-cc-indo')

from utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


class BatchClassifier:
    """夜间批量分类器"""

    def __init__(self):
        self.llm_client = LLMClient()
        self.cache_file = 'outputs/app_analysis/classification_cache.json'
        self.cache = self._load_cache()

    def _load_cache(self) -> dict:
        """加载分类缓存"""
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_cache(self):
        """保存分类缓存"""
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def get_unknown_apps(self, input_file: str) -> List[Dict]:
        """
        获取未分类APP列表

        Args:
            input_file: 输入文件（包含未分类APP列表）

        Returns:
            未分类APP列表
        """
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 过滤已分类的APP
        unknown_apps = []
        for app in data:
            pkg_name = app.get('package_name', app.get('app', ''))
            if pkg_name and pkg_name not in self.cache:
                unknown_apps.append(app)

        logger.info(f"找到 {len(unknown_apps)} 个未分类APP")
        return unknown_apps

    def classify_with_llm(self, app_list: List[Dict]) -> Dict:
        """
        使用LLM批量分类APP

        Args:
            app_list: APP列表

        Returns:
            分类结果 {package_name: {category, confidence, reason}}
        """
        results = {}
        batch_size = 50  # 每批处理50个APP
        total_batches = (len(app_list) + batch_size - 1) // batch_size

        logger.info(f"开始LLM批量分类，共{len(app_list)}个APP，分{total_batches}批处理")

        for batch_idx in range(total_batches):
            start = batch_idx * batch_size
            end = min((batch_idx + 1) * batch_size, len(app_list))
            batch = app_list[start:end]

            logger.info(f"处理第{batch_idx + 1}/{total_batches}批，共{len(batch)}个APP")

            # 构建批量分类Prompt
            prompt = self._build_batch_prompt(batch)

            try:
                # 调用LLM
                messages = [{"role": "user", "content": prompt}]
                response = self.llm_client.chat(messages, temperature=0)

                # 解析结果
                batch_results = self._parse_llm_response(response, batch)

                # 合并到总结果
                results.update(batch_results)

                # 每5批保存一次
                if (batch_idx + 1) % 5 == 0:
                    self.cache.update(results)
                    self._save_cache()
                    logger.info(f"已保存 {len(results)} 个分类结果")

            except Exception as e:
                logger.error(f"第{batch_idx + 1}批处理失败: {e}")
                continue

        # 保存最终结果
        self.cache.update(results)
        self._save_cache()

        logger.info(f"批量分类完成，共处理 {len(results)} 个APP")
        return results

    def _build_batch_prompt(self, batch: List[Dict]) -> str:
        """
        构建批量分类Prompt（与历史11,850个APP分类的Prompt保持一致）

        Args:
            batch: 本批次的APP列表

        Returns:
            Prompt文本
        """
        prompt = """# 任务：批量分类印尼APP

## 背景
请对以下印尼智能手机用户安装的应用程序包名（package names）进行科学分类。

## 分类标准

请采用以下**15个标准类别**（与历史分类保持一致）：

### 高风险类别（优先判断）
1. **gambling** - 赌博/棋牌/老虎机
2. **cash_loan** - 现金贷/网贷
3. **fintech_lending** - 金融科技借贷（持牌机构）
4. **fake_gps** - 虚拟定位工具
5. **clone_app** - 应用克隆/分身工具
6. **app_store** - 第三方应用商店

### 金融机构
7. **banking** - 银行应用
8. **ewallet** - 电子钱包

### 消费金融
9. **installment** - 分期购物
10. **shopping** - 购物/电商

### 工具生活服务
11. **transportation** - 出行/打车/物流
12. **food_delivery** - 外卖点餐
13. **utility** - 工具/系统增强
14. **productivity** - 办公/效率
15. **religious** - 宗教应用
16. **social_entertainment** - 社交/娱乐/游戏

**注意**：不包含`other`类别，如果应用确实无法归类，请标记为`unknown`

## 类别优先级规则

**第一优先级**：高风险具体类别（fake_gps, clone_app, app_store, gambling, cash_loan）
- 如果符合，直接返回该类别，不再判断其他类别

**第二优先级**：金融/消费类别（fintech_lending, banking, ewallet, shopping等）
- 如果不是高风险类别，再判断是否属于金融/生活服务类别

**第三优先级**：通用类别（utility, productivity, social_entertainment等）
- 最后判断通用类别

**最终兜底**：如果确实无法归类，标记为`unknown`

## 待分类应用列表

"""
        for i, app in enumerate(batch, 1):
            pkg_name = app.get('package_name', app.get('app', ''))
            app_name = app.get('app_name', '')
            prompt += f"{i}. 包名: `{pkg_name}`"
            if app_name:
                prompt += f"\n   应用名: {app_name}"
            prompt += "\n"

        prompt += """
## 输出要求

请输出JSON格式的分类结果（不要有其他文字）：

```json
{
  "classifications": {
    "包名1": {
      "category": "类别名",
      "confidence": 0.9,
      "reason": "分类理由（中文）"
    },
    "包名2": {
      "category": "类别名",
      "confidence": 0.8,
      "reason": "分类理由"
    },
    ...
  }
}
```

## 注意事项

1. **置信度评估**：
   - 0.9-1.0: 几乎100%准确（如已知品牌、白牌模板）
   - 0.8-0.9: 高度可信（如明确关键词）
   - 0.7-0.8: 较可信（如单一特征）
   - <0.7: 不确定，标记为unknown

2. **分类理由**：
   - 用中文说明
   - 说明判断依据（如"包含judi赌博词"、"符合NTLA白牌模板"）

3. **unknown处理**：
   - 只有确实无法判定的才标记为unknown
   - 会进入人工审核队列

## 开始

请对上述应用进行分类，输出JSON格式结果：
"""
        return prompt

    def _parse_llm_response(self, response: str, batch: List[Dict]) -> Dict:
        """
        解析LLM响应结果

        Args:
            response: LLM返回的文本
            batch: 原始APP列表

        Returns:
            分类结果字典
        """
        results = {}

        try:
            # 提取JSON
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()

            data = json.loads(json_str)
            classifications = data.get('classifications', {})

            for pkg_name, info in classifications.items():
                results[pkg_name] = {
                    'category': info.get('category', 'unknown'),
                    'confidence': info.get('confidence', 0.5),
                    'reason': info.get('reason', ''),
                    'classified_date': datetime.now().strftime('%Y-%m-%d'),
                    'method': 'llm_batch_classification'
                }

        except Exception as e:
            logger.error(f"解析LLM响应失败: {e}")
            # 返回空结果
            pass

        return results

    def merge_into_complete_classification(self, new_results: Dict):
        """
        将新分类结果合并到历史完整分类文件中

        Args:
            new_results: 新分类的APP结果
        """
        # 1. 加载历史完整分类文件
        # 查找最新的 classification_complete_*.json
        history_dir = 'outputs/app_analysis'
        history_files = [f for f in os.listdir(history_dir)
                        if f.startswith('classification_complete_') and f.endswith('.json')]

        if history_files:
            # 使用最新的文件
            latest_history = max(history_files,
                               key=lambda f: os.path.getmtime(os.path.join(history_dir, f)))
            history_path = os.path.join(history_dir, latest_history)

            with open(history_path, 'r', encoding='utf-8') as f:
                history_data = json.load(f)

            history_classifications = history_data.get('classifications', {})
            logger.info(f"加载历史分类: {len(history_classifications)} 个APP ({latest_history})")
        else:
            # 没有历史文件，从头开始
            history_data = {}
            history_classifications = {}
            logger.warning("没有找到历史分类文件，将创建新文件")

        # 2. 合并新结果
        history_classifications.update(new_results)
        total_apps = len(history_classifications)

        logger.info(f"合并后总计: {total_apps} 个APP")
        logger.info(f"新增: {len(new_results)} 个APP")

        # 3. 生成新的完整分类文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        new_filename = f'classification_complete_{total_apps}.json'
        new_filepath = os.path.join(history_dir, new_filename)

        output_data = {
            'total_apps': total_apps,
            'classification_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'model': 'qwen/qwen3.6-plus',
            'merge_info': {
                'merged_at': datetime.now().isoformat(),
                'new_count': len(new_results),
                'previous_count': len(history_classifications) - len(new_results)
            },
            'classifications': history_classifications
        }

        os.makedirs(history_dir, exist_ok=True)
        with open(new_filepath, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ 新分类文件已生成: {new_filename}")

        # 4. 更新classification_cache.json（保持最新缓存）
        self._save_cache()
        logger.info(f"✅ 缓存已更新: {self.cache_file}")

        # 5. 更新app_classification_complete.csv
        self._update_csv(history_classifications, new_filepath)

        return new_filepath

    def _update_csv(self, classifications: Dict, json_path: str):
        """更新CSV文件"""
        import csv

        csv_path = json_path.replace('.json', '.csv')

        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['package_name', 'category', 'confidence', 'reason'])

            for pkg, info in classifications.items():
                writer.writerow([
                    pkg,
                    info.get('category', 'unknown'),
                    info.get('confidence', ''),
                    info.get('reason', '')
                ])

        logger.info(f"✅ CSV已更新: {csv_path}")

    def generate_report(self, results: Dict) -> str:
        """
        生成分类报告

        Args:
            results: 分类结果

        Returns:
            报告文本
        """
        report_lines = []
        report_lines.append("# 夜间批量分类报告")
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"分类总数: {len(results)}")
        report_lines.append("")

        # 类别统计
        category_stats = {}
        for info in results.values():
            cat = info['category']
            category_stats[cat] = category_stats.get(cat, 0) + 1

        report_lines.append("## 类别分布")
        for cat, count in sorted(category_stats.items(), key=lambda x: x[1], reverse=True):
            report_lines.append(f"- {cat}: {count}")

        report_lines.append("")
        report_lines.append("## 高风险类别")
        high_risk_cats = ['gambling', 'cash_loan', 'fintech_lending', 'fake_gps', 'clone_app', 'app_store']
        for cat in high_risk_cats:
            if cat in category_stats:
                report_lines.append(f"- **{cat}**: {category_stats[cat]}")

        report_lines.append("")
        report_lines.append("## 待人工审核（unknown）")
        unknown_count = category_stats.get('unknown', 0)
        report_lines.append(f"- 数量: {unknown_count}")

        return "\n".join(report_lines)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='夜间批量分类新APP')
    parser.add_argument('--input', type=str, required=True, help='输入文件（未分类APP列表）')
    parser.add_argument('--output', type=str, default='outputs/app_analysis/batch_classification_report.md', help='输出报告文件')

    args = parser.parse_args()

    # 创建分类器
    classifier = BatchClassifier()

    # 获取未分类APP
    unknown_apps = classifier.get_unknown_apps(args.input)

    if not unknown_apps:
        print("✅ 没有未分类的APP")
        sys.exit(0)

    # 批量分类
    results = classifier.classify_with_llm(unknown_apps)

    # 合并到历史完整分类文件（关键步骤！）
    merged_file_path = classifier.merge_into_complete_classification(results)

    # 生成报告
    report = classifier.generate_report(results)

    # 保存报告
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"✅ 批量分类完成！")
    print(f"📊 分类总数: {len(results)}")
    print(f"🔀 已合并到: {merged_file_path}")
    print(f"📝 报告已保存到: {args.output}")
