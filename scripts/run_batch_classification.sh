#!/bin/bash
# 夜间批量分类执行脚本

cd /Users/apple/Desktop/agents/risk-agent-cc-indo

echo "=========================================="
echo "开始执行夜间批量分类任务"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# 设置环境变量
export PYTHONPATH=/Users/apple/Desktop/agents/risk-agent-cc-indo:$PYTHONPATH
export OPENROUTER_API_KEY=$(grep OPENROUTER_API_KEY .env | cut -d '=' -f2)

# 执行批量分类
python3 data/batch_classify_new_apps.py \
    --input data/unknown_apps.json \
    --output outputs/app_analysis/batch_classification_$(date '+%Y%m%d').md

# 检查执行结果
if [ $? -eq 0 ]; then
    echo "✅ 批量分类执行成功"
else
    echo "❌ 批量分类执行失败"
fi

echo "=========================================="
echo "任务执行完成"
echo "=========================================="
