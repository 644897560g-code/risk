"""
使用LLM对好坏客户应用进行科学分类

基于全量分析结果，将去重后的应用列表发送给LLM进行风险分类
"""

import sys
import os
import json
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))

from utils.llm_client import LLMClient

# 配置日志
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def prepare_app_lists():
    """准备去重后的应用列表 - 基于完整数据集"""
    summary_path = "outputs/app_analysis/app_analysis_summary.json"
    with open(summary_path, 'r', encoding='utf-8') as f:
        summary = json.load(f)

    # 提取完整的好客户独有应用列表（从CSV）
    good_only_path = "outputs/app_analysis/good_only_apps.csv"
    df_good_only = pd.read_csv(good_only_path)
    good_only_apps = df_good_only['app'].tolist()

    # 完整的坏客户独有应用列表（从CSV读取）
    bad_only_path = "outputs/app_analysis/high_risk_apps.csv"
    df_bad_only = pd.read_csv(bad_only_path)
    bad_only_apps = df_bad_only['app'].tolist()

    # 从common apps中提取所有应用（有好坏客户都安装的应用）
    common_apps_path = "outputs/app_analysis/common_apps.csv"
    df_common = pd.read_csv(common_apps_path)
    common_apps = df_common['app'].tolist()

    logger.info(f"好客户独有应用: {len(good_only_apps)} 个")
    logger.info(f"坏客户独有应用: {len(bad_only_apps)} 个")
    logger.info(f"共有应用: {len(common_apps)} 个")

    return good_only_apps, bad_only_apps, common_apps


def classify_apps_with_llm(good_apps, bad_apps, common_apps):
    """使用LLM对应用进行分类"""
    client = LLMClient()

    # 构建prompt
    system_prompt = """你是印尼现金贷风控数据分析专家。请基于印尼金融科技常识，对用户手机安装的应用进行风险分类。

你的任务是将应用列表分配到以下风险类别中：

1. **banking** - 银行类应用（如BCA、Mandiri、BRI、BNI、DanDan等印尼各大银行APP）
2. **ewallet** - 电子钱包（如GoPay、OVO、DANA、LinkAja、ShopeePay等）
3. **fintech_lending** - 金融科技借贷平台（如Kredivo、FinAccel、Home Credit、AdaEmi、KataPay等）
4. **cash_loan** - 现金贷应用（快速小额贷款APP，通常名称包含pinjaman、uang、dana、rupiah等）
5. **installment** - 分期付款应用
6. **gambling** - 赌博/棋牌/老虎机类应用（高风险信号，如777、domino、slot等）
7. **adult** - 成人内容应用（高风险信号）
8. **utility** - 工具类应用（浏览器、文件管理器、清理工具、VPN、FakeGPS等）
9. **social_entertainment** - 社交娱乐/游戏/短视频应用
10. **shopping** - 购物电商应用
11. **productivity** - 生产力/办公/财务记账应用
12. **transportation** - 交通出行应用（如Grab、Gojek、租车软件等）
13. **religious** - 宗教/文化应用（如Quran、Qibla、Tafsir等）

请返回JSON格式，每个应用一个分类。对于不确定的应用，根据包名关键词判断。

特别注意：
- 好客户独有应用通常代表保守型/保护性应用特征
- 坏客户高频应用通常代表高风险借贷或多头借贷信号
- 赌博、成人内容、VPN、FakeGPS、接码平台、第三方应用商店属于高风险信号
- 正规银行、大型电商、生产力工具通常属于低风险信号"""

    # 构建用户消息 - 分批处理以避免token限制
    # 好客户应用
    good_apps_json = json.dumps(good_apps, ensure_ascii=False, indent=2)
    # 坏客户独有应用（取Top 200按频次）
    bad_apps_top = bad_apps[:200] if len(bad_apps) > 200 else bad_apps
    bad_apps_json = json.dumps(bad_apps_top, ensure_ascii=False, indent=2)
    # 共有应用（取Top 100按频次）
    common_apps_top = common_apps[:100] if len(common_apps) > 100 else common_apps
    common_apps_json = json.dumps(common_apps_top, ensure_ascii=False, indent=2)

    user_message = f"""请对以下印尼现金贷客户的应用进行分类：

**好客户独有应用 ({len(good_apps)}个)：**
{good_apps_json}

**坏客户独有应用Top {len(bad_apps_top)}个（共{len(bad_apps)}个）：**
{bad_apps_json}

**共有应用Top {len(common_apps_top)}个（共{len(common_apps)}个）：**
{common_apps_json}

请返回JSON格式：
```json
{{
  "classifications": {{
    "package.name.here": {{
      "category": "类别名称",
      "confidence": "high/medium/low",
      "reason": "分类理由（简短说明）"
    }},
    ...
  }},
  "summary": {{
    "good_only_summary": "好客户应用整体特征总结（50字以内）",
    "bad_apps_summary": "坏客户应用整体特征总结（50字以内）",
    "key_insights": "关键洞察：好坏客户应用差异的核心发现（100字以内）"
  }}
}}
```

请确保返回有效的JSON格式。"""

    logger.info("发送应用分类请求到LLM...")
    logger.info(f"总应用数: {len(good_apps) + len(bad_apps_top) + len(common_apps_top)}")

    response = client.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=0
    )

    return response


