#!/bin/bash
# ================================================================
# RiskForge AI — 阿里云 ECS 首次部署脚本
# 用  法: bash scripts/deploy.sh <your_github_username>
# 说  明: 在刚买的 ECS 上执行，自动初始化环境
# ================================================================
set -euo pipefail

GITHUB_USER="${1:?请提供 GitHub 用户名: bash scripts/deploy.sh <username>}"
REPO_NAME="riskforge-ai"
APP_DIR="/opt/riskforge"

echo "=========================================="
echo " RiskForge AI — 阿里云 ECS 初始化"
echo "=========================================="

# 1. 系统更新 + 安装 Docker
echo "[1/6] 安装 Docker..."
apt-get update -qq
apt-get install -y -qq docker.io docker-compose nginx certbot python3-certbot-nginx
systemctl enable docker
systemctl start docker

# 2. 创建应用目录
echo "[2/6] 创建应用目录: $APP_DIR"
mkdir -p "$APP_DIR"
cd "$APP_DIR"

# 3. 克隆私有仓库（需要 Personal Access Token）
echo "[3/6] 克隆仓库..."
echo "    → 请在 GitHub 生成 Personal Access Token (repo 权限)"
echo "    → 访问: https://github.com/settings/tokens"
read -sp "    GitHub Personal Access Token: " GH_TOKEN
echo ""
git clone "https://${GITHUB_USER}:${GH_TOKEN}@github.com/${GITHUB_USER}/${REPO_NAME}.git" .
git config credential.helper store

# 4. 生成密钥
echo "[4/6] 生成环境密钥..."
cat > .env << EOF
API_KEY=$(openssl rand -hex 16)
JWT_SECRET=$(openssl rand -hex 32)
DOCKER_USERNAME=${GITHUB_USER}
EOF

# 5. 创建持久化数据目录
echo "[5/6] 创建数据目录..."
mkdir -p data outputs
chmod 777 data outputs

# 6. 启动服务（首次先本地构建）
echo "[6/6] 首次启动（本地构建镜像）..."
docker-compose up -d --build

echo ""
echo "=========================================="
echo " 部署完成！"
echo "=========================================="
echo ""
echo " 访问地址: http://$(curl -s ifconfig.me):5173"
echo ""
echo " 后续更新:"
echo "   1. 本地开发 → push 到 GitHub main 分支"
echo "   2. CI/CD 自动构建镜像并推送"
echo "   3. 服务器上执行:"
echo "      cd $APP_DIR && docker-compose pull && docker-compose up -d"
echo ""
echo " JWT密钥: 已写入 $APP_DIR/.env"
echo " 请立即拷贝备份！"
echo "=========================================="
