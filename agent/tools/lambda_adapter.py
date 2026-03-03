"""
Lambda + Web Adapter Deployment Implementation

Core implementation for deploying dynamic web applications to AWS Lambda
with the Lambda Web Adapter extension.

Supports database connections:
- DynamoDB (no VPC required)
- RDS/Aurora (requires VPC)
- ElastiCache Redis (requires VPC)
"""

import base64
import io
import json
import logging
import os
import time
import zipfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


# ============================================================================
# Database Configuration
# ============================================================================

@dataclass
class DatabaseConfig:
    """Database configuration for Lambda deployment.

    Supports multiple database types:
    - DynamoDB: Serverless NoSQL, no VPC required
    - RDS/Aurora: Relational databases, requires VPC
    - ElastiCache: Redis cache, requires VPC
    """

    # Database type: "dynamodb", "rds", "aurora", "elasticache"
    db_type: str = ""

    # DynamoDB specific
    dynamodb_table_name: Optional[str] = None
    dynamodb_create_table: bool = False
    dynamodb_partition_key: str = "id"
    dynamodb_sort_key: Optional[str] = None

    # RDS/Aurora specific
    rds_endpoint: Optional[str] = None
    rds_port: int = 5432
    rds_database: Optional[str] = None
    rds_secret_arn: Optional[str] = None  # Secrets Manager ARN

    # ElastiCache specific
    redis_endpoint: Optional[str] = None
    redis_port: int = 6379

    # VPC configuration (for RDS/Aurora/ElastiCache)
    vpc_id: Optional[str] = None
    subnet_ids: List[str] = field(default_factory=list)
    security_group_ids: List[str] = field(default_factory=list)

    @property
    def requires_vpc(self) -> bool:
        """Check if database type requires VPC access."""
        return self.db_type in ("rds", "aurora", "elasticache")

    def to_env_vars(self) -> Dict[str, str]:
        """Convert database config to environment variables."""
        env = {}

        if self.db_type == "dynamodb":
            if self.dynamodb_table_name:
                env["DYNAMODB_TABLE_NAME"] = self.dynamodb_table_name

        elif self.db_type in ("rds", "aurora"):
            if self.rds_endpoint:
                env["DB_HOST"] = self.rds_endpoint
                env["DB_PORT"] = str(self.rds_port)
            if self.rds_database:
                env["DB_NAME"] = self.rds_database
            if self.rds_secret_arn:
                env["DB_SECRET_ARN"] = self.rds_secret_arn

        elif self.db_type == "elasticache":
            if self.redis_endpoint:
                env["REDIS_HOST"] = self.redis_endpoint
                env["REDIS_PORT"] = str(self.redis_port)

        return env


# Default VPC configuration for ugc-backend-vpc
DEFAULT_VPC_CONFIG = {
    "vpc_id": "vpc-07b5c24a0f91df4dd",
    "private_subnet_ids": [
        "subnet-0329b67cf826b518e",  # us-east-1a private
        "subnet-072f14c05a2503799",  # us-east-1b private
    ],
    "lambda_security_group_id": "sg-07ebd70714a5f711b",  # ugc-lambda-db-sg
}

# Pre-configured database resources for AI auto-selection
DEFAULT_DATABASE_CONFIG = {
    # Aurora PostgreSQL Serverless v2
    "aurora": {
        "endpoint": "ugc-aurora-cluster.cluster-ced80ewm044h.us-east-1.rds.amazonaws.com",
        "port": 5432,
        "database": "ugcdb",
        "secret_arn": "arn:aws:secretsmanager:us-east-1:947472889616:secret:ugc-aurora-credentials-G6dZkn",
    },
    # ElastiCache Redis Serverless
    "elasticache": {
        "endpoint": "ugc-redis-ifbg4g.serverless.use1.cache.amazonaws.com",
        "port": 6379,
    },
}