def parse_llm_response(response_text):
    """解析LLM响应，提取JSON"""
    # 尝试提取JSON（可能在markdown代码块中）
    json_text = response_text

    # 查找JSON代码块
    if "```json" in response_text:
        json_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        json_text = response_text.split("```")[1].split("```")[0].strip()

    # 尝试解析
    try:
        result = json.loads(json_text)
        return result
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败: {e}")
        # 尝试找到第一个{和最后一个}之间的内容
        start = json_text.find('{')
        end = json_text.rfind('}')
        if start != -1 and end != -1:
            try:
                result = json.loads(json_text[start:end+1])
                return result
            except:
                pass

        # 如果都失败，返回None
        return None


def save_classification(result):
    """保存分类结果"""
    output_dir = "outputs/app_analysis"
    os.makedirs(output_dir, exist_ok=True)

    # 保存完整分类结果
    output_path = f"{output_dir}/app_classification_result.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info(f"分类结果已保存到: {output_path}")

    # 生成按类别统计的CSV
    if result and 'classifications' in result:
        classifications = result['classifications']

        rows = []
        for app, info in classifications.items():
            rows.append({
                'app': app,
                'category': info.get('category', 'unknown'),
                'confidence': info.get('confidence', 'unknown'),
                'reason': info.get('reason', '')
            })

        df = pd.DataFrame(rows)
        csv_path = f"{output_dir}/app_classification_by_category.csv"
        df.to_csv(csv_path, index=False)

        logger.info(f"分类详情已保存到: {csv_path}")

        # 生成类别统计表
        category_stats = df.groupby('category').size().reset_index(name='count')
        category_stats = category_stats.sort_values('count', ascending=False)
        stats_path = f"{output_dir}/category_statistics.csv"
        category_stats.to_csv(stats_path, index=False)

        logger.info(f"类别统计已保存到: {stats_path}")


def main():
    logger.info("="*80)
    logger.info("开始使用LLM进行应用科学分类")
    logger.info("="*80)

    # 1. 准备应用列表
    good_apps, bad_apps, common_apps = prepare_app_lists()

    # 2. 调用LLM分类
    response = classify_apps_with_llm(good_apps, bad_apps, common_apps)

    logger.info("\n" + "="*80)
    logger.info("LLM分类完成")
    logger.info("="*80)

    print("\n【LLM响应预览】")
    print(response[:500] + "..." if len(response) > 500 else response)

    # 3. 解析响应
    result = parse_llm_response(response)

    if result:
        # 4. 保存结果
        save_classification(result)

        # 5. 打印摘要
        if 'summary' in result:
            print("\n【分类摘要】")
            summary = result['summary']
            print(f"好客户应用特征: {summary.get('good_only_summary', 'N/A')}")
            print(f"坏客户应用特征: {summary.get('bad_apps_summary', 'N/A')}")
            print(f"关键洞察: {summary.get('key_insights', 'N/A')}")
    else:
        logger.error("LLM响应解析失败，原始响应已保存")
        # 保存原始响应
        with open("outputs/app_analysis/llm_raw_response.txt", 'w', encoding='utf-8') as f:
            f.write(response)

    return result


if __name__ == '__main__':
    main()
