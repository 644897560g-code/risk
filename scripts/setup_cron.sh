"""
定时任务配置 - 夜间批量分类新APP

功能：
1. 每天凌晨2点自动执行批量分类
2. 扫描未分类APP列表
3. 调用LLM批量分类
4. 结果回写缓存
5. 发送通知

配置方式：
- macOS: 使用 launchd
- Linux: 使用 cron
- Windows: 使用 任务计划程序
"""

import os
import sys
import json
import subprocess
from datetime import datetime

# 项目根目录
PROJECT_ROOT = '/Users/apple/Desktop/agents/risk-agent-cc-indo'
PYTHON_PATH = 'python3'  # 或完整路径如 /usr/bin/python3
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, 'scripts')
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
LOGS_DIR = os.path.join(PROJECT_ROOT, 'logs')


def setup_cron_macos():
    """
    macOS: 配置launchd定时任务
    """
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.riskagent.batchclassify</string>

    <key>ProgramArguments</key>
    <array>
        <string>{PYTHON_PATH}</string>
        <string>{PROJECT_ROOT}/scripts/run_batch_classification.sh</string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>WorkingDirectory</key>
    <string>{PROJECT_ROOT}</string>

    <key>StandardOutPath</key>
    <string>{PROJECT_ROOT}/logs/batch_classification.log</string>

    <key>StandardErrorPath</key>
    <string>{PROJECT_ROOT}/logs/batch_classification_error.log</string>
</dict>
</plist>
"""

    # 写入plist文件
    plist_dir = os.path.join(os.path.expanduser('~'), 'Library', 'LaunchAgents')
    os.makedirs(plist_dir, exist_ok=True)
    plist_file = os.path.join(plist_dir, 'com.riskagent.batchclassify.plist')

    with open(plist_file, 'w') as f:
        f.write(plist_content)

    print(f"✅ launchd配置已保存到: {plist_file}")
    print(f"\n要启用定时任务，请运行:")
    print(f"  launchctl load {plist_file}")
    print(f"\n要禁用定时任务，请运行:")
    print(f"  launchctl unload {plist_file}")


def setup_cron_linux():
    """
    Linux: 配置cron定时任务
    """
    cron_job = f"0 2 * * * cd {PROJECT_ROOT} && {PYTHON_PATH} {PROJECT_ROOT}/scripts/run_batch_classification.sh >> {PROJECT_ROOT}/logs/batch_classification.log 2>&1\n"

    print("✅ 请将以下cron任务添加到crontab:")
    print(f"  {cron_job}")
    print(f"\n要添加cron任务，请运行:")
    print(f"  crontab -e")
    print(f"然后粘贴上面的任务内容")


def create_wrapper_script():
    """
    创建执行脚本（wrapper script）
    """
    script_content = f"""#!/bin/bash
# 夜间批量分类执行脚本

cd {PROJECT_ROOT}

echo "=========================================="
echo "开始执行夜间批量分类任务"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# 设置环境变量
export PYTHONPATH={PROJECT_ROOT}:$PYTHONPATH
export OPENROUTER_API_KEY=$(grep OPENROUTER_API_KEY .env | cut -d '=' -f2)

# 执行批量分类
{PYTHON_PATH} data/batch_classify_new_apps.py \\
    --input data/unknown_apps.json \\
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
"""

    script_dir = SCRIPTS_DIR
    os.makedirs(script_dir, exist_ok=True)
    script_file = os.path.join(script_dir, 'run_batch_classification.sh')

    with open(script_file, 'w') as f:
        f.write(script_content)

    # 设置可执行权限
    os.chmod(script_file, 0o755)

    print(f"✅ 执行脚本已保存到: {script_file}")


def create_input_example():
    """
    创建输入文件示例
    """
    example_data = [
        {"package_name": "com.newapp1.app", "app_name": "新应用1"},
        {"package_name": "com.newapp2.app", "app_name": "新应用2"},
        {"package_name": "com.unknOWN.app123", "app_name": "未知应用"}
    ]

    data_dir = DATA_DIR
    os.makedirs(data_dir, exist_ok=True)
    example_file = os.path.join(data_dir, 'unknown_apps.json')

    with open(example_file, 'w', encoding='utf-8') as f:
        json.dump(example_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 输入文件示例已保存到: {example_file}")


def main():
    """主函数"""
    import platform

    print("# 定时任务配置工具")
    print("=" * 60)

    # 创建执行脚本
    create_wrapper_script()

    # 创建输入示例
    create_input_example()

    # 根据操作系统配置定时任务
    os_name = platform.system()

    print(f"\n检测到操作系统: {os_name}\n")

    if os_name == 'Darwin':  # macOS
        setup_cron_macos()
    elif os_name == 'Linux':
        setup_cron_linux()
    else:
        print(f"⚠️  不支持的操作系统: {os_name}")
        print("请手动配置定时任务，运行以下命令:")
        print(f"  cd {PROJECT_ROOT}")
        print(f"  {PYTHON_PATH} data/batch_classify_new_apps.py --input data/unknown_apps.json")


if __name__ == '__main__':
    main()
