#!/usr/bin/env python3
"""
Deploy Agent to Amazon Bedrock AgentCore Runtime

This script builds and deploys the Website Generator Agent to AgentCore Runtime.
Requirements:
- AWS credentials configured
- Docker (or use CodeBuild for ARM64 builds)
"""

import boto3
import json
import os
import sys
import time


# Configuration
AGENT_NAME = "ugc_website_generator"
REGION = os.environ.get("AWS_REGION", "us-east-1")
ACCOUNT_ID = boto3.client("sts").get_caller_identity()["Account"]
ECR_REPO_NAME = "ugc-agent-runtime"
IMAGE_TAG = "latest"

# AgentCore Built-in Tools Configuration
# Created via: scripts/create-agentcore-tools.sh
AGENTCORE_BROWSER_ID = os.environ.get("AGENTCORE_BROWSER_ID", "ugc_browser-pXEF8HjbYA")
AGENTCORE_CODE_INTERPRETER_ID = os.environ.get("AGENTCORE_CODE_INTERPRETER_ID", "ugc_code_interpreter-xWbd7jhzHc")


def create_ecr_repository():
    """Create ECR repository if it doesn't exist."""
    ecr = boto3.client("ecr", region_name=REGION)
    try:
        ecr.describe_repositories(repositoryNames=[ECR_REPO_NAME])
        print(f"ECR repository {ECR_REPO_NAME} already exists")
    except ecr.exceptions.RepositoryNotFoundException:
        print(f"Creating ECR repository {ECR_REPO_NAME}...")
        ecr.create_repository(
            repositoryName=ECR_REPO_NAME,
            imageScanningConfiguration={"scanOnPush": True},
        )
        print(f"Created ECR repository {ECR_REPO_NAME}")

    return f"{ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/{ECR_REPO_NAME}"


def get_or_create_agent_runtime_role():
    """Get or create IAM role for AgentCore Runtime."""
    iam = boto3.client("iam")
    role_name = "ugc-agentcore-runtime-role"

    try:
        response = iam.get_role(RoleName=role_name)
        print(f"IAM role {role_name} already exists")
        return response["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        pass

    print(f"Creating IAM role {role_name}...")

    # Trust policy for AgentCore Runtime
    trust_policy = {
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

    iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(trust_policy),
        Description="IAM role for UGC Website Generator Agent on AgentCore Runtime"
    )

    # Attach policies for Bedrock model access and other services
    policies = [
        "arn:aws:iam::aws:policy/AmazonBedrockFullAccess",
        "arn:aws:iam::aws:policy/AmazonS3FullAccess",
        "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
    ]

    for policy_arn in policies:
        iam.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)

    # Wait for role propagation
    time.sleep(10)

    response = iam.get_role(RoleName=role_name)
    return response["Role"]["Arn"]


def deploy_agent_runtime(container_uri: str, role_arn: str):
    """Deploy agent to AgentCore Runtime."""
    print(f"\nDeploying agent to AgentCore Runtime...")
    print(f"Container URI: {container_uri}")
    print(f"Role ARN: {role_arn}")

    client = boto3.client("bedrock-agentcore-control", region_name=REGION)

    # Check if agent runtime already exists
    try:
        existing = client.list_agent_runtimes()
        for runtime in existing.get("agentRuntimeSummaries", []):
            if runtime["agentRuntimeName"] == AGENT_NAME:
                print(f"Agent runtime {AGENT_NAME} already exists. Updating...")
                # Delete existing runtime first
                client.delete_agent_runtime(agentRuntimeId=runtime["agentRuntimeId"])
                print("Waiting for deletion to complete...")
                time.sleep(30)
                break
    except Exception as e:
        print(f"Warning: Could not list existing runtimes: {e}")

    # Create new agent runtime with environment variables for AgentCore tools
    # Environment variables enable Browser and Code Interpreter integration
    response = client.create_agent_runtime(
        agentRuntimeName=AGENT_NAME,
        description="AI-powered website generator with browsing and deployment capabilities",
        agentRuntimeArtifact={
            "containerConfiguration": {
                "containerUri": container_uri,
                "environment": {
                    "AWS_REGION": REGION,
                    "AGENTCORE_BROWSER_ID": AGENTCORE_BROWSER_ID,
                    "AGENTCORE_CODE_INTERPRETER_ID": AGENTCORE_CODE_INTERPRETER_ID,
                }
            }
        },
        networkConfiguration={"networkMode": "PUBLIC"},
        roleArn=role_arn,
    )

    agent_arn = response["agentRuntimeArn"]
    status = response["status"]

    print(f"\nAgent Runtime created successfully!")
    print(f"ARN: {agent_arn}")
    print(f"Status: {status}")

    # Wait for deployment to complete
    print("\nWaiting for deployment to complete...")
    while True:
        response = client.get_agent_runtime(agentRuntimeArn=agent_arn)
        status = response["status"]
        print(f"Status: {status}")

        if status == "ACTIVE":
            print("\nDeployment completed successfully!")
            break
        elif status in ["FAILED", "DELETED"]:
            print(f"\nDeployment failed with status: {status}")
            if "failureReasons" in response:
                print(f"Failure reasons: {response['failureReasons']}")
            sys.exit(1)

        time.sleep(15)

    return agent_arn


def main():
    print("=" * 60)
    print("Deploying UGC Website Generator Agent to AgentCore Runtime")
    print("=" * 60)
    print(f"Account: {ACCOUNT_ID}")
    print(f"Region: {REGION}")
    print(f"Agent Name: {AGENT_NAME}")
    print()

    # Step 1: Create ECR repository
    ecr_uri = create_ecr_repository()
    container_uri = f"{ecr_uri}:{IMAGE_TAG}"

    # Step 2: Get or create IAM role
    role_arn = get_or_create_agent_runtime_role()

    # Step 3: Build and push Docker image (ARM64)
    print("\n" + "=" * 60)
    print("IMPORTANT: Build and push the Docker image manually")
    print("=" * 60)
    print(f"""
Before continuing, build and push the ARM64 image:

1. Navigate to the agent directory:
   cd agent

2. Build ARM64 image using docker buildx:
   docker buildx build --platform linux/arm64 -t {container_uri} --push .

   OR use CodeBuild (if no local Docker):
   # Run build-agent-codebuild.sh script

3. Verify the image was pushed:
   aws ecr describe-images --repository-name {ECR_REPO_NAME} --region {REGION}
""")

    response = input("Has the image been pushed to ECR? (yes/no): ")
    if response.lower() not in ["yes", "y"]:
        print("Please push the image and run this script again.")
        sys.exit(0)

    # Step 4: Deploy to AgentCore Runtime
    agent_arn = deploy_agent_runtime(container_uri, role_arn)

    print("\n" + "=" * 60)
    print("Deployment Summary")
    print("=" * 60)
    print(f"Agent ARN: {agent_arn}")
    print(f"Container URI: {container_uri}")
    print(f"\nAgentCore Built-in Tools:")
    print(f"  Browser ID: {AGENTCORE_BROWSER_ID}")
    print(f"  Code Interpreter ID: {AGENTCORE_CODE_INTERPRETER_ID}")
    print(f"\nTo invoke the agent:")
    print(f"""
import boto3
import json

client = boto3.client('bedrock-agentcore', region_name='{REGION}')
response = client.invoke_agent_runtime(
    agentRuntimeArn='{agent_arn}',
    runtimeSessionId='your-session-id-must-be-33-chars-or-more',
    payload=json.dumps({{"prompt": "Create a landing page"}})
)
""")


if __name__ == "__main__":
    main()
