"""
规则引擎分类器 - 基于LLM生成的规则库进行在线APP分类

功能：
1. 加载LLM生成的规则库（JSON格式）
2. 两级分类流程：
   - 第一级：缓存查询（已知APP直接返回）
   - 第二级：规则引擎匹配（新APP实时判定）
3. 多维度评分：
   - 关键词匹配（印尼语/英语特征词）
   - 正则表达式匹配（白牌模板、幸运数字等）
   - 品牌白名单匹配
   - 排除规则过滤
4. 输出分类结果（类别 + 置信度 + 判定依据）

调用方式：
- 在线API: classifier.classify(app_name)
- 批量分类: classifier.batch_classify(app_list)
"""

import json
import os
import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class RuleEngineClassifier:
    """规则引擎分类器"""

    def __init__(self, rules_file: str = None, cache_file: str = None):
        """
        Args:
            rules_file: 规则库文件路径（支持LLM生成的规则或统计方法规则）
            cache_file: 已知APP分类缓存文件路径
        """
        # 优先使用LLM规则，如果不存在则使用统计方法规则
        if rules_file:
            self.rules_file = rules_file
        elif os.path.exists('outputs/risk_rules/online_app_classification_rules_llm.json'):
            self.rules_file = 'outputs/risk_rules/online_app_classification_rules_llm.json'
        else:
            self.rules_file = 'outputs/risk_rules/online_app_classification_rules.json'

        self.cache_file = cache_file or 'outputs/app_analysis/classification_complete_11850.json'

        self.rules = {}
        self.cache = {}
        self.high_risk_categories = []

        # 加载数据
        self._load_cache()
        self._load_rules()

    def _load_cache(self):
        """加载已知APP的分类缓存"""
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 兼容两种格式
                if 'classifications' in data:
                    self.cache = data['classifications']
                else:
                    self.cache = data
            logger.info(f"✅ 加载缓存: {len(self.cache)} 个已知APP")
        else:
            logger.warning(f"⚠️  缓存文件不存在: {self.cache_file}")

    def _load_rules(self):
        """加载LLM生成的规则库"""
        if os.path.exists(self.rules_file):
            with open(self.rules_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.rules = data.get('rules', {})
                self.high_risk_categories = data.get('high_risk_categories', [])
            logger.info(f"✅ 加载规则: {len(self.rules)} 个类别")
        else:
            logger.warning(f"⚠️  规则文件不存在: {self.rules_file}")
            logger.warning("请先执行: python data/rule_learner_llm.py 生成规则库")

    def classify(self, app_name: str, package_name: str = None) -> Dict:
        """
        分类单个APP

        Args:
            app_name: APP名称或包名
            package_name: APP包名（可选）

        Returns:
            分类结果字典 {category, confidence, reason, method, matched_rules}
        """
        pkg = package_name or app_name

        # 第一级：缓存查询
        if pkg in self.cache:
            cached = self.cache[pkg]
            return {
                'package_name': pkg,
                'category': cached.get('category', 'unknown'),
                'confidence': cached.get('confidence', cached.get('confidence', 0.9)),
                'reason': cached.get('reason', '缓存匹配'),
                'method': 'cache_lookup'
            }

        # 第二级：规则引擎匹配
        return self._rule_classify(pkg)

    def _rule_classify(self, pkg: str) -> Dict:
        """
        基于规则引擎分类APP

        Args:
            pkg: APP包名

        Returns:
            分类结果字典
        """
        best_match = None
        best_score = 0.0
        best_method = None

        for category, rules in self.rules.items():
            # 跳过unknown类别
            if category == 'unknown':
                continue

            # 多维度评分
            score, match_details = self._calculate_risk_score(pkg, rules)

            if score > best_score:
                best_score = score
                best_match = category
                best_method = match_details

        # 构建结果
        if best_match and best_score >= 0.7:
            return {
                'package_name': pkg,
                'category': best_match,
                'confidence': best_score,
                'reason': self._generate_reason(best_method),
                'method': 'rule_engine',
                'matched_rules': best_method
            }
        else:
            return {
                'package_name': pkg,
                'category': 'unknown',
                'confidence': 0.0,
                'reason': '未匹配任何规则，等待夜间批量分类',
                'method': 'rule_engine',
                'matched_rules': []
            }

    def _calculate_risk_score(self, pkg: str, rules: Dict) -> Tuple[float, Dict]:
        """
        计算风险评分

        Args:
            pkg: APP包名
            rules: 该类别的规则字典

        Returns:
            (评分, 匹配详情)
        """
        pkg_lower = pkg.lower()
        score = 0.0
        matched = {
            'keywords': [],
            'patterns': [],
            'brands': []
        }

        # 1. 关键词匹配（权重0.3）
        keywords = rules.get('keywords', {})

        # 适配两种格式：字符串数组 或 {word, freq}字典数组
        indonesian_keywords = []
        english_keywords = []

        raw_indonesian = keywords.get('indonesian', [])
        raw_english = keywords.get('english', [])

        for item in raw_indonesian:
            if isinstance(item, str):
                indonesian_keywords.append(item)
            elif isinstance(item, dict):
                indonesian_keywords.append(item.get('word', ''))

        for item in raw_english:
            if isinstance(item, str):
                english_keywords.append(item)
            elif isinstance(item, dict):
                english_keywords.append(item.get('word', ''))

        for kw in indonesian_keywords + english_keywords:
            if kw and kw.lower() in pkg_lower:
                matched['keywords'].append(kw)

        if matched['keywords']:
            score += 0.3

        # 2. 正则表达式匹配（权重0.4）
        patterns = rules.get('patterns', [])
        for pattern_item in patterns:
            # 适配两种格式
            if isinstance(pattern_item, str):
                regex = pattern_item
                pattern_confidence = 0.8
            elif isinstance(pattern_item, dict):
                regex = pattern_item.get('regex', '')
                pattern_confidence = pattern_item.get('confidence', 0.8)
            else:
                continue

            if regex and re.search(regex, pkg, re.IGNORECASE):
                matched['patterns'].append(pattern_item if isinstance(pattern_item, dict) else {'regex': regex})
                score += 0.4 * pattern_confidence

        # 3. 品牌匹配（权重0.25）
        brands = rules.get('brands', [])
        for brand_item in brands:
            # 适配两种格式
            if isinstance(brand_item, str):
                brand_name = brand_item
                brand_confidence = 0.9
            elif isinstance(brand_item, dict):
                brand_name = brand_item.get('name', '')
                brand_confidence = brand_item.get('confidence', 0.9)
            else:
                continue

            if brand_name and brand_name.lower() in pkg_lower:
                matched['brands'].append(brand_item if isinstance(brand_item, dict) else {'name': brand_name})
                score += 0.25 * brand_confidence

        # 4. 排除规则检查（降低置信度）
        exclusion_rules = rules.get('exclusion_rules', [])
        for rule in exclusion_rules:
            if self._check_exclusion_rule(pkg, rule):
                # 触发排除规则，降低置信度
                score *= 0.5

        # 归一化到0-1
        score = min(score, 1.0)

        return score, matched

    def _check_exclusion_rule(self, pkg: str, rule: Dict) -> bool:
        """
        检查排除规则

        Args:
            pkg: APP包名
            rule: 排除规则字典

        Returns:
            是否触发排除规则
        """
        rule_text = rule.get('rule', '').lower()
        pkg_lower = pkg.lower()

        # 简单的关键词匹配排除规则
        # 例如： "如果包含 com.google" → 检查 "com.google" 是否在包名中
        exclusion_keywords = ['com.google', 'com.android', 'com.microsoft', 'com.samsung',
                             'com.bank', 'com.finance', 'candy crush']

        for kw in exclusion_keywords:
            if kw.lower() in pkg_lower:
                return True

        return False

    def _generate_reason(self, match_details: Dict) -> str:
        """
        生成分类理由

        Args:
            match_details: 匹配详情

        Returns:
            分类理由（中文）
        """
        reasons = []

        # 关键词匹配
        if match_details.get('keywords'):
            reasons.append(f"匹配关键词: {', '.join(match_details['keywords'][:5])}")

        # 正则匹配
        if match_details.get('patterns'):
            for pattern in match_details['patterns']:
                desc = pattern.get('description_cn', '')
                if desc:
                    reasons.append(f"正则匹配: {desc}")

        # 品牌匹配
        if match_details.get('brands'):
            brand_names = [b.get('name', '') for b in match_details['brands']]
            reasons.append(f"品牌匹配: {', '.join(brand_names[:3])}")

        return '; '.join(reasons) if reasons else '未匹配任何规则'

    def batch_classify(self, app_list: List[str]) -> List[Dict]:
        """
        批量分类APP

        Args:
            app_list: APP包名列表

        Returns:
            分类结果列表
        """
        results = []
        for app in app_list:
            result = self.classify(app)
            results.append(result)
        return results

    def get_statistics(self) -> Dict:
        """
        获取分类统计信息

        Returns:
            统计信息字典
        """
        stats = {
            'cache_size': len(self.cache),
            'rules_count': len(self.rules),
            'categories': list(self.rules.keys()),
            'high_risk_categories': self.high_risk_categories
        }
        return stats


if __name__ == '__main__':
    # 测试示例
    classifier = RuleEngineClassifier()

    # 获取统计信息
    stats = classifier.get_statistics()
    print(f"📊 分类器统计:")
    print(f"   - 缓存大小: {stats['cache_size']}")
    print(f"   - 规则类别: {stats['rules_count']}")
    print(f"   - 高风险类别: {stats['high_risk_categories']}")

    # 测试分类
    test_apps = [
        'com.id5dan777.ntla337',  # 赌博
        'com.motioncredit.app',   # 信贷
        'com.gojek.app',          # 出行
        'com.unknown.app123',     # 未知
    ]

    print(f"\n🔍 测试分类:")
    for app in test_apps:
        result = classifier.classify(app)
        print(f"  - {app}")
        print(f"    类别: {result['category']}")
        print(f"    置信度: {result['confidence']}")
        print(f"    方法: {result['method']}")
        print(f"    理由: {result['reason']}")
        print()