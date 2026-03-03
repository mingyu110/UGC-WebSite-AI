#!/bin/bash
# AWS Deployment Script for UGC AI Demo
#
# Architecture:
# - ECS Fargate: FastAPI backend service
# - AgentCore Runtime: AI Agent (Browser Tool, Code Interpreter)
# - S3 + CloudFront: Static website deployments
# - Lambda + Web Adapter: Dynamic application deployments

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "UGC AI Demo - AWS Deployment"
echo "=========================================="

# Check AWS credentials
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "Error: AWS credentials not configured"
    echo "Please run: aws configure"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=${AWS_REGION:-us-east-1}

echo "AWS Account: $ACCOUNT_ID"
echo "AWS Region: $REGION"
echo ""

# Navigate to infra directory
cd "$PROJECT_ROOT/infra"

# Install CDK dependencies
echo "Installing CDK dependencies..."
npm install

# Compile TypeScript
echo "Compiling TypeScript..."
npx tsc

# Bootstrap CDK (if needed)
echo "Bootstrapping CDK..."
npx cdk bootstrap aws://$ACCOUNT_ID/$REGION 2>/dev/null || true

# Deploy function
deploy_stack() {
    local stack_name=$1
    echo ""
    echo "=========================================="
    echo "Deploying $stack_name..."
    echo "=========================================="
    npx cdk deploy $stack_name --require-approval never
}

# Build and push Docker image
build_and_push_image() {
    echo ""
    echo "=========================================="
    echo "Building and pushing Docker image..."
    echo "=========================================="

    cd "$PROJECT_ROOT"

    # Get ECR repository URI
    ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/ugc-backend"

    # Login to ECR
    aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URI

    # Build image
    docker build -t ugc-backend:latest .

    # Tag and push
    docker tag ugc-backend:latest $ECR_URI:latest
    docker push $ECR_URI:latest

    # Force new deployment
    echo "Forcing new ECS deployment..."
    aws ecs update-service \
        --cluster ugc-backend-cluster \
        --service ugc-backend-service \
        --force-new-deployment \
        --region $REGION

    cd "$PROJECT_ROOT/infra"
}

# Parse arguments
case "${1:-all}" in
    static)
        deploy_stack "UgcStaticDeploymentStack"
        ;;
    dynamic)
        deploy_stack "UgcDynamicDeploymentStack"
        ;;
    backend)
        deploy_stack "UgcBackendStack"
        build_and_push_image
        ;;
    agentcore)
        deploy_stack "UgcAgentCoreRuntimeStack"
        echo ""
        echo "Note: AgentCore agent needs to be created via AWS Console or CLI."
        echo "See the CreateAgentCommand output above."
        ;;
    image)
        build_and_push_image
        ;;
    all)
        deploy_stack "UgcStaticDeploymentStack"
        deploy_stack "UgcDynamicDeploymentStack"
        deploy_stack "UgcAgentCoreRuntimeStack"
        deploy_stack "UgcBackendStack"
        build_and_push_image
        ;;
    *)
        echo "Usage: $0 [static|dynamic|backend|agentcore|image|all]"
        echo ""
        echo "Options:"
        echo "  static    - Deploy S3 + CloudFront for static websites"
        echo "  dynamic   - Deploy Lambda + Web Adapter for dynamic apps"
        echo "  backend   - Deploy ECS Fargate backend service"
        echo "  agentcore - Deploy AgentCore Runtime infrastructure"
        echo "  image     - Build and push Docker image only"
        echo "  all       - Deploy all stacks (default)"
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="

# Show outputs
echo ""
echo "Deployed Resources:"
echo ""

# Get Backend URL
BACKEND_URL=$(aws cloudformation describe-stacks \
    --stack-name UgcBackendStack \
    --query "Stacks[0].Outputs[?OutputKey=='BackendUrl'].OutputValue" \
    --output text 2>/dev/null || echo "Not deployed")

if [ "$BACKEND_URL" != "Not deployed" ] && [ -n "$BACKEND_URL" ]; then
    echo "Backend API: $BACKEND_URL"
    echo ""
    echo "Test the API:"
    echo "  curl $BACKEND_URL/health"
    echo ""
    echo "Frontend Configuration:"
    echo "  Update frontend/.env.local:"
    echo "    NEXT_PUBLIC_API_URL=$BACKEND_URL"
fi

# Get CloudFront Domain
CF_DOMAIN=$(aws cloudformation describe-stacks \
    --stack-name UgcStaticDeploymentStack \
    --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDomain'].OutputValue" \
    --output text 2>/dev/null || echo "Not deployed")

if [ "$CF_DOMAIN" != "Not deployed" ] && [ -n "$CF_DOMAIN" ]; then
    echo ""
    echo "Static Deployment CDN: https://$CF_DOMAIN"
fi

echo ""
echo "Done!"
