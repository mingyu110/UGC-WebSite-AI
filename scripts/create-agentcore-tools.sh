#!/bin/bash
# =============================================================================
# Create AgentCore Browser and Code Interpreter Tools
#
# This script creates the necessary AWS resources for AgentCore built-in tools:
# 1. S3 bucket for Browser session recordings
# 2. IAM role for Browser and Code Interpreter
# 3. Browser Tool
# 4. Code Interpreter Tool
#
# Usage: ./scripts/create-agentcore-tools.sh
#
# Prerequisites:
# - AWS CLI configured with appropriate permissions
# - jq installed for JSON parsing
# =============================================================================

set -e

# Configuration
REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
PROJECT_NAME="ugc-ai-demo"
TIMESTAMP=$(date +%Y%m%d%H%M%S)

# Resource names
S3_BUCKET_NAME="${PROJECT_NAME}-browser-recordings-${ACCOUNT_ID}"
IAM_ROLE_NAME="${PROJECT_NAME}-agentcore-tools-role"
BROWSER_NAME="${PROJECT_NAME}-browser"
CODE_INTERPRETER_NAME="${PROJECT_NAME}-code-interpreter"

echo "=============================================="
echo "Creating AgentCore Tools"
echo "=============================================="
echo "Region: ${REGION}"
echo "Account ID: ${ACCOUNT_ID}"
echo "S3 Bucket: ${S3_BUCKET_NAME}"
echo "IAM Role: ${IAM_ROLE_NAME}"
echo "Browser Name: ${BROWSER_NAME}"
echo "Code Interpreter Name: ${CODE_INTERPRETER_NAME}"
echo "=============================================="

# =============================================================================
# Step 1: Create S3 Bucket for Browser Recordings
# =============================================================================
echo ""
echo "[Step 1/4] Creating S3 bucket for browser recordings..."

if aws s3api head-bucket --bucket "${S3_BUCKET_NAME}" 2>/dev/null; then
    echo "S3 bucket ${S3_BUCKET_NAME} already exists, skipping..."
else
    if [ "$REGION" = "us-east-1" ]; then
        aws s3api create-bucket \
            --bucket "${S3_BUCKET_NAME}" \
            --region "${REGION}"
    else
        aws s3api create-bucket \
            --bucket "${S3_BUCKET_NAME}" \
            --region "${REGION}" \
            --create-bucket-configuration LocationConstraint="${REGION}"
    fi
    echo "S3 bucket created: ${S3_BUCKET_NAME}"
fi

# =============================================================================
# Step 2: Create IAM Role for AgentCore Tools
# =============================================================================
echo ""
echo "[Step 2/4] Creating IAM role for AgentCore tools..."

# Trust policy for AgentCore
TRUST_POLICY=$(cat <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "bedrock-agentcore.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
EOF
)

# Check if role exists
if aws iam get-role --role-name "${IAM_ROLE_NAME}" 2>/dev/null; then
    echo "IAM role ${IAM_ROLE_NAME} already exists, skipping creation..."
    IAM_ROLE_ARN=$(aws iam get-role --role-name "${IAM_ROLE_NAME}" --query 'Role.Arn' --output text)
else
    # Create the role
    IAM_ROLE_ARN=$(aws iam create-role \
        --role-name "${IAM_ROLE_NAME}" \
        --assume-role-policy-document "${TRUST_POLICY}" \
        --description "IAM role for AgentCore Browser and Code Interpreter tools" \
        --query 'Role.Arn' \
        --output text)
    echo "IAM role created: ${IAM_ROLE_ARN}"

    # Wait for role to be available
    sleep 5
fi

# Inline policy for S3 and CloudWatch access
POLICY_DOCUMENT=$(cat <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "S3Permissions",
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket",
                "s3:ListMultipartUploadParts",
                "s3:AbortMultipartUpload"
            ],
            "Resource": [
                "arn:aws:s3:::${S3_BUCKET_NAME}",
                "arn:aws:s3:::${S3_BUCKET_NAME}/*"
            ]
        },
        {
            "Sid": "CloudWatchLogsPermissions",
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
                "logs:DescribeLogStreams"
            ],
            "Resource": "*"
        }
    ]
}
EOF
)

# Attach inline policy
aws iam put-role-policy \
    --role-name "${IAM_ROLE_NAME}" \
    --policy-name "AgentCoreToolsPolicy" \
    --policy-document "${POLICY_DOCUMENT}" 2>/dev/null || true

echo "IAM role ARN: ${IAM_ROLE_ARN}"

# Wait for IAM to propagate
echo "Waiting for IAM role to propagate..."
sleep 10

# =============================================================================
# Step 3: Create Browser Tool
# =============================================================================
echo ""
echo "[Step 3/4] Creating Browser Tool..."

