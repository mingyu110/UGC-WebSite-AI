#!/bin/bash
# =============================================================================
# ECS 后端服务一键部署脚本
# 使用 CodeBuild 构建镜像并部署到 ECS Fargate
# =============================================================================

set -e

REGION="us-east-1"
PROJECT_NAME="ugc-backend-build"
CLUSTER="ugc-backend-cluster"
SERVICE="ugc-backend-service"

echo "=============================================="
echo "ECS 后端服务部署"
echo "=============================================="
echo "区域: $REGION"
echo "CodeBuild 项目: $PROJECT_NAME"
echo "ECS 集群: $CLUSTER"
echo "ECS 服务: $SERVICE"
echo ""

echo "=== 步骤 1: 触发 CodeBuild 构建 ==="
BUILD_ID=$(aws codebuild start-build \
  --project-name $PROJECT_NAME \
  --region $REGION \
  --query 'build.id' --output text)
echo "构建 ID: $BUILD_ID"

echo ""
echo "=== 步骤 2: 等待构建完成 ==="
while true; do
  STATUS=$(aws codebuild batch-get-builds \
    --ids "$BUILD_ID" \
    --region $REGION \
    --query 'builds[0].buildStatus' --output text)
  echo "$(date +%H:%M:%S) - 构建状态: $STATUS"

  if [ "$STATUS" = "SUCCEEDED" ]; then
    echo "✅ 构建成功！"
    break
  elif [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "STOPPED" ]; then
    echo "❌ 构建失败！请检查 CodeBuild 日志"
    exit 1
  fi
  sleep 10
done

echo ""
echo "=== 步骤 3: 更新 ECS 服务 ==="
aws ecs update-service \
  --cluster $CLUSTER \
  --service $SERVICE \
  --force-new-deployment \
  --region $REGION > /dev/null
echo "ECS 部署已启动"

echo ""
echo "=== 步骤 4: 等待部署完成 ==="
while true; do
  PRIMARY_COUNT=$(aws ecs describe-services \
    --cluster $CLUSTER \
    --services $SERVICE \
    --region $REGION \
    --query 'services[0].deployments[?status==`PRIMARY`].runningCount | [0]' --output text)

  TOTAL=$(aws ecs describe-services \
    --cluster $CLUSTER \
    --services $SERVICE \
    --region $REGION \
    --query 'services[0].runningCount' --output text)

  echo "$(date +%H:%M:%S) - 运行中任务: $TOTAL, Primary: $PRIMARY_COUNT"

  if [ "$PRIMARY_COUNT" = "1" ]; then
    echo "✅ 部署完成！"
    break
  fi
  sleep 15
done

echo ""
echo "=============================================="
echo "部署成功！"
echo "=============================================="
echo "后端地址: http://ugc-backend-alb-938534309.us-east-1.elb.amazonaws.com"
echo ""
echo "健康检查: curl http://ugc-backend-alb-938534309.us-east-1.elb.amazonaws.com/health"
