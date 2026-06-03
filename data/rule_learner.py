"""
规则学习器 - 从已分类APP样本中自动学习在线判定规则

功能：
1. 从 classification_complete_11850.json 加载已分类数据
2. 对每个类别提取判定规则：
   - 关键词规则（高频词）
   - 正则表达式规则（包名模式）
   - 品牌规则（知名应用品牌）
   - 域名结构规则
3. 输出在线判定规则库（JSON格式）
"""

import json
import re
import string
from collections import Counter, defaultdict
from pathlib import Path


class RuleLearner:
    """从已分类APP中学习判定规则"""

    def __init__(self, classified_file: str):
        """
        Args:
            classified_file: 已分类APP的JSON文件路径
        """
        self.classified_file = classified_file
        self.data = None
        self.rules = {}

    def load_data(self):
        """加载已分类数据"""
        with open(self.classified_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        print(f"✅ 加载了 {self.data['total_apps']} 个已分类APP")

    def _tokenize_package_name(self, package_name: str) -> list:
        """
        分词包名：com.hypermart.hicard → ['hypermart', 'hicard']

        Args:
            package_name: APP包名

        Returns:
            分词后的token列表
        """
        # 转小写
        package_name = package_name.lower()
        # 按非字母数字字符分割
        tokens = re.findall(r'[a-z0-9]+', package_name)
        # 过滤掉常见无意义前缀
        stop_words = {'com', 'android', 'app', 'application', 'mobile', 'lite', 'pro'}
        tokens = [t for t in tokens if t not in stop_words and len(t) > 1]
        return tokens

    def _extract_keywords(self, apps_in_category: list, top_n: int = 30) -> dict:
        """
        提取类别的关键词（按语种分类）

        Args:
            apps_in_category: 该类别下的APP列表
            top_n: 返回top N关键词

        Returns:
            分类后的关键词字典
        """
        package_names = [app['package_name'] for app in apps_in_category]
        reasons = [app.get('reason', '') for app in apps_in_category]

        # 统计词频
        word_freq = Counter()
        for pkg in package_names:
            tokens = self._tokenize_package_name(pkg)
            word_freq.update(tokens)

        # 过滤掉通用词
        generic_words = {'id', 'co', 'net', 'org', 'app', 'android', 'mobile', 'lite',
                        'pro', 'free', 'com', 'version', 'apk', 'download'}
        word_freq = Counter({k: v for k, v in word_freq.items() if k not in generic_words})

        # 按语种分类关键词
        keywords = {
            "indonesian": [],  # 印尼语关键词
            "english": [],     # 英语关键词
            "brand_names": [], # 品牌名
            "numeric_patterns": [] # 数字模式
        }

        # 印尼语特征词（高风险类别）
        indonesian_risk_words = {
            'judi', 'slot', 'pinjaman', 'pinjol', 'pinjam', 'kredit', 'loan',
            'dana', 'uang', 'duit', 'cair', 'cepat', 'kilat', 'gampang',
            'muda', 'jaminan', 'bunga', 'sholat', 'quran', 'islam', 'muslim'
        }

        # 英语特征词
        english_risk_words = {
            'gambling', 'casino', 'poker', 'bingo', 'mahjong', 'domino', 'toto',
            'bet', 'wager', 'lottery', 'winner', 'lucky', 'jackpot', 'spin',
            'loan', 'credit', 'cash', 'finance', 'bank', 'wallet', 'pay'
        }

        for word, freq in word_freq.most_common(top_n * 2):
            # 检测是否为印尼语
            if word in indonesian_risk_words:
                keywords["indonesian"].append({"word": word, "freq": freq})
            # 检测是否为英语
            elif word in english_risk_words or all(c in string.ascii_letters for c in word):
                keywords["english"].append({"word": word, "freq": freq})
            # 数字模式
            elif re.search(r'\d', word):
                keywords["numeric_patterns"].append({"word": word, "freq": freq})
            # 品牌名（首字母大写或专有名词）
            elif freq >= 3:
                keywords["brand_names"].append({"word": word, "freq": freq})

        # 限制返回数量
        for key in keywords:
            keywords[key] = keywords[key][:top_n]

        return keywords

    def _extract_patterns(self, apps_in_category: list) -> list:
        """
        提取包名的正则表达式模式

        Args:
            apps_in_category: 该类别下的APP列表

        Returns:
            正则表达式模式列表
        """
        package_names = [app['package_name'] for app in apps_in_category]

        patterns = []

        # 模式1：提取共同前缀
        prefix_counter = Counter()
        for pkg in package_names:
            # 提取前缀：com.xxx 或 id.co.xxx
            parts = pkg.split('.')
            if len(parts) >= 2:
                prefix = '.'.join(parts[:2])  # com.xxx
                prefix_counter[prefix] += 1
            if len(parts) >= 3 and parts[0] == 'id':
                prefix = '.'.join(parts[:3])  # id.co.xxx
                prefix_counter[prefix] += 1

        # 保留出现频率>=3的前缀模式
        for prefix, count in prefix_counter.items():
            if count >= 3:
                pattern = f"^{re.escape(prefix)}\\..*"
                patterns.append({
                    "pattern": pattern,
                    "type": "prefix",
                    "count": count
                })

        # 模式2：特殊结构（如赌博白牌模板）
        special_patterns = [
            (r"com\.id\d{2,4}\.[a-z]{4,8}\d+", "白牌模板结构"),
            (r"com\.h5la\d+\..*", "H5套壳结构"),
            (r".*\.(777|888|168|388|999)$", "幸运数字结尾"),
            (r".*slot.*\d+.*", "slot+数字"),
            (r".*judi.*", "包含judi词"),
            (r".*pinjol.*", "包含pinjol词"),
            (r".*pinjaman.*", "包含pinjaman词"),
        ]

        for pattern, desc in special_patterns:
            match_count = sum(1 for pkg in package_names if re.search(pattern, pkg, re.IGNORECASE))
            if match_count >= 2:
                patterns.append({
                    "pattern": pattern,
                    "type": "special_structure",
                    "description": desc,
                    "count": match_count
                })

        # 按出现频率排序
        patterns.sort(key=lambda x: x['count'], reverse=True)

        return patterns[:20]  # 最多返回20个模式

    def _extract_brands(self, apps_in_category: list, min_count: int = 2) -> list:
        """
        提取品牌名列表

        Args:
            apps_in_category: 该类别下的APP列表
            min_count: 最小出现次数

        Returns:
            品牌名列表
        """
        package_names = [app['package_name'] for app in apps_in_category]

        # 提取品牌候选（包名第二段或第三段）
        brand_candidates = Counter()
        for pkg in package_names:
            parts = pkg.split('.')
            if len(parts) >= 3:
                # com.brand.function → brand
                brand_candidates[parts[1]] += 1
            if len(parts) >= 4:
                # id.co.brand.function → brand
                if parts[0] == 'id' and parts[1] == 'co':
                    brand_candidates[parts[2]] += 1

        # 过滤掉通用词
        generic_brands = {'android', 'app', 'mobile', 'lite', 'pro', 'free', 'game', 'tools'}
        brand_candidates = Counter({k: v for k, v in brand_candidates.items()
                          if k not in generic_brands and v >= min_count})

        # 提取reason中的品牌名（如果有）
        reasons = [app.get('reason', '') for app in apps_in_category]
        reason_text = ' '.join(reasons)
        # 这里简化处理，实际可以结合NER识别

        brands = [
            {"name": brand, "count": count}
            for brand, count in brand_candidates.most_common(30)
        ]

        return brands

    def _extract_domain_structures(self, apps_in_category: list) -> list:
        """
        提取域名结构模式

        Args:
            apps_in_category: 该类别下的APP列表

        Returns:
            域名结构模式列表
        """
        package_names = [app['package_name'] for app in apps_in_category]

        structures = Counter()
        for pkg in package_names:
            parts = pkg.split('.')
            if len(parts) >= 3:
                # 抽象化为结构模式
                structure_parts = []
                for part in parts:
                    if part in ['id', 'co', 'com', 'org', 'net']:
                        structure_parts.append(part)
                    elif re.match(r'^\d+$', part):
                        structure_parts.append('[NUM]')
                    elif len(part) <= 3:
                        structure_parts.append('[SHORT]')
                    else:
                        structure_parts.append('[WORD]')

                structure = '.'.join(structure_parts)
                structures[structure] += 1

        # 保留出现频率>=2的结构
        domain_structures = [
            {"structure": struct, "count": count}
            for struct, count in structures.items()
            if count >= 2
        ]

        domain_structures.sort(key=lambda x: x['count'], reverse=True)

        return domain_structures[:15]

    def learn_rules(self) -> dict:
        """
        学习所有类别的规则

        Returns:
            规则字典
        """
        if not self.data:
            self.load_data()

        classifications = self.data['classifications']

        # 按类别分组
        categories = defaultdict(list)
        for pkg_name, info in classifications.items():
            category = info['category']
            categories[category].append({
                'package_name': pkg_name,
                'category': category,
                'confidence': info['confidence'],
                'reason': info.get('reason', '')
            })

        print(f"\n📊 共 {len(categories)} 个类别")

        # 对每个类别学习规则
        rules = {}
        for category, apps in categories.items():
            print(f"\n⚙️  学习类别: {category} ({len(apps)} 个样本)")

            rules[category] = {
                "category": category,
                "sample_count": len(apps),
                "confidence_threshold": self._calculate_confidence_threshold(apps),
                "keywords": self._extract_keywords(apps),
                "patterns": self._extract_patterns(apps),
                "brands": self._extract_brands(apps),
                "domain_structures": self._extract_domain_structures(apps),
                "high_risk_indicators": self._extract_high_risk_indicators(apps, category)
            }

        self.rules = rules
        print(f"\n✅ 规则学习完成！共 {len(rules)} 个类别")

        return rules

    def _calculate_confidence_threshold(self, apps_in_category: list) -> float:
        """
        计算类别的置信度阈值

        Args:
            apps_in_category: 该类别下的APP列表

        Returns:
            置信度阈值 (0.0 - 1.0)
        """
        confidence_map = {
            'high': 0.9,
            'medium': 0.7,
            'low': 0.5
        }

        confidences = [
            confidence_map.get(app['confidence'], 0.5)
            for app in apps_in_category
        ]

        # 取平均值作为阈值
        return sum(confidences) / len(confidences) if confidences else 0.7

    def _extract_high_risk_indicators(self, apps_in_category: list, category: str) -> list:
        """
        提取高风险指标（仅针对高风险类别）

        Args:
            apps_in_category: 该类别下的APP列表
            category: 类别名

        Returns:
            高风险指标列表
        """
        high_risk_categories = [
            'gambling', 'cash_loan', 'fintech_lending',
            'fake_gps', 'clone_app', 'app_store'
        ]

        if category not in high_risk_categories:
            return []

        indicators = []

        # 从reason中提取高风险特征
        reasons = [app.get('reason', '') for app in apps_in_category]

        # 常见高风险关键词
        risk_keywords = [
            '多头借贷', '共债', '欺诈', '高风险', '伪造', '篡改',
            '模拟器', '虚拟定位', '克隆', '分身', '第三方', '未授权',
            '老虎机', '扑克', '棋牌', '赌博', '返奖', 'RTP'
        ]

        for keyword in risk_keywords:
            count = sum(1 for reason in reasons if keyword in reason)
            if count >= 2:
                indicators.append({
                    "keyword": keyword,
                    "count": count,
                    "ratio": count / len(apps_in_category)
                })

        return indicators

    def save_rules(self, output_file: str):
        """
        保存规则到JSON文件

        Args:
            output_file: 输出文件路径
        """
        if not self.rules:
            raise ValueError("规则尚未学习，请先调用 learn_rules()")

        # 构建输出结构
        output = {
            "meta": {
                "total_apps": self.data['total_apps'],
                "total_categories": len(self.rules),
                "learning_date": "2026-04-26",
                "model": self.data['model'],
                "classification_date": self.data['classification_date']
            },
            "high_risk_categories": [
                'gambling', 'cash_loan', 'fintech_lending',
                'fake_gps', 'clone_app', 'app_store'
            ],
            "rules": self.rules
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"\n💾 规则已保存到: {output_file}")

    def generate_summary_md(self, output_file: str):
        """
        生成规则摘要Markdown文件

        Args:
            output_file: 输出Markdown文件路径
        """
        if not self.rules:
            raise ValueError("规则尚未学习，请先调用 learn_rules()")

        lines = []
        lines.append("# 在线APP分类规则库\n")
        lines.append(f"生成时间: 2026-04-26\n")
        lines.append(f"基于样本: {self.data['total_apps']} 个已分类应用\n")
        lines.append("---\n")

        for category, rules in sorted(self.rules.items(), key=lambda x: x[1]['sample_count'], reverse=True):
            lines.append(f"## {category}\n")
            lines.append(f"- 样本数: {rules['sample_count']}")

            # 关键词
            all_keywords = (
                [k['word'] for k in rules['keywords']['indonesian'][:10]] +
                [k['word'] for k in rules['keywords']['english'][:10]]
            )
            if all_keywords:
                lines.append(f"- 关键词模式: {', '.join(all_keywords[:20])}")

            # 正则模式
            patterns = [p['pattern'] for p in rules['patterns'][:5]]
            if patterns:
                lines.append(f"- 正则模式: {', '.join(patterns[:5])}")

            # 品牌
            brands = [b['name'] for b in rules['brands'][:10]]
            if brands:
                lines.append(f"- 品牌模式: {', '.join(brands[:10])}")

            lines.append("")
            lines.append("---\n")

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f"📝 规则摘要已保存到: {output_file}")


if __name__ == '__main__':
    # 使用示例
    learner = RuleLearner(
        classified_file='outputs/app_analysis/classification_complete_11850.json'
    )

    # 学习规则
    rules = learner.learn_rules()

    # 保存规则
    learner.save_rules('outputs/risk_rules/online_app_classification_rules.json')
    learner.generate_summary_md('outputs/risk_rules/online_app_classification_rules_summary.md')

    print("\n🎉 规则学习完成！")
