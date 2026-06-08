"""
完整应用LLM分批分类

对11,851个应用进行LLM科学分类（2147个好客户独有 + 6892个坏客户独有 + 2812个共有）
采用每批200个应用的策略，约60批次完成
"""

import sys
import os
import json
import pandas as pd
import time
from typing import List, Dict
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))

from utils.llm_client import LLMClient

# 配置日志
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('outputs/app_analysis/batch_classification.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def prepare_app_data():
    """准备所有应用数据，标记来源"""
    logger.info("加载完整应用清单...")

    # 读取三类应用
    good_only_df = pd.read_csv('outputs/app_analysis/good_customer_apps_complete.csv')
    bad_only_df = pd.read_csv('outputs/app_analysis/bad_customer_apps_complete.csv')
    common_df = pd.read_csv('outputs/app_analysis/common_apps_complete.csv')

    # 标记来源并合并
    good_only_df['source'] = 'good_only'
    bad_only_df['source'] = 'bad_only'
    common_df['source'] = 'common'

    all_apps = pd.concat([good_only_df, bad_only_df, common_df], ignore_index=True)

    logger.info(f"总应用数: {len(all_apps)}")
    logger.info(f"  好客户独有: {len(good_only_df)}")
    logger.info(f"  坏客户独有: {len(bad_only_df)}")
    logger.info(f"  共有: {len(common_df)}")

    return all_apps


def create_batch_prompt(apps_batch: List[Dict]) -> str:
    """创建一个批次的prompt"""

    # 构建应用列表JSON
    apps_json = json.dumps([{
        'app': app['app'],
        'source': app['source'],
        'good_count': int(app.get('good_count', 0)),
        'bad_count': int(app.get('bad_count', 0))
    } for app in apps_batch], ensure_ascii=False, indent=2)

    system_prompt = """你是印尼现金贷风控数据分析专家。请基于印尼金融科技常识和应用包名特征，对用户手机安装的应用进行风险分类。

**严格使用以下15个类别名**（不要创造新类别）：

【高风险类别 - 重点关注】
1. cash_loan - 现金贷/小额贷款APP（如：AdaEmi, Kredit Pintar, CashMe, Rupiah Cepat）
2. fintech_lending - 金融科技借贷平台（如：Kredivo, FinAccel, Home Credit, Akulaku, KataPay）
3. gambling - 赌博/棋牌/彩票/老虎机（如：777, domino, slot, poker, togel, higgs）
4. fake_gps - 虚拟定位/位置伪造工具（如：Fake GPS, GPS JoyStick, Location Spoofer）
5. app_store - 第三方应用商店/侧载渠道（如：APKPure, Aptoide, 9Apps, GetJar）
6. clone_app - 应用克隆/双开工具（如：Parallel Space, Dual Space, Clone App, 2Accounts）

【金融机构类别】
7. banking - 银行官方应用（如：BCA Mobile, Mandiri, BRI, BNI, Danamon, CIMB, Permata）
8. ewallet - 电子钱包/支付应用（如：GoPay, OVO, DANA, LinkAja, ShopeePay, Jago）

【消费金融类别】
9. installment - 分期付款应用（如：Cicilan, PayLater, Kredivo分期, Akulaku分期）
10. shopping - 购物电商平台（如：Tokopedia, Shopee, Lazada, Bukalapak, Blibli）

【工具与生活服务类别】
11. transportation - 交通出行（如：Grab, Gojek, Maxim, inDrive, MRT, KRL）
12. food_delivery - 餐饮外卖（如：GoFood, GrabFood, ShopeeFood, Traveloka Eats）
13. utility - 通用工具应用（如：文件管理/浏览器/清理/杀毒/Temu类应用）
14. social_entertainment - 社交娱乐/游戏/短视频（如：WhatsApp, TikTok, Facebook, Instagram, Mobile Legends）
15. productivity - 生产力/办公/财务记账（如：Microsoft Office, Google Docs, Money Manager）
16. religious - 宗教文化应用（如：Al-Quran, Qibla, Tafsir, Muslim Pro）
17. other - 其他无法明确分类的应用

**高风险信号判定标准**：
- 现金贷/借贷类：多头借贷风险，评分高
- 赌博/FakeGPS/AppStore/CloneApp：欺诈风险，评分极高
- 银行/正规电商：低风险，评分低

**类别优先级规则**（当一个应用符合多个类别时，严格按此顺序判断）：
1. **第一优先级 - 高风险具体类别**：fake_gps, clone_app, app_store, gambling, cash_loan
   - 先判断应用是否属于这些高风险类别
   - 如果符合，直接返回该类别，不再判断其他类别
2. **第二优先级 - 金融/消费类别**：fintech_lending, banking, ewallet, installment, shopping, transportation, food_delivery
   - 如果不是高风险类别，再判断是否属于金融/生活服务类别
3. **第三优先级 - 通用类别**：utility, social_entertainment, productivity, religious, education, other
   - 最后判断通用类别
   - **other是最终兜底类别**：只有当应用不属于以上所有类别时，才使用other

**重要原则**：
- utility是通用类别，优先级低于所有具体类别
- 如果一个应用既是utility又是其他具体类别（如fake_gps/clone_app），必须选择**具体类别**
- 例如：com.xxx.fakegps → fake_gps（不是utility）
- 例如：com.xxx.clone → clone_app（不是utility）
- 例如：com.browser → utility（没有更具体类别时）

**判断规则**：
1. 根据包名关键词判断（如loan/pinjaman/kredit→cash_loan；gambling/777/slot→gambling）
2. 好客户独有应用倾向于正规金融机构（banking/ewallet/shopping）
3. 坏客户独有应用倾向于高风险工具（fake_gps/clone_app/gambling/cash_loan）
4. 共有应用中安装次数高的通常是基础应用（WhatsApp/Gojek/Tokopedia等）

请返回JSON格式，每个应用一个分类，必须包含：
- category: 上述15个类别之一
- confidence: high/medium/low（根据包名明确度）
- reason: 20字以内的分类理由（包含关键识别词）"""

    user_prompt = f"""请对以下{len(apps_batch)}个印尼用户安装的应用进行分类：

{apps_json}

请返回**有效JSON**格式（确保能直接解析）：
```json
{{
  "classifications": {{
    "com.example.package": {{
      "category": "类别名（15个标准类别之一）",
      "confidence": "high或medium或low",
      "reason": "20字以内的分类理由"
    }}
  }}
}}
```

**示例参考**：
- id.dana → ewallet (电子钱包DANA)
- com.kredivo → fintech_lending (借贷平台Kredivo)
- com.adakami → cash_loan (现金贷应用AdaEmi)
- com.google.android.gms → utility (Google服务框架)
- com.whatsapp → social_entertainment (社交通信WhatsApp)
"""

    return system_prompt, user_prompt


def classify_batch(client: LLMClient, apps_batch: List[Dict], retry: int = 3) -> Dict:
    """对单个批次进行分类，带重试机制"""

    system_prompt, user_prompt = create_batch_prompt(apps_batch)

    for attempt in range(retry):
        try:
            logger.info(f"  批次分类尝试 {attempt + 1}/{retry}...")

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

            # 找到最后一个}
            last_brace = json_text.rfind('}')
            if last_brace != -1:
                json_text = json_text[:last_brace + 1]

            result = json.loads(json_text)

            if 'classifications' in result:
                logger.info(f"  ✓ 成功分类 {len(result['classifications'])} 个应用")
                return result['classifications']
            else:
                logger.warning(f"  ⚠ 响应格式错误，无classifications字段")

        except json.JSONDecodeError as e:
            logger.error(f"  ✗ JSON解析失败: {e}")
        except Exception as e:
            logger.error(f"  ✗ LLM调用失败: {e}")

        if attempt < retry - 1:
            wait_time = 5 * (attempt + 1)
            logger.info(f"  等待{wait_time}秒后重试...")
            time.sleep(wait_time)

    logger.error(f"  ✗ 批次分类失败，已重试{retry}次")
    return None


def run_batch_classification():
    """运行分批分类"""
    logger.info("="*80)
    logger.info("开始完整应用LLM分批分类")
    logger.info("="*80)

    # 1. 准备数据
    all_apps_df = prepare_app_data()
    all_apps = all_apps_df.to_dict('records')

    # 2. 分批设置
    BATCH_SIZE = 200
    total_apps = len(all_apps)
    num_batches = (total_apps + BATCH_SIZE - 1) // BATCH_SIZE

    logger.info(f"\n分批设置:")
    logger.info(f"  总应用数: {total_apps:,}")
    logger.info(f"  每批大小: {BATCH_SIZE}")
    logger.info(f"  总批次数: {num_batches}")

    # 3. 初始化LLM客户端
    client = LLMClient()

    # 4. 分批处理
    all_classifications = {}
    start_time = time.time()

    for batch_idx in range(num_batches):
        start_idx = batch_idx * BATCH_SIZE
        end_idx = min((batch_idx + 1) * BATCH_SIZE, total_apps)
        batch = all_apps[start_idx:end_idx]

        batch_start = time.time()
        logger.info(f"\n{'='*60}")
        logger.info(f"批次 {batch_idx + 1}/{num_batches} (应用 {start_idx+1}-{end_idx})")
        logger.info(f"{'='*60}")

        result = classify_batch(client, batch)

        if result:
            all_classifications.update(result)
            logger.info(f"  累计分类: {len(all_classifications):,} / {total_apps:,} ({len(all_classifications)/total_apps*100:.1f}%)")
        else:
            logger.error(f"  批次 {batch_idx + 1} 失败，跳过")

        batch_elapsed = time.time() - batch_start
        logger.info(f"  批次耗时: {batch_elapsed:.1f}秒")

        # 速率限制：每批之间等待
        if batch_idx < num_batches - 1:
            wait_time = 3  # 3秒间隔
            logger.info(f"  等待{wait_time}秒...")
            time.sleep(wait_time)

        # 每5批保存一次中间结果（更安全的策略）
        if (batch_idx + 1) % 5 == 0:
            save_intermediate_result(all_classifications, batch_idx + 1)

        # 每批都保存一个紧急备份文件
        save_emergency_backup(all_classifications, batch_idx + 1)

    # 5. 保存最终结果
    elapsed = time.time() - start_time
    logger.info(f"\n{'='*80}")
    logger.info(f"分类完成！")
    logger.info(f"{'='*80}")
    logger.info(f"  总耗时: {elapsed/60:.1f}分钟")
    logger.info(f"  成功分类: {len(all_classifications):,} / {total_apps:,} ({len(all_classifications)/total_apps*100:.1f}%)")

    save_final_result(all_classifications, all_apps_df)

    return all_classifications


def save_intermediate_result(classifications: Dict, batch_num: int):
    """保存中间结果"""
    output_path = f'outputs/app_analysis/classification_intermediate_batch{batch_num}.json'

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(classifications, f, ensure_ascii=False, indent=2)

    logger.info(f"  ✓ 中间结果已保存: {output_path}")


def save_emergency_backup(classifications: Dict, batch_num: int):
    """每批都保存紧急备份文件（轻量级，仅JSON数据）"""
    output_path = f'outputs/app_analysis/classification_backup_latest.json'

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(classifications, f, ensure_ascii=False)

    # 只在每5批时打印日志，避免日志过多
    if batch_num % 5 == 0:
        logger.info(f"  ✓ 紧急备份已更新: {output_path} ({len(classifications):,} 个应用)")


def save_final_result(classifications: Dict, all_apps_df: pd.DataFrame):
    """保存最终结果并生成统计"""
    output_dir = 'outputs/app_analysis'

    # 1. 保存完整分类结果
    result_path = f'{output_dir}/classification_complete_{len(classifications)}.json'

    result_data = {
        'total_apps': len(classifications),
        'classification_date': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
        'model': 'qwen/qwen3.6-plus',
        'classifications': classifications
    }

    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    logger.info(f"\n✓ 完整分类结果已保存: {result_path}")

    # 2. 生成分类统计
    category_counts = Counter([v['category'] for v in classifications.values()])

    stats_data = {
        'total_classified': len(classifications),
        'category_distribution': dict(category_counts.most_common()),
        'high_risk_categories': {
            cat: count for cat, count in category_counts.items()
            if cat in ['cash_loan', 'fintech_lending', 'gambling', 'adult']
        }
    }

    stats_path = f'{output_dir}/classification_statistics.json'
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats_data, f, ensure_ascii=False, indent=2)

    logger.info(f"✓ 分类统计已保存: {stats_path}")

    # 3. 生成带分类的应用清单CSV
    classified_apps = []
    for _, row in all_apps_df.iterrows():
        app = row['app']
        if app in classifications:
            info = classifications[app]
            classified_apps.append({
                'app': app,
                'source': row['source'],
                'good_count': int(row.get('good_count', 0)),
                'bad_count': int(row.get('bad_count', 0)),
                'total_count': int(row.get('total_count', 0)),
                'category': info['category'],
                'confidence': info['confidence'],
                'reason': info['reason']
            })

    classified_df = pd.DataFrame(classified_apps)
    csv_path = f'{output_dir}/app_classification_complete.csv'
    classified_df.to_csv(csv_path, index=False)

    logger.info(f"✓ 带分类的应用清单已保存: {csv_path}")
    logger.info(f"  行数: {len(classified_df):,}")

    # 4. 打印类别分布
    logger.info(f"\n类别分布统计:")
    for cat, count in category_counts.most_common():
        pct = count / len(classifications) * 100
        logger.info(f"  {cat:30s}: {count:5,} ({pct:4.1f}%)")


if __name__ == '__main__':
    run_batch_classification()
