#!/bin/bash
# =============================================================================
# 修复 Lambda 动态网站部署的 IAM 权限
# =============================================================================

set -e

ROLE_NAME="AmazonBedrockAgentCoreSDKRuntime-us-east-1-201eb2b3a8"
POLICY_NAME="UGCLambdaDeploymentPolicy"
REGION="us-east-1"

echo "=============================================="
echo "修复 Lambda 部署 IAM 权限"
echo "=============================================="
echo "角色: $ROLE_NAME"
echo "策略: $POLICY_NAME"
echo ""

# Create policy document
cat > /tmp/lambda-deploy-policy.json << 'POLICY'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "LambdaFullDeployment",
            "Effect": "Allow",
            "Action": [
                "lambda:*"
            ],
            "Resource": "*"
        },
        {
            "Sid": "DynamoDBFullDeployment",
            "Effect": "Allow",
            "Action": [
                "dynamodb:*"
            ],
            "Resource": "*"
        },
        {
            "Sid": "IAMRoleManagement",
            "Effect": "Allow",
            "Action": [
                "iam:CreateRole",
                "iam:AttachRolePolicy",
                "iam:PassRole",
                "iam:GetRole",
                "iam:PutRolePolicy",
                "iam:DeleteRolePolicy",
                "iam:DetachRolePolicy",
                "iam:DeleteRole"
            ],
            "Resource": "*"
        },
        {
            "Sid": "EC2VPCAccess",
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeSecurityGroups",
                "ec2:DescribeSubnets",
                "ec2:DescribeVpcs",
                "ec2:DescribeNetworkInterfaces",
                "ec2:CreateNetworkInterface",
                "ec2:DeleteNetworkInterface",
                "ec2:DescribeVpcEndpoints"
            ],
            "Resource": "*"
        },
        {
            "Sid": "APIGatewayAccess",
            "Effect": "Allow",
            "Action": [
                "apigateway:*"
            ],
            "Resource": "*"
        },
        {
            "Sid": "CloudFrontAccess",
            "Effect": "Allow",
            "Action": [
                "cloudfront:*"
            ],
            "Resource": "*"
        }
    ]
}
POLICY

# Check if policy exists
POLICY_ARN=$(aws iam list-policies --query "Policies[?PolicyName=='$POLICY_NAME'].Arn" --output text 2>/dev/null)

if [ -z "$POLICY_ARN" ] || [ "$POLICY_ARN" = "None" ]; then
    echo "=== 创建新策略 ==="
    POLICY_ARN=$(aws iam create-policy \
        --policy-name "$POLICY_NAME" \
        --policy-document file:///tmp/lambda-deploy-policy.json \
        --query 'Policy.Arn' --output text)
    echo "✅ 已创建策略: $POLICY_ARN"
else
    echo "=== 更新现有策略 ==="
    # Delete old versions (keep only default)
    VERSIONS=$(aws iam list-policy-versions --policy-arn "$POLICY_ARN" --query 'Versions[?IsDefaultVersion==`false`].VersionId' --output text)
    for v in $VERSIONS; do
        aws iam delete-policy-version --policy-arn "$POLICY_ARN" --version-id "$v" 2>/dev/null || true
    done

    # Create new version
    aws iam create-policy-version \
        --policy-arn "$POLICY_ARN" \
        --policy-document file:///tmp/lambda-deploy-policy.json \
        --set-as-default > /dev/null
    echo "✅ 已更新策略: $POLICY_ARN"
fi

# Attach policy to role
echo ""
echo "=== 附加策略到角色 ==="
aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn "$POLICY_ARN" 2>/dev/null || true

echo "✅ 已附加策略到角色"

echo ""
echo "=============================================="
echo "权限修复完成！"
echo "=============================================="
echo ""
echo "包含的权限:"
echo "  - Lambda: 完整权限 (创建/更新/删除函数、配置URL等)"
echo "  - DynamoDB: 完整权限 (创建/删除表、CRUD操作等)"
echo "  - IAM: 角色管理 (创建/删除角色、附加/删除策略等)"
echo "  - EC2: VPC 访问 (描述安全组/子网/VPC等)"
echo "  - API Gateway: HTTP API 管理 (创建/更新API、集成、路由等)"
echo "  - CloudFront: CDN 分发管理"
echo ""
echo "现在可以重新测试动态网站部署了。"