class LambdaWebAdapterDeployer:
    """
    Handles dynamic application deployment to Lambda + Web Adapter.

    This class manages:
    - Application packaging
    - Lambda function creation with Web Adapter layer
    - IAM role creation
    - Function URL configuration
    """

    # Lambda Web Adapter Layer ARNs by region (x86_64)
    WEB_ADAPTER_LAYERS = {
        "us-east-1": "arn:aws:lambda:us-east-1:753240598075:layer:LambdaAdapterLayerX86:26",
        "us-east-2": "arn:aws:lambda:us-east-2:753240598075:layer:LambdaAdapterLayerX86:26",
        "us-west-2": "arn:aws:lambda:us-west-2:753240598075:layer:LambdaAdapterLayerX86:26",
        "eu-west-1": "arn:aws:lambda:eu-west-1:753240598075:layer:LambdaAdapterLayerX86:26",
        "eu-central-1": "arn:aws:lambda:eu-central-1:753240598075:layer:LambdaAdapterLayerX86:26",
        "ap-northeast-1": "arn:aws:lambda:ap-northeast-1:753240598075:layer:LambdaAdapterLayerX86:26",
        "ap-southeast-1": "arn:aws:lambda:ap-southeast-1:753240598075:layer:LambdaAdapterLayerX86:26",
    }

    # Node.js Dependencies Layer ARNs by region
    # Contains: express, cors, body-parser, uuid, @aws-sdk/client-dynamodb, @aws-sdk/lib-dynamodb
    NODEJS_DEPS_LAYERS = {
        "us-east-1": "arn:aws:lambda:us-east-1:947472889616:layer:ugc-nodejs-dependencies:1",
    }

    # Default entry points by runtime
    DEFAULT_ENTRY_POINTS = {
        "nodejs18.x": "node server.js",
        "nodejs20.x": "node server.js",
        "python3.11": "python app.py",
        "python3.12": "python app.py",
    }

    def __init__(self, region: str = "us-east-1"):
        """
        Initialize the deployer.

        Args:
            region: AWS region for deployment
        """
        self.region = region
        self.lambda_client = boto3.client("lambda", region_name=region)
        self.iam_client = boto3.client("iam", region_name=region)
        self.sts_client = boto3.client("sts", region_name=region)
        self.dynamodb_client = boto3.client("dynamodb", region_name=region)
        self.ec2_client = boto3.client("ec2", region_name=region)
        self.secretsmanager_client = boto3.client("secretsmanager", region_name=region)
        self.apigateway_client = boto3.client("apigatewayv2", region_name=region)

        try:
            self.account_id = self.sts_client.get_caller_identity()["Account"]
        except Exception:
            self.account_id = "000000000000"

    async def deploy(
        self,
        project_name: str,
        files: List[Dict[str, Any]],
        runtime: str = "nodejs18.x",
        port: int = 3000,
        memory_size: int = 1024,
        timeout: int = 30,
        environment_variables: Optional[Dict[str, str]] = None,
        entry_point: Optional[str] = None,
        database_config: Optional[DatabaseConfig] = None,
    ) -> Dict[str, Any]:
        """
        Deploy dynamic application to Lambda + Web Adapter.

        Args:
            project_name: Unique name for this deployment
            files: List of files to deploy
            runtime: Lambda runtime
            port: Port the application listens on
            memory_size: Lambda memory in MB
            timeout: Lambda timeout in seconds
            environment_variables: Additional environment variables
            entry_point: Custom entry point command
            database_config: Database configuration for DynamoDB/RDS/Aurora/ElastiCache

        Returns:
            Deployment result including URL
        """
        # Generate unique function name
        function_name = f"ugc-dynamic-{project_name}-{os.urandom(4).hex()}"
        role_name = f"{function_name}-role"
        security_group_id = None
        dynamodb_table_created = False

        try:
            # 1. Setup database resources if configured
            db_resources = {}
            if database_config and database_config.db_type:
                db_resources = await self._setup_database_resources(
                    function_name=function_name,
                    database_config=database_config,
                )
                logger.info(f"Database resources setup: {db_resources}")
                security_group_id = db_resources.get("security_group_id")
                dynamodb_table_created = db_resources.get("dynamodb_table_created", False)

            # 2. Create IAM role with database permissions
            role_arn = await self._create_role(
                role_name=role_name,
                database_config=database_config,
            )
            logger.info(f"Created IAM role: {role_name}")

            # Wait for role to propagate
            time.sleep(10)

            # 3. Package application
            zip_bytes = await self._package_application(
                files=files,
                runtime=runtime,
                entry_point=entry_point or self.DEFAULT_ENTRY_POINTS.get(runtime, ""),
            )
            logger.info(f"Packaged application: {len(zip_bytes)} bytes")

            # 4. Get layer ARNs
            layers = []
            # Web Adapter layer
            layer_arn = self.WEB_ADAPTER_LAYERS.get(
                self.region,
                self.WEB_ADAPTER_LAYERS["us-east-1"]
            )
            layers.append(layer_arn)

            # Node.js dependencies layer (for Node.js runtimes)
            if runtime.startswith("nodejs"):
                nodejs_layer = self.NODEJS_DEPS_LAYERS.get(self.region)
                if nodejs_layer:
                    layers.append(nodejs_layer)
                    logger.info(f"Added Node.js dependencies layer: {nodejs_layer}")

            # 5. Prepare environment variables
            env_vars = {
                "AWS_LAMBDA_EXEC_WRAPPER": "/opt/bootstrap",
                "AWS_LWA_PORT": str(port),
                "AWS_LWA_READINESS_CHECK_PATH": "/",
            }
            # Add database environment variables
            if database_config:
                env_vars.update(database_config.to_env_vars())
            # Add custom environment variables
            if environment_variables:
                env_vars.update(environment_variables)

            # 6. Prepare Lambda creation params
            create_params = {
                "FunctionName": function_name,
                "Runtime": runtime,
                "Role": role_arn,
                "Handler": "run.sh",
                "Code": {"ZipFile": zip_bytes},
                "Layers": layers,
                "MemorySize": memory_size,
                "Timeout": timeout,
                "Environment": {"Variables": env_vars},
                "Description": f"UGC AI Demo - {project_name}",
            }

            # 7. Add VPC configuration if database requires it
            if database_config and database_config.requires_vpc:
                vpc_config = await self._get_vpc_config(database_config, security_group_id)
                create_params["VpcConfig"] = vpc_config
                logger.info(f"VPC config applied: {vpc_config}")

            # 8. Create Lambda function
            lambda_response = self.lambda_client.create_function(**create_params)
            logger.info(f"Created Lambda function: {function_name}")

            function_arn = lambda_response["FunctionArn"]

            # 9. Wait for function to be active
            waiter = self.lambda_client.get_waiter("function_active")
            waiter.wait(FunctionName=function_name)
            logger.info("Lambda function is active")

            # 10. Create API Gateway HTTP API for Lambda access
            api_url = await self._create_api_gateway(
                function_name=function_name,
                function_arn=function_arn,
            )
            logger.info(f"Created API Gateway: {api_url}")

            result = {
                "status": "deployed",
                "deployment_type": "dynamic",
                "function_name": function_name,
                "function_arn": function_arn,
                "role_arn": role_arn,
                "url": api_url,  # API Gateway URL for public access
                "runtime": runtime,
                "memory_size": memory_size,
                "timeout": timeout,
            }

            # Add database info to result
            if database_config and database_config.db_type:
                result["database"] = {
                    "type": database_config.db_type,
                    **db_resources,
                }

            return result

        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            # Cleanup on failure
            try:
                await self._cleanup(
                    function_name=function_name,
                    role_name=role_name,
                    security_group_id=security_group_id,
                    dynamodb_table_name=database_config.dynamodb_table_name if database_config and dynamodb_table_created else None,
                )
            except Exception:
                pass
            raise

    async def _setup_database_resources(
        self,
        function_name: str,
        database_config: DatabaseConfig,
    ) -> Dict[str, Any]:
        """Set up database resources based on configuration."""
        result = {}

        # DynamoDB: Create table if requested
        if database_config.db_type == "dynamodb" and database_config.dynamodb_create_table:
            table_name = database_config.dynamodb_table_name or f"{function_name}-table"
            database_config.dynamodb_table_name = table_name

            try:
                key_schema = [{"AttributeName": database_config.dynamodb_partition_key, "KeyType": "HASH"}]
                attribute_defs = [{"AttributeName": database_config.dynamodb_partition_key, "AttributeType": "S"}]

                if database_config.dynamodb_sort_key:
                    key_schema.append({"AttributeName": database_config.dynamodb_sort_key, "KeyType": "RANGE"})
                    attribute_defs.append({"AttributeName": database_config.dynamodb_sort_key, "AttributeType": "S"})

                self.dynamodb_client.create_table(
                    TableName=table_name,
                    KeySchema=key_schema,
                    AttributeDefinitions=attribute_defs,
                    BillingMode="PAY_PER_REQUEST",
                    Tags=[{"Key": "Project", "Value": "UGC-AI-Demo"}],
                )

                # Wait for table to be active
                waiter = self.dynamodb_client.get_waiter("table_exists")
                waiter.wait(TableName=table_name)

                result["dynamodb_table_name"] = table_name
                result["dynamodb_table_created"] = True
                logger.info(f"Created DynamoDB table: {table_name}")

            except self.dynamodb_client.exceptions.ResourceInUseException:
                result["dynamodb_table_name"] = table_name
                result["dynamodb_table_created"] = False
                logger.info(f"DynamoDB table already exists: {table_name}")

        # VPC databases: Use pre-configured security group or create new one
        if database_config.requires_vpc:
            # Check if pre-configured security groups are provided
            if database_config.security_group_ids:
                result["security_group_id"] = database_config.security_group_ids[0]
                logger.info(f"Using pre-configured security group: {database_config.security_group_ids[0]}")
            else:
                # Create a new security group for this Lambda function
                vpc_id = database_config.vpc_id or DEFAULT_VPC_CONFIG["vpc_id"]
                sg_name = f"{function_name}-sg"

                try:
                    sg_response = self.ec2_client.create_security_group(
                        GroupName=sg_name,
                        Description=f"Security group for Lambda function {function_name}",
                        VpcId=vpc_id,
                        TagSpecifications=[{
                            "ResourceType": "security-group",
                            "Tags": [
                                {"Key": "Name", "Value": sg_name},
                                {"Key": "Project", "Value": "UGC-AI-Demo"},
                            ],
                        }],
                    )
                    security_group_id = sg_response["GroupId"]

                    # Allow outbound traffic (Lambda needs this for VPC)
                    self.ec2_client.authorize_security_group_egress(
                        GroupId=security_group_id,
                        IpPermissions=[{
                            "IpProtocol": "-1",
                            "FromPort": -1,
                            "ToPort": -1,
                            "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                        }],
                    )

                    result["security_group_id"] = security_group_id
                    result["security_group_name"] = sg_name
                    logger.info(f"Created security group: {sg_name} ({security_group_id})")

                except ClientError as e:
                    if "InvalidGroup.Duplicate" in str(e):
                        # Get existing security group
                        sgs = self.ec2_client.describe_security_groups(
                            Filters=[
                                {"Name": "group-name", "Values": [sg_name]},
                                {"Name": "vpc-id", "Values": [vpc_id]},
                            ]
                        )
                        if sgs["SecurityGroups"]:
                            result["security_group_id"] = sgs["SecurityGroups"][0]["GroupId"]
                            logger.info(f"Using existing security group: {sg_name}")
                    else:
                        raise

        return result

    async def _get_vpc_config(
        self,
        database_config: DatabaseConfig,
        security_group_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get VPC configuration for Lambda."""
        # Use provided subnet IDs or default private subnets
        subnet_ids = database_config.subnet_ids or DEFAULT_VPC_CONFIG["private_subnet_ids"]

        # Use provided security group IDs or the one we created
        sg_ids = database_config.security_group_ids.copy() if database_config.security_group_ids else []
        if security_group_id and security_group_id not in sg_ids:
            sg_ids.append(security_group_id)

        return {
            "SubnetIds": subnet_ids,
            "SecurityGroupIds": sg_ids,
        }

    async def _create_role(
        self,
        role_name: str,
        database_config: Optional[DatabaseConfig] = None,
    ) -> str:
        """Create IAM role for Lambda execution with database permissions."""
        assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }

        try:
            response = self.iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(assume_role_policy),
                Description="UGC AI Demo - Lambda execution role",
            )
            role_arn = response["Role"]["Arn"]

            # Attach basic execution policy
            self.iam_client.attach_role_policy(
                RoleName=role_name,
                PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            )

            # Add VPC execution policy if needed
            if database_config and database_config.requires_vpc:
                self.iam_client.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole",
                )
                logger.info(f"Attached VPC execution policy to {role_name}")

            # Add database-specific permissions
            if database_config and database_config.db_type:
                db_policy = self._create_database_policy(database_config)
                if db_policy:
                    self.iam_client.put_role_policy(
                        RoleName=role_name,
                        PolicyName="DatabaseAccessPolicy",
                        PolicyDocument=json.dumps(db_policy),
                    )
                    logger.info(f"Added database policy to {role_name}")

            return role_arn

        except self.iam_client.exceptions.EntityAlreadyExistsException:
            response = self.iam_client.get_role(RoleName=role_name)
            return response["Role"]["Arn"]

    def _create_database_policy(self, database_config: DatabaseConfig) -> Optional[Dict[str, Any]]:
        """Create IAM policy for database access."""
        statements = []

        if database_config.db_type == "dynamodb":
            # DynamoDB full access to the table
            table_arn = f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{database_config.dynamodb_table_name or '*'}"
            statements.append({
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                    "dynamodb:BatchGetItem",
                    "dynamodb:BatchWriteItem",
                ],
                "Resource": [table_arn, f"{table_arn}/index/*"],
            })

        elif database_config.db_type in ("rds", "aurora"):
            # RDS/Aurora: Secrets Manager access for credentials
            if database_config.rds_secret_arn:
                statements.append({
                    "Effect": "Allow",
                    "Action": [
                        "secretsmanager:GetSecretValue",
                    ],
                    "Resource": database_config.rds_secret_arn,
                })

            # RDS IAM authentication (optional)
            statements.append({
                "Effect": "Allow",
                "Action": [
                    "rds-db:connect",
                ],
                "Resource": f"arn:aws:rds-db:{self.region}:{self.account_id}:dbuser:*/*",
            })

        elif database_config.db_type == "elasticache":
            # ElastiCache doesn't need special IAM permissions
            # Connection is via VPC networking
            pass

        if statements:
            return {
                "Version": "2012-10-17",
                "Statement": statements,
            }
        return None

    async def _create_api_gateway(
        self,
        function_name: str,
        function_arn: str,
    ) -> str:
        """
        Create API Gateway HTTP API to access Lambda function.

        This approach:
        1. Creates an HTTP API (v2) - simpler and cheaper than REST API
        2. Creates Lambda integration with proxy payload format
        3. Creates default route to handle all requests
        4. Adds Lambda permission for API Gateway invocation
        5. Returns the API Gateway invoke URL
        """
        api_name = f"ugc-api-{function_name}"

        # 1. Create HTTP API
        try:
            api_response = self.apigateway_client.create_api(
                Name=api_name,
                ProtocolType="HTTP",
                Description=f"API Gateway for {function_name}",
                CorsConfiguration={
                    "AllowOrigins": ["*"],
                    "AllowMethods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
                    "AllowHeaders": ["*"],
                    "MaxAge": 86400,
                },
            )
            api_id = api_response["ApiId"]
            logger.info(f"Created HTTP API: {api_id}")
        except ClientError as e:
            # If API already exists, find it
            if "ConflictException" in str(e):
                apis = self.apigateway_client.get_apis()
                for api in apis.get("Items", []):
                    if api["Name"] == api_name:
                        api_id = api["ApiId"]
                        break
                else:
                    raise
            else:
                raise

        # 2. Create Lambda integration
        try:
            integration_response = self.apigateway_client.create_integration(
                ApiId=api_id,
                IntegrationType="AWS_PROXY",
                IntegrationUri=function_arn,
                PayloadFormatVersion="2.0",
                TimeoutInMillis=30000,
            )
            integration_id = integration_response["IntegrationId"]
            logger.info(f"Created Lambda integration: {integration_id}")
        except ClientError as e:
            if "ConflictException" in str(e):
                # Get existing integration
                integrations = self.apigateway_client.get_integrations(ApiId=api_id)
                if integrations.get("Items"):
                    integration_id = integrations["Items"][0]["IntegrationId"]
                else:
                    raise
            else:
                raise

        # 3. Create default route (catch-all)
        try:
            self.apigateway_client.create_route(
                ApiId=api_id,
                RouteKey="$default",
                Target=f"integrations/{integration_id}",
            )
            logger.info("Created default route")
        except ClientError as e:
            if "ConflictException" not in str(e):
                raise

        # 4. Create or get default stage with auto-deploy
        try:
            self.apigateway_client.create_stage(
                ApiId=api_id,
                StageName="$default",
                AutoDeploy=True,
            )
            logger.info("Created default stage with auto-deploy")
        except ClientError as e:
            if "ConflictException" not in str(e):
                raise

        # 5. Add Lambda permission for API Gateway
        try:
            self.lambda_client.add_permission(
                FunctionName=function_name,
                StatementId="AllowAPIGatewayInvoke",
                Action="lambda:InvokeFunction",
                Principal="apigateway.amazonaws.com",
                SourceArn=f"arn:aws:execute-api:{self.region}:{self.account_id}:{api_id}/*",
            )
            logger.info("Added Lambda permission for API Gateway")
        except ClientError as e:
            if "ResourceConflictException" not in str(e):
                raise

        # 6. Get the API endpoint
        api_info = self.apigateway_client.get_api(ApiId=api_id)
        api_endpoint = api_info.get("ApiEndpoint", f"https://{api_id}.execute-api.{self.region}.amazonaws.com")
        logger.info(f"API Gateway endpoint: {api_endpoint}")

        return api_endpoint

    async def _package_application(
        self,
        files: List[Dict[str, Any]],
        runtime: str,
        entry_point: str,
    ) -> bytes:
        """Package the application into a zip file with dependencies installed."""
        import tempfile
        import subprocess
        import shutil

        # Create temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write all files to temp directory
            for file_info in files:
                path = file_info["path"].lstrip("/")
                content = file_info["content"]
                encoding = file_info.get("encoding", "utf-8")

                file_path = os.path.join(temp_dir, path)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                if isinstance(content, str):
                    if encoding == "base64":
                        content_bytes = base64.b64decode(content)
                        with open(file_path, "wb") as f:
                            f.write(content_bytes)
                    else:
                        with open(file_path, "w", encoding=encoding) as f:
                            f.write(content)
                else:
                    with open(file_path, "wb") as f:
                        f.write(content)

            # Create run.sh bootstrap script
            run_sh = self._create_bootstrap_script(runtime, entry_point)
            with open(os.path.join(temp_dir, "run.sh"), "w") as f:
                f.write(run_sh)

            # Install npm dependencies if package.json exists
            package_json = os.path.join(temp_dir, "package.json")
            if os.path.exists(package_json) and runtime.startswith("nodejs"):
                logger.info("Installing npm dependencies...")
                try:
                    result = subprocess.run(
                        ["npm", "install", "--production", "--no-optional"],
                        cwd=temp_dir,
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    if result.returncode == 0:
                        logger.info("npm dependencies installed successfully")
                    else:
                        logger.warning(f"npm install warning: {result.stderr}")
                except subprocess.TimeoutExpired:
                    logger.warning("npm install timed out, continuing without dependencies")
                except FileNotFoundError:
                    logger.warning("npm not found, skipping dependency installation")

            # Install pip dependencies if requirements.txt exists
            requirements_txt = os.path.join(temp_dir, "requirements.txt")
            if os.path.exists(requirements_txt) and runtime.startswith("python"):
                logger.info("Installing pip dependencies...")
                try:
                    result = subprocess.run(
                        ["pip", "install", "-r", "requirements.txt", "-t", temp_dir],
                        cwd=temp_dir,
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    if result.returncode == 0:
                        logger.info("pip dependencies installed successfully")
                    else:
                        logger.warning(f"pip install warning: {result.stderr}")
                except subprocess.TimeoutExpired:
                    logger.warning("pip install timed out, continuing without dependencies")
                except FileNotFoundError:
                    logger.warning("pip not found, skipping dependency installation")

            # Create zip from temp directory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, filenames in os.walk(temp_dir):
                    for filename in filenames:
                        file_path = os.path.join(root, filename)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zipf.write(file_path, arcname)

            return zip_buffer.getvalue()

    def _create_bootstrap_script(self, runtime: str, entry_point: str) -> str:
        """
        Create the run.sh bootstrap script for Lambda Web Adapter.

        Per official docs: https://github.com/awslabs/aws-lambda-web-adapter
        The script should be simple - just execute the web server.
        """
        # Use provided entry point or determine from runtime
        if entry_point:
            cmd = entry_point
        elif runtime.startswith("nodejs"):
            cmd = "node server.js"
        elif runtime.startswith("python"):
            cmd = "python app.py"
        else:
            cmd = "node server.js"

        # Simple script per official examples
        script = f"""#!/bin/bash
exec {cmd}
"""
        return script

    async def get_status(self, function_name: str) -> Dict[str, Any]:
        """Get function status."""
        try:
            response = self.lambda_client.get_function(FunctionName=function_name)
            config = response["Configuration"]

            # Get Function URL if exists
            try:
                url_response = self.lambda_client.get_function_url_config(
                    FunctionName=function_name
                )
                function_url = url_response["FunctionUrl"]
            except ClientError:
                function_url = None

            return {
                "function_name": function_name,
                "status": config["State"],
                "runtime": config["Runtime"],
                "memory_size": config["MemorySize"],
                "timeout": config["Timeout"],
                "last_modified": config["LastModified"],
                "url": function_url,
            }

        except ClientError as e:
            return {
                "function_name": function_name,
                "status": "not_found",
                "error": str(e),
            }

    async def update(
        self,
        function_name: str,
        files: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Update function code."""
        try:
            # Get current function config
            current = await self.get_status(function_name)
            if current["status"] == "not_found":
                return {"status": "failed", "error": "Function not found"}

            runtime = current.get("runtime", "nodejs18.x")

            # Package new code
            zip_bytes = await self._package_application(
                files=files,
                runtime=runtime,
                entry_point=self.DEFAULT_ENTRY_POINTS.get(runtime, ""),
            )

            # Update function code
            self.lambda_client.update_function_code(
                FunctionName=function_name,
                ZipFile=zip_bytes,
            )

            # Wait for update to complete
            waiter = self.lambda_client.get_waiter("function_updated")
            waiter.wait(FunctionName=function_name)

            return {
                "status": "updated",
                "function_name": function_name,
                "url": current.get("url"),
            }

        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
            }

    async def delete(self, function_name: str) -> Dict[str, Any]:
        """Delete a Lambda function and its role."""
        try:
            # Get role name
            try:
                response = self.lambda_client.get_function(FunctionName=function_name)
                role_arn = response["Configuration"]["Role"]
                role_name = role_arn.split("/")[-1]
            except Exception:
                role_name = None

            # Delete function
            self.lambda_client.delete_function(FunctionName=function_name)

            # Delete role
            if role_name:
                try:
                    # Detach policies first
                    self.iam_client.detach_role_policy(
                        RoleName=role_name,
                        PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                    )
                    self.iam_client.delete_role(RoleName=role_name)
                except Exception:
                    pass

            return {
                "status": "deleted",
                "function_name": function_name,
            }

        except ClientError as e:
            return {
                "status": "failed",
                "error": str(e),
            }

    async def _cleanup(
        self,
        function_name: str,
        role_name: str,
        security_group_id: Optional[str] = None,
        dynamodb_table_name: Optional[str] = None,
    ) -> None:
        """Clean up resources on deployment failure."""
        # Delete Lambda function
        try:
            self.lambda_client.delete_function(FunctionName=function_name)
        except Exception:
            pass

        # Delete IAM role and policies
        try:
            # Detach managed policies
            self.iam_client.detach_role_policy(
                RoleName=role_name,
                PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            )
        except Exception:
            pass

        try:
            self.iam_client.detach_role_policy(
                RoleName=role_name,
                PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole",
            )
        except Exception:
            pass

        try:
            # Delete inline policy
            self.iam_client.delete_role_policy(
                RoleName=role_name,
                PolicyName="DatabaseAccessPolicy",
            )
        except Exception:
            pass

        try:
            self.iam_client.delete_role(RoleName=role_name)
        except Exception:
            pass

        # Delete security group (wait a bit for Lambda ENI to be deleted)
        if security_group_id:
            try:
                time.sleep(30)  # Wait for Lambda ENIs to be deleted
                self.ec2_client.delete_security_group(GroupId=security_group_id)
                logger.info(f"Deleted security group: {security_group_id}")
            except Exception as e:
                logger.warning(f"Failed to delete security group {security_group_id}: {e}")

        # Delete DynamoDB table if it was created
        if dynamodb_table_name:
            try:
                self.dynamodb_client.delete_table(TableName=dynamodb_table_name)
                logger.info(f"Deleted DynamoDB table: {dynamodb_table_name}")
            except Exception as e:
                logger.warning(f"Failed to delete DynamoDB table {dynamodb_table_name}: {e}")

    async def list_functions(self, limit: int = 20) -> Dict[str, Any]:
        """List all UGC dynamic deployments."""
        try:
            functions = []
            paginator = self.lambda_client.get_paginator("list_functions")

            for page in paginator.paginate():
                for func in page.get("Functions", []):
                    # Filter for UGC deployments
                    name = func.get("FunctionName", "")
                    description = func.get("Description", "")

                    if name.startswith("ugc-dynamic-") or "UGC AI Demo" in description:
                        # Get Function URL if exists
                        try:
                            url_response = self.lambda_client.get_function_url_config(
                                FunctionName=name
                            )
                            function_url = url_response["FunctionUrl"]
                        except ClientError:
                            function_url = None

                        functions.append({
                            "function_name": name,
                            "runtime": func.get("Runtime"),
                            "memory_size": func.get("MemorySize"),
                            "timeout": func.get("Timeout"),
                            "last_modified": func.get("LastModified"),
                            "state": func.get("State", "Unknown"),
                            "url": function_url,
                            "description": description,
                        })

                    if len(functions) >= limit:
                        break
                if len(functions) >= limit:
                    break

            return {
                "functions": functions,
                "count": len(functions),
            }

        except ClientError as e:
            return {
                "functions": [],
                "count": 0,
                "error": str(e),
            }
