#!/bin/bash
# Build Docker image using AWS CodeBuild
# No local Docker required

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=${AWS_REGION:-us-east-1}
PROJECT_NAME="ugc-backend-build"

echo "=========================================="
echo "Building Docker image with AWS CodeBuild"
echo "=========================================="
echo "Account: $ACCOUNT_ID"
echo "Region: $REGION"
echo ""

# Create ECR repository if it doesn't exist
echo "Ensuring ECR repository exists..."
aws ecr describe-repositories --repository-names ugc-backend --region $REGION 2>/dev/null || \
    aws ecr create-repository --repository-name ugc-backend --region $REGION

# Create CodeBuild service role if it doesn't exist
ROLE_NAME="ugc-codebuild-service-role"
ROLE_ARN="arn:aws:iam::$ACCOUNT_ID:role/$ROLE_NAME"

if ! aws iam get-role --role-name $ROLE_NAME 2>/dev/null; then
    echo "Creating CodeBuild service role..."

    # Create trust policy
    cat > /tmp/trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "codebuild.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document file:///tmp/trust-policy.json

    # Attach policies
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser

    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess

    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

    # Wait for role propagation
    echo "Waiting for role propagation..."
    sleep 10
fi

# Create or update CodeBuild project
echo "Creating/updating CodeBuild project..."

# First, create S3 bucket for source if it doesn't exist
SOURCE_BUCKET="ugc-codebuild-source-$ACCOUNT_ID-$REGION"
aws s3 mb s3://$SOURCE_BUCKET --region $REGION 2>/dev/null || true

# Package source code
echo "Packaging source code..."
cd "$PROJECT_ROOT"
zip -r /tmp/source.zip . -x "*.git*" -x "node_modules/*" -x "venv/*" -x "*.pyc" -x "__pycache__/*" -x "infra/node_modules/*" -x "frontend/node_modules/*" -x "infra/cdk.out/*"

# Upload to S3
echo "Uploading source to S3..."
aws s3 cp /tmp/source.zip s3://$SOURCE_BUCKET/source.zip

# Create CodeBuild project
cat > /tmp/codebuild-project.json << EOF
{
  "name": "$PROJECT_NAME",
  "description": "Build UGC Backend Docker image",
  "source": {
    "type": "S3",
    "location": "$SOURCE_BUCKET/source.zip"
  },
  "artifacts": {
    "type": "NO_ARTIFACTS"
  },
  "environment": {
    "type": "LINUX_CONTAINER",
    "image": "aws/codebuild/amazonlinux2-x86_64-standard:5.0",
    "computeType": "BUILD_GENERAL1_MEDIUM",
    "privilegedMode": true,
    "environmentVariables": [
      {
        "name": "AWS_DEFAULT_REGION",
        "value": "$REGION"
      },
      {
        "name": "AWS_ACCOUNT_ID",
        "value": "$ACCOUNT_ID"
      }
    ]
  },
  "serviceRole": "$ROLE_ARN",
  "timeoutInMinutes": 30
}
EOF

# Try to create or update project
aws codebuild create-project --cli-input-json file:///tmp/codebuild-project.json 2>/dev/null || \
    aws codebuild update-project --cli-input-json file:///tmp/codebuild-project.json

# Start build
echo ""
echo "Starting CodeBuild..."
BUILD_ID=$(aws codebuild start-build --project-name $PROJECT_NAME --query 'build.id' --output text)
echo "Build ID: $BUILD_ID"

# Wait for build to complete
echo ""
echo "Waiting for build to complete (this may take 5-10 minutes)..."
while true; do
    STATUS=$(aws codebuild batch-get-builds --ids $BUILD_ID --query 'builds[0].buildStatus' --output text)
    PHASE=$(aws codebuild batch-get-builds --ids $BUILD_ID --query 'builds[0].currentPhase' --output text)

    echo "Status: $STATUS, Phase: $PHASE"

    if [ "$STATUS" = "SUCCEEDED" ]; then
        echo ""
        echo "=========================================="
        echo "Build completed successfully!"
        echo "=========================================="
        echo "Image: $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/ugc-backend:latest"
        break
    elif [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "FAULT" ] || [ "$STATUS" = "STOPPED" ]; then
        echo ""
        echo "Build failed with status: $STATUS"
        echo "Check CloudWatch Logs for details"
        exit 1
    fi

    sleep 15
done
