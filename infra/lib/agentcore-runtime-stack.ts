import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import { Construct } from 'constructs';

/**
 * Stack for deploying the Website Generator Agent to AgentCore Runtime.
 *
 * AgentCore Runtime is AWS Bedrock's managed runtime for AI agents.
 * It provides:
 * - Managed agent execution environment
 * - Built-in tools (Browser, Code Interpreter, Memory)
 * - MCP Server support
 * - IAM-based authentication
 *
 * Note: AgentCore Runtime resources are created via AWS Console or CLI
 * as CDK L2 constructs are not yet available. This stack creates
 * supporting infrastructure and outputs configuration values.
 */
export class AgentCoreRuntimeStack extends cdk.Stack {
  public readonly agentCodeBucket: s3.Bucket;
  public readonly agentRole: iam.Role;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // S3 bucket for agent code and assets
    this.agentCodeBucket = new s3.Bucket(this, 'AgentCodeBucket', {
      bucketName: `ugc-agentcore-code-${cdk.Aws.ACCOUNT_ID}-${cdk.Aws.REGION}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: true,
    });

    // IAM Role for AgentCore Runtime
    this.agentRole = new iam.Role(this, 'AgentCoreRole', {
      roleName: 'ugc-agentcore-execution-role',
      assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
      description: 'Execution role for UGC Website Generator Agent in AgentCore Runtime',
    });

    // Bedrock model invocation permissions
    this.agentRole.addToPolicy(new iam.PolicyStatement({
      sid: 'BedrockModelInvocation',
      effect: iam.Effect.ALLOW,
      actions: [
        'bedrock:InvokeModel',
        'bedrock:InvokeModelWithResponseStream',
      ],
      resources: [
        `arn:aws:bedrock:${cdk.Aws.REGION}::foundation-model/*`,
        `arn:aws:bedrock:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:inference-profile/*`,
      ],
    }));

    // AgentCore Browser Tool permissions
    this.agentRole.addToPolicy(new iam.PolicyStatement({
      sid: 'AgentCoreBrowserTool',
      effect: iam.Effect.ALLOW,
      actions: [
        'bedrock-agentcore:CreateBrowserSession',
        'bedrock-agentcore:InvokeBrowser',
        'bedrock-agentcore:TerminateBrowserSession',
      ],
      resources: ['*'],
    }));

    // AgentCore Code Interpreter permissions
    this.agentRole.addToPolicy(new iam.PolicyStatement({
      sid: 'AgentCoreCodeInterpreter',
      effect: iam.Effect.ALLOW,
      actions: [
        'bedrock-agentcore:CreateCodeInterpreterSession',
        'bedrock-agentcore:InvokeCodeInterpreter',
        'bedrock-agentcore:TerminateCodeInterpreterSession',
      ],
      resources: ['*'],
    }));

    // AgentCore Memory permissions
    this.agentRole.addToPolicy(new iam.PolicyStatement({
      sid: 'AgentCoreMemory',
      effect: iam.Effect.ALLOW,
      actions: [
        'bedrock-agentcore:CreateMemory',
        'bedrock-agentcore:GetMemory',
        'bedrock-agentcore:UpdateMemory',
        'bedrock-agentcore:DeleteMemory',
        'bedrock-agentcore:SearchMemory',
      ],
      resources: ['*'],
    }));

    // S3 permissions for agent code and deployments
    this.agentRole.addToPolicy(new iam.PolicyStatement({
      sid: 'S3Access',
      effect: iam.Effect.ALLOW,
      actions: [
        's3:GetObject',
        's3:PutObject',
        's3:DeleteObject',
        's3:ListBucket',
      ],
      resources: [
        this.agentCodeBucket.bucketArn,
        `${this.agentCodeBucket.bucketArn}/*`,
        `arn:aws:s3:::ugc-static-${cdk.Aws.ACCOUNT_ID}-${cdk.Aws.REGION}`,
        `arn:aws:s3:::ugc-static-${cdk.Aws.ACCOUNT_ID}-${cdk.Aws.REGION}/*`,
      ],
    }));

    // CloudFront permissions
    this.agentRole.addToPolicy(new iam.PolicyStatement({
      sid: 'CloudFrontAccess',
      effect: iam.Effect.ALLOW,
      actions: [
        'cloudfront:CreateInvalidation',
        'cloudfront:GetDistribution',
      ],
      resources: ['*'],
    }));

    // Lambda permissions for dynamic deployments
    this.agentRole.addToPolicy(new iam.PolicyStatement({
      sid: 'LambdaAccess',
      effect: iam.Effect.ALLOW,
      actions: [
        'lambda:CreateFunction',
        'lambda:UpdateFunctionCode',
        'lambda:UpdateFunctionConfiguration',
        'lambda:GetFunction',
        'lambda:DeleteFunction',
        'lambda:InvokeFunction',
        'lambda:AddPermission',
        'lambda:CreateFunctionUrlConfig',
      ],
      resources: [`arn:aws:lambda:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:function:ugc-*`],
    }));

    // IAM PassRole for Lambda creation
    this.agentRole.addToPolicy(new iam.PolicyStatement({
      sid: 'IAMPassRole',
      effect: iam.Effect.ALLOW,
      actions: ['iam:PassRole'],
      resources: [`arn:aws:iam::${cdk.Aws.ACCOUNT_ID}:role/ugc-*`],
    }));

    // CloudWatch Logs
    this.agentRole.addToPolicy(new iam.PolicyStatement({
      sid: 'CloudWatchLogs',
      effect: iam.Effect.ALLOW,
      actions: [
        'logs:CreateLogGroup',
        'logs:CreateLogStream',
        'logs:PutLogEvents',
      ],
      resources: [`arn:aws:logs:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:log-group:/aws/agentcore/*`],
    }));

    // Outputs
    new cdk.CfnOutput(this, 'AgentCodeBucketName', {
      value: this.agentCodeBucket.bucketName,
      description: 'S3 bucket for agent code',
      exportName: 'UgcAgentCoreCodeBucket',
    });

    new cdk.CfnOutput(this, 'AgentRoleArn', {
      value: this.agentRole.roleArn,
      description: 'IAM role ARN for AgentCore Runtime',
      exportName: 'UgcAgentCoreRoleArn',
    });

    // Output the AgentCore CLI command to create the agent
    new cdk.CfnOutput(this, 'CreateAgentCommand', {
      value: `aws bedrock-agentcore create-agent --agent-name ugc-website-generator --role-arn ${this.agentRole.roleArn} --instruction "You are an AI website generator assistant." --region ${cdk.Aws.REGION}`,
      description: 'CLI command to create the AgentCore agent',
    });
  }
}
