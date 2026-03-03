#!/bin/bash
# Deploy script for UGC AI Demo infrastructure

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Parse arguments
STACK_NAME="${1:-all}"
AWS_REGION="${AWS_REGION:-us-east-1}"

echo "=== Deploying UGC AI Demo Infrastructure ==="
echo "Region: $AWS_REGION"
echo "Stack: $STACK_NAME"

cd "$PROJECT_ROOT/infra"

# Bootstrap CDK if needed
if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region "$AWS_REGION" &> /dev/null; then
    echo "Bootstrapping CDK..."
    npx cdk bootstrap "aws://$(aws sts get-caller-identity --query Account --output text)/$AWS_REGION"
fi

# Deploy stacks
case "$STACK_NAME" in
    "static")
        echo "Deploying Static Deployment Stack..."
        npx cdk deploy UgcStaticDeploymentStack --require-approval never
        ;;
    "dynamic")
        echo "Deploying Dynamic Deployment Stack..."
        npx cdk deploy UgcDynamicDeploymentStack --require-approval never
        ;;
    "all")
        echo "Deploying all stacks..."
        npx cdk deploy --all --require-approval never
        ;;
    *)
        echo "Unknown stack: $STACK_NAME"
        echo "Usage: $0 [static|dynamic|all]"
        exit 1
        ;;
esac

echo "=== Deployment complete ==="

# Show outputs
echo ""
echo "Stack Outputs:"
aws cloudformation describe-stacks --stack-name UgcStaticDeploymentStack --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs' --output table 2>/dev/null || true
aws cloudformation describe-stacks --stack-name UgcDynamicDeploymentStack --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs' --output table 2>/dev/null || true
