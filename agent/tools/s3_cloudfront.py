"""
S3 + CloudFront Deployment Implementation

Core implementation for deploying static websites to S3 with CloudFront CDN.

Async Task Management Implementation:
- Deployment runs in background task
- Results written to AgentCore Memory
- ctx parameter is optional (None when running in background)
- Reference: https://aws.amazon.com/blogs/machine-learning/build-long-running-mcp-servers-on-amazon-bedrock-agentcore-with-strands-agents-integration/
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class S3CloudFrontDeployer:
    """
    Handles static website deployment to S3 + CloudFront.

    This class manages:
    - S3 bucket creation and configuration
    - File uploads with proper content types
    - CloudFront distribution creation/update
    - Origin Access Control setup
    """

    # Content type mappings
    CONTENT_TYPES = {
        ".html": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
        ".ttf": "font/ttf",
        ".eot": "application/vnd.ms-fontobject",
        ".webp": "image/webp",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".pdf": "application/pdf",
        ".xml": "application/xml",
        ".txt": "text/plain",
    }

    def __init__(self, region: str = "us-east-1"):
        """
        Initialize the deployer.

        Args:
            region: AWS region for deployment
        """
        self.region = region
        self.s3_client = boto3.client("s3", region_name=region)
        self.cloudfront_client = boto3.client("cloudfront", region_name=region)
        self.sts_client = boto3.client("sts", region_name=region)

        # Get account ID for resource naming
        try:
            self.account_id = self.sts_client.get_caller_identity()["Account"]
        except Exception:
            self.account_id = "000000000000"

    async def deploy(
        self,
        project_name: str,
        files: List[Dict[str, Any]],
        index_document: str = "index.html",
        error_document: str = "error.html",
        ctx: Any = None,  # MCP Context for progress updates
    ) -> Dict[str, Any]:
        """
        Deploy static files to S3 + CloudFront with Context Messaging.
        
        Uses MCP Context to send progress updates during deployment:
        - Keeps connection alive with heartbeat messages
        - Provides real-time feedback to users
        - Prevents timeout for long-running operations (40-50 seconds)

        Args:
            project_name: Unique name for this deployment
            files: List of files to deploy
            index_document: Index document name
            error_document: Error document name
            ctx: MCP Context for sending progress updates

        Returns:
            Deployment result with URLs
        """
        # Generate unique bucket name
        bucket_name = f"ugc-static-{project_name}-{os.urandom(4).hex()}"
        
        try:
            # Step 1: Create S3 bucket (0-20%)
            if ctx:
                await ctx.report_progress(0.0, 1.0, "🚀 开始部署...")
            
            if self.region == "us-east-1":
                self.s3_client.create_bucket(Bucket=bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": self.region},
                )
            
            # Block public access
            self.s3_client.put_public_access_block(
                Bucket=bucket_name,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": True,
                    "IgnorePublicAcls": True,
                    "BlockPublicPolicy": False,
                    "RestrictPublicBuckets": False,
                },
            )
            logger.info(f"Created bucket: {bucket_name}")
            
            if ctx:
                await ctx.report_progress(0.2, 1.0, f"✅ S3 存储桶已创建: {bucket_name}")

            # Step 2: Configure bucket for static hosting (20-30%)
            self.s3_client.put_bucket_website(
                Bucket=bucket_name,
                WebsiteConfiguration={
                    "IndexDocument": {"Suffix": index_document},
                    "ErrorDocument": {"Key": error_document},
                },
            )
            logger.info(f"Configured bucket for static hosting")
            
            if ctx:
                await ctx.report_progress(0.3, 1.0, "✅ 静态网站托管已配置")

            # Step 3: Upload files (30-50%)
            if ctx:
                await ctx.report_progress(0.35, 1.0, f"📤 正在上传 {len(files)} 个文件...")
            
            import concurrent.futures
            def upload_file(file_info):
                path = file_info["path"]
                content = file_info["content"]
                encoding = file_info.get("encoding", "utf-8")
                ext = os.path.splitext(path)[1].lower()
                content_type = self.CONTENT_TYPES.get(ext, "application/octet-stream")
                
                if isinstance(content, str):
                    if encoding == "base64":
                        import base64
                        content_bytes = base64.b64decode(content)
                    else:
                        content_bytes = content.encode(encoding)
                else:
                    content_bytes = content
                
                self.s3_client.put_object(
                    Bucket=bucket_name,
                    Key=path.lstrip("/"),
                    Body=content_bytes,
                    ContentType=content_type,
                )
                return path
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                uploaded_files = list(executor.map(upload_file, files))
            
            logger.info(f"Uploaded {len(uploaded_files)} files")
            
            if ctx:
                await ctx.report_progress(0.5, 1.0, f"✅ {len(uploaded_files)} 个文件上传完成")

            # Step 4: Create CloudFront distribution (50-80%)
            if ctx:
                await ctx.report_progress(0.55, 1.0, "🌐 正在创建 CloudFront CDN 分发...")
            
            oac_response = self.cloudfront_client.create_origin_access_control(
                OriginAccessControlConfig={
                    "Name": f"OAC-{project_name}-{os.urandom(4).hex()}",
                    "Description": f"OAC for {project_name}",
                    "SigningProtocol": "sigv4",
                    "SigningBehavior": "always",
                    "OriginAccessControlOriginType": "s3",
                }
            )
            oac_id = oac_response["OriginAccessControl"]["Id"]
            
            if ctx:
                await ctx.report_progress(0.6, 1.0, "⏳ 正在配置 CloudFront 分发（这可能需要 20-30 秒）...")

            caller_ref = f"{project_name}-{os.urandom(8).hex()}"
            distribution_config = {
                "CallerReference": caller_ref,
                "Comment": f"UGC AI Demo - {project_name}",
                "Enabled": True,
                "DefaultRootObject": "index.html",
                "Origins": {
                    "Quantity": 1,
                    "Items": [{
                        "Id": f"S3-{bucket_name}",
                        "DomainName": f"{bucket_name}.s3.{self.region}.amazonaws.com",
                        "S3OriginConfig": {"OriginAccessIdentity": ""},
                        "OriginAccessControlId": oac_id,
                    }],
                },
                "DefaultCacheBehavior": {
                    "TargetOriginId": f"S3-{bucket_name}",
                    "ViewerProtocolPolicy": "redirect-to-https",
                    "AllowedMethods": {
                        "Quantity": 2,
                        "Items": ["GET", "HEAD"],
                        "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]},
                    },
                    "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",
                    "Compress": True,
                },
                "CustomErrorResponses": {
                    "Quantity": 2,
                    "Items": [
                        {
                            "ErrorCode": 403,
                            "ResponsePagePath": "/index.html",
                            "ResponseCode": "200",
                            "ErrorCachingMinTTL": 300,
                        },
                        {
                            "ErrorCode": 404,
                            "ResponsePagePath": "/index.html",
                            "ResponseCode": "200",
                            "ErrorCachingMinTTL": 300,
                        },
                    ],
                },
                "PriceClass": "PriceClass_100",
            }

            response = self.cloudfront_client.create_distribution(
                DistributionConfig=distribution_config
            )
            distribution_id = response["Distribution"]["Id"]
            distribution_domain = response["Distribution"]["DomainName"]
            logger.info(f"Created CloudFront distribution: {distribution_id}")
            
            if ctx:
                await ctx.report_progress(0.8, 1.0, f"✅ CloudFront 分发已创建: {distribution_domain}")

            # Step 5: Update bucket policy (80-100%)
            if ctx:
                await ctx.report_progress(0.85, 1.0, "🔒 正在配置访问权限...")
            
            policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Sid": "AllowCloudFrontAccess",
                    "Effect": "Allow",
                    "Principal": {"Service": "cloudfront.amazonaws.com"},
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket_name}/*",
                    "Condition": {
                        "StringEquals": {
                            "AWS:SourceArn": f"arn:aws:cloudfront::{self.account_id}:distribution/{distribution_id}"
                        }
                    },
                }],
            }
            self.s3_client.put_bucket_policy(
                Bucket=bucket_name,
                Policy=json.dumps(policy),
            )

            s3_website_url = f"http://{bucket_name}.s3-website-{self.region}.amazonaws.com"
            cloudfront_url = f"https://{distribution_domain}"
            
            if ctx:
                await ctx.report_progress(1.0, 1.0, "🎉 部署完成！")

            return {
                "status": "deployed",
                "deployment_type": "static",
                "bucket_name": bucket_name,
                "distribution_id": distribution_id,
                "distribution_domain": distribution_domain,
                "url": cloudfront_url,
                "s3_website_url": s3_website_url,
                "files_uploaded": len(uploaded_files),
                "message": f"✅ 部署成功！\n\n🌐 CloudFront CDN 地址（推荐）：\n{cloudfront_url}\n\n📍 S3 网站端点（立即可用）：\n{s3_website_url}\n\n💡 CloudFront 分发正在全球部署中（5-15 分钟后全球加速生效）。您可以立即通过 S3 地址访问网站。",
            }

        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            # Cleanup on failure
            try:
                await self._cleanup_bucket(bucket_name)
            except Exception:
                pass
            raise

    async def get_status(self, deployment_id: str) -> Dict[str, Any]:
        """Get deployment status."""
        try:
            response = self.cloudfront_client.get_distribution(Id=deployment_id)
            distribution = response["Distribution"]

            return {
                "deployment_id": deployment_id,
                "status": distribution["Status"],
                "domain_name": distribution["DomainName"],
                "enabled": distribution["DistributionConfig"]["Enabled"],
            }
        except ClientError as e:
            return {
                "deployment_id": deployment_id,
                "status": "not_found",
                "error": str(e),
            }

    async def delete(self, deployment_id: str, delete_bucket: bool = True) -> Dict[str, Any]:
        """Delete a deployment."""
        try:
            # Get distribution config
            response = self.cloudfront_client.get_distribution(Id=deployment_id)
            etag = response["ETag"]
            config = response["Distribution"]["DistributionConfig"]

            # Extract bucket name from origin
            bucket_name = None
            if config.get("Origins", {}).get("Items"):
                origin = config["Origins"]["Items"][0]
                domain = origin.get("DomainName", "")
                if ".s3." in domain:
                    bucket_name = domain.split(".s3.")[0]

            # Disable distribution first
            if config["Enabled"]:
                config["Enabled"] = False
                self.cloudfront_client.update_distribution(
                    Id=deployment_id,
                    DistributionConfig=config,
                    IfMatch=etag,
                )
                logger.info("Distribution disabled, waiting for deployment to complete")

            result = {
                "deployment_id": deployment_id,
                "status": "deletion_initiated",
                "message": "Distribution disabled. Full deletion requires waiting for deployment to complete.",
            }

            # Delete bucket if requested
            if delete_bucket and bucket_name:
                try:
                    await self._cleanup_bucket(bucket_name)
                    result["bucket_deleted"] = True
                    result["bucket_name"] = bucket_name
                except Exception as e:
                    result["bucket_deleted"] = False
                    result["bucket_error"] = str(e)

            return result

        except ClientError as e:
            return {
                "deployment_id": deployment_id,
                "status": "deletion_failed",
                "error": str(e),
            }

    async def list_deployments(self, limit: int = 20) -> Dict[str, Any]:
        """List all UGC static deployments."""
        try:
            deployments = []
            paginator = self.cloudfront_client.get_paginator("list_distributions")

            for page in paginator.paginate():
                items = page.get("DistributionList", {}).get("Items", [])
                for item in items:
                    # Filter for UGC deployments
                    comment = item.get("Comment", "")
                    if "UGC AI Demo" in comment:
                        deployments.append({
                            "deployment_id": item["Id"],
                            "domain_name": item["DomainName"],
                            "status": item["Status"],
                            "enabled": item["Enabled"],
                            "comment": comment,
                            "url": f"https://{item['DomainName']}",
                        })

                    if len(deployments) >= limit:
                        break
                if len(deployments) >= limit:
                    break

            return {
                "deployments": deployments,
                "count": len(deployments),
            }

        except ClientError as e:
            return {
                "deployments": [],
                "count": 0,
                "error": str(e),
            }

    async def _cleanup_bucket(self, bucket_name: str) -> None:
        """Clean up bucket and its contents on deployment failure."""
        try:
            # Delete all objects
            paginator = self.s3_client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket_name):
                if "Contents" in page:
                    objects = [{"Key": obj["Key"]} for obj in page["Contents"]]
                    self.s3_client.delete_objects(
                        Bucket=bucket_name,
                        Delete={"Objects": objects},
                    )

            # Delete bucket
            self.s3_client.delete_bucket(Bucket=bucket_name)

        except Exception as e:
            logger.warning(f"Failed to cleanup bucket {bucket_name}: {e}")
