#!/bin/bash
# Deploy Next.js frontend to Lambda + Web Adapter

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
DEPLOY_DIR="$FRONTEND_DIR/deploy-package"
LAMBDA_FUNCTION="ugc-frontend-app"
AWS_REGION="${AWS_REGION:-us-east-1}"
S3_BUCKET="ugc-dynamic-deployments-947472889616-us-east-1"

echo "=== Deploying Next.js Frontend to Lambda ==="

# Clean and create deploy directory
rm -rf "$DEPLOY_DIR"
mkdir -p "$DEPLOY_DIR"

# Copy standalone output
echo "Copying standalone build..."
cp -r "$FRONTEND_DIR/.next/standalone/"* "$DEPLOY_DIR/"

# Copy static assets
echo "Copying static assets..."
mkdir -p "$DEPLOY_DIR/frontend/.next/static"
cp -r "$FRONTEND_DIR/.next/static/"* "$DEPLOY_DIR/frontend/.next/static/"

# Copy public folder
if [ -d "$FRONTEND_DIR/public" ]; then
    echo "Copying public folder..."
    cp -r "$FRONTEND_DIR/public" "$DEPLOY_DIR/frontend/"
fi

# Create run.sh for Lambda Web Adapter
echo "Creating run.sh..."
cat > "$DEPLOY_DIR/run.sh" << 'EOF'
#!/bin/bash
export NODE_ENV=production
export PORT=${PORT:-3000}
cd /var/task/frontend
exec node server.js
EOF
chmod +x "$DEPLOY_DIR/run.sh"

# Create deployment zip
echo "Creating deployment package..."
cd "$DEPLOY_DIR"
zip -r -q ../frontend-lambda.zip .

# Upload to S3
echo "Uploading to S3..."
aws s3 cp "$FRONTEND_DIR/frontend-lambda.zip" "s3://$S3_BUCKET/frontend-lambda.zip" --region "$AWS_REGION"

# Check if Lambda function exists
if aws lambda get-function --function-name "$LAMBDA_FUNCTION" --region "$AWS_REGION" 2>/dev/null; then
    echo "Updating existing Lambda function..."
    aws lambda update-function-code \
        --function-name "$LAMBDA_FUNCTION" \
        --s3-bucket "$S3_BUCKET" \
        --s3-key "frontend-lambda.zip" \
        --region "$AWS_REGION"
else
    echo "Creating new Lambda function..."
    ROLE_ARN=$(aws cloudformation describe-stacks \
        --stack-name UgcDynamicDeploymentStack \
        --query "Stacks[0].Outputs[?OutputKey=='LambdaRoleArn'].OutputValue" \
        --output text \
        --region "$AWS_REGION")

    LAYER_ARN=$(aws cloudformation describe-stacks \
        --stack-name UgcDynamicDeploymentStack \
        --query "Stacks[0].Outputs[?OutputKey=='WebAdapterLayerArn'].OutputValue" \
        --output text \
        --region "$AWS_REGION")

    aws lambda create-function \
        --function-name "$LAMBDA_FUNCTION" \
        --runtime "nodejs18.x" \
        --role "$ROLE_ARN" \
        --handler "run.sh" \
        --code "S3Bucket=$S3_BUCKET,S3Key=frontend-lambda.zip" \
        --timeout 30 \
        --memory-size 1024 \
        --environment "Variables={AWS_LAMBDA_EXEC_WRAPPER=/opt/bootstrap,PORT=3000,NODE_ENV=production,MOCK_MODE=true,NEXT_PUBLIC_USE_MOCK=true}" \
        --layers "$LAYER_ARN" \
        --region "$AWS_REGION"

    # Add Function URL
    aws lambda add-permission \
        --function-name "$LAMBDA_FUNCTION" \
        --statement-id "FunctionURLAllowPublicAccess" \
        --action "lambda:InvokeFunctionUrl" \
        --principal "*" \
        --function-url-auth-type "NONE" \
        --region "$AWS_REGION" 2>/dev/null || true

    aws lambda create-function-url-config \
        --function-name "$LAMBDA_FUNCTION" \
        --auth-type "NONE" \
        --cors "AllowOrigins=*,AllowMethods=*,AllowHeaders=*" \
        --region "$AWS_REGION"
fi

# Wait for update to complete
echo "Waiting for Lambda update..."
aws lambda wait function-updated --function-name "$LAMBDA_FUNCTION" --region "$AWS_REGION" 2>/dev/null || true

# Get Function URL
FUNCTION_URL=$(aws lambda get-function-url-config \
    --function-name "$LAMBDA_FUNCTION" \
    --query "FunctionUrl" \
    --output text \
    --region "$AWS_REGION" 2>/dev/null || echo "N/A")

echo ""
echo "=== Deployment Complete ==="
echo "Lambda Function: $LAMBDA_FUNCTION"
echo "Function URL: $FUNCTION_URL"
echo ""
