"""
测试数据分析Agent - 使用全部短链数据
"""

import os
import sys
import json
import logging
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(__file__))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'logs/test_data_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)

logger = logging.getLogger(__name__)


def main():
    """主函数"""
    from agents.data_analysis_agent import DataAnalysisAgent
    from data.data_loader import DataLoader

    logger.info("="*60)
    logger.info("测试数据分析Agent - 使用全部短链数据")
    logger.info("="*60)

    # 创建Agent
    agent = DataAnalysisAgent()
    loader = DataLoader()

    # 加载数据
    logger.info("步骤1: 加载短链文件...")
    short_links = loader.load_short_links()
    logger.info(f"加载了 {len(short_links)} 条短链")

    logger.info("步骤2: 加载建模样本...")
    model_samples = loader.load_model_samples()
    logger.info(f"加载了 {len(model_samples)} 条建模样本")

    # 测试参数
    # sample_size: 控制用于分析的样本数量（避免过多API调用和token消耗）
    # 注意: 由于prompt过长（253万token超100万限制），需要减少样本数
    # 建议: 先用10-20条测试LLM调用
    sample_size = 20

    logger.info(f"步骤3: 开始数据分析（使用 {sample_size} 条样本）...")

    # 运行分析
    try:
        result = agent.run({
            'short_links': short_links,
            'model_samples': model_samples,
            'sample_size': sample_size
        })

        logger.info("数据分析完成！")
        from utils.json_utils import custom_json_dumps
        logger.info(f"知识库大小: {len(custom_json_dumps(result, ensure_ascii=False))} 字节")

        # 打印摘要
        if 'knowledge_base' in result:
            kb = result['knowledge_base']
            logger.info(f"样本总数: {kb.get('summary', {}).get('total_samples', 0)}")
            logger.info(f"逾期率: {kb.get('summary', {}).get('overdue_rate', 0):.2%}")

            # 检查各模块
            if 'base_analysis' in kb:
                logger.info("✅ 基础信息分析完成")
            if 'app_analysis' in kb:
                logger.info("✅ 应用列表分析完成")
            if 'fdc_analysis' in kb:
                logger.info("✅ FDC数据分析完成")
            if 'risk_rules' in kb:
                logger.info(f"✅ 识别了 {len(kb['risk_rules'])} 条风险规则")

        logger.info("="*60)
        logger.info("测试完成！知识库已保存到 outputs/knowledge_base/knowledge_base.json")
        logger.info("="*60)

        return 0

    except Exception as e:
        logger.error(f"数据分析失败: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