# Check if browser already exists
EXISTING_BROWSERS=$(aws bedrock-agentcore-control list-browsers \
    --region "${REGION}" \
    --query "browsers[?name=='${BROWSER_NAME}'].browserId" \
    --output text 2>/dev/null || echo "")

if [ -n "$EXISTING_BROWSERS" ]; then
    BROWSER_ID="${EXISTING_BROWSERS}"
    echo "Browser Tool already exists: ${BROWSER_ID}"
else
    # Create browser
    BROWSER_RESPONSE=$(aws bedrock-agentcore-control create-browser \
        --region "${REGION}" \
        --name "${BROWSER_NAME}" \
        --description "Browser tool for ${PROJECT_NAME} - web browsing and design extraction" \
        --network-configuration '{"networkMode": "PUBLIC"}' \
        --recording "{\"enabled\": true, \"s3Location\": {\"bucket\": \"${S3_BUCKET_NAME}\", \"prefix\": \"browser-recordings\"}}" \
        --execution-role-arn "${IAM_ROLE_ARN}" \
        --output json)

    BROWSER_ID=$(echo "${BROWSER_RESPONSE}" | jq -r '.browserId')
    BROWSER_ARN=$(echo "${BROWSER_RESPONSE}" | jq -r '.browserArn')
    echo "Browser Tool created!"
    echo "  Browser ID: ${BROWSER_ID}"
    echo "  Browser ARN: ${BROWSER_ARN}"
fi

# =============================================================================
# Step 4: Create Code Interpreter Tool
# =============================================================================
echo ""
echo "[Step 4/4] Creating Code Interpreter Tool..."

# Check if code interpreter already exists
EXISTING_INTERPRETERS=$(aws bedrock-agentcore-control list-code-interpreters \
    --region "${REGION}" \
    --query "codeInterpreters[?name=='${CODE_INTERPRETER_NAME}'].codeInterpreterId" \
    --output text 2>/dev/null || echo "")

if [ -n "$EXISTING_INTERPRETERS" ]; then
    CODE_INTERPRETER_ID="${EXISTING_INTERPRETERS}"
    echo "Code Interpreter Tool already exists: ${CODE_INTERPRETER_ID}"
else
    # Create code interpreter
    CODE_INTERPRETER_RESPONSE=$(aws bedrock-agentcore-control create-code-interpreter \
        --region "${REGION}" \
        --name "${CODE_INTERPRETER_NAME}" \
        --description "Code Interpreter for ${PROJECT_NAME} - code validation and execution" \
        --network-configuration '{"networkMode": "PUBLIC"}' \
        --execution-role-arn "${IAM_ROLE_ARN}" \
        --output json)

    CODE_INTERPRETER_ID=$(echo "${CODE_INTERPRETER_RESPONSE}" | jq -r '.codeInterpreterId')
    CODE_INTERPRETER_ARN=$(echo "${CODE_INTERPRETER_RESPONSE}" | jq -r '.codeInterpreterArn')
    echo "Code Interpreter Tool created!"
    echo "  Code Interpreter ID: ${CODE_INTERPRETER_ID}"
    echo "  Code Interpreter ARN: ${CODE_INTERPRETER_ARN}"
fi

# =============================================================================
# Output Summary
# =============================================================================
echo ""
echo "=============================================="
echo "AgentCore Tools Created Successfully!"
echo "=============================================="
echo ""
echo "Add these environment variables to your deployment:"
echo ""
echo "  export AGENTCORE_BROWSER_ID=\"${BROWSER_ID}\""
echo "  export AGENTCORE_CODE_INTERPRETER_ID=\"${CODE_INTERPRETER_ID}\""
echo "  export AWS_REGION=\"${REGION}\""
echo ""
echo "Or add to your .env file:"
echo ""
echo "  AGENTCORE_BROWSER_ID=${BROWSER_ID}"
echo "  AGENTCORE_CODE_INTERPRETER_ID=${CODE_INTERPRETER_ID}"
echo "  AWS_REGION=${REGION}"
echo ""
echo "=============================================="

# Save to a config file for easy reference
CONFIG_FILE="scripts/.agentcore-tools-config"
cat > "${CONFIG_FILE}" <<EOF
# AgentCore Tools Configuration
# Generated: $(date)

AGENTCORE_BROWSER_ID=${BROWSER_ID}
AGENTCORE_CODE_INTERPRETER_ID=${CODE_INTERPRETER_ID}
AWS_REGION=${REGION}
S3_BUCKET=${S3_BUCKET_NAME}
IAM_ROLE_ARN=${IAM_ROLE_ARN}
EOF

echo "Configuration saved to: ${CONFIG_FILE}"
