#!/bin/bash
# ================================================================
# RiskForge AI — v9 特征计算服务 阿里云 ECS 一键部署脚本
# 用法: bash deploy.sh
# 说明: 在 ECS 上执行，自动部署特征计算 API 服务
# ================================================================
set -euo pipefail

SERVICE_DIR="/opt/riskforge-api"
VERSION="v9"

echo "=========================================="
echo " RiskForge AI — 特征计算服务 v9 部署"
echo "=========================================="

# 1. 安装 Docker（如果未安装）
if ! command -v docker &>/dev/null; then
    echo "[1/5] 安装 Docker..."
    apt-get update -qq
    apt-get install -y -qq docker.io docker-compose
    systemctl enable docker
    systemctl start docker
else
    echo "[1/5] Docker 已安装，跳过"
fi

# 2. 创建服务目录
echo "[2/5] 创建服务目录: $SERVICE_DIR"
mkdir -p "$SERVICE_DIR"

# 3. 解压部署包（脚本同级目录下应有 v9.tar.gz）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARBALL="$SCRIPT_DIR/../v9.tar.gz"

if [ ! -f "$TARBALL" ]; then
    echo "   未找到 $TARBALL"
    echo "   请将 v9.tar.gz 放到脚本同级或上级目录"
    exit 1
fi

echo "[3/5] 解压部署包..."
tar -xzf "$TARBALL" -C "$SERVICE_DIR"
echo "   解压完成: $SERVICE_DIR"
ls -la "$SERVICE_DIR"

# 4. 设置 API Key（随机生成，可手动指定）
if [ ! -f "$SERVICE_DIR/.env" ]; then
    echo "[4/5] 生成 API Key..."
    API_KEY=$(openssl rand -hex 16)
    cat > "$SERVICE_DIR/.env" << EOF
FEATURE_API_KEY=$API_KEY
EOF
    echo "   API Key 已写入: $SERVICE_DIR/.env"
    echo "   ⚠️  请立即拷贝备份！风控团队调用时需要此 Key"
else
    echo "[4/5] .env 已存在，跳过"
    API_KEY=$(grep FEATURE_API_KEY "$SERVICE_DIR/.env" | cut -d= -f2)
fi

# 5. 构建并启动 Docker 服务
echo "[5/5] 构建并启动 Docker 服务..."
cd "$SERVICE_DIR/deploy"
docker-compose up -d --build

echo ""
echo "=========================================="
echo " 部署完成！"
echo "=========================================="
echo ""
echo " 服务地址: http://$(curl -s ifconfig.me):8000"
echo " API Key:  $API_KEY"
echo ""
echo " 测试调用:"
echo "   curl -X POST http://<ECS公网IP>:8000/api/v1/calculate \\"
echo "     -H \"Content-Type: application/json\" \\"
echo "     -H \"X-API-Key: $API_KEY\" \\"
echo "     -d '{\"order_id\":\"test\",\"raw_data\":{}}'"
echo ""
echo " 健康检查:"
echo "   curl http://<ECS公网IP>:8000/"
echo ""
echo " 后续更新:"
echo "   1. 将新版本 v10.tar.gz 上传到 $SERVICE_DIR"
echo "   2. 执行:"
echo "      cd $SERVICE_DIR && tar -xzf v10.tar.gz && cd deploy"
echo "      docker-compose up -d --build"
echo ""
echo " API Key 文件: $SERVICE_DIR/.env（请保密！）"
echo "=========================================="
