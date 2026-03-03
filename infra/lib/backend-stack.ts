import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

/**
 * Stack for deploying the FastAPI backend service on ECS Fargate.
 *
 * Architecture:
 * - VPC with public/private subnets
 * - ECS Cluster with Fargate
 * - Application Load Balancer
 * - FastAPI service container
 *
 * The backend calls AgentCore Runtime for AI agent operations.
 */
export class BackendStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;
  public readonly cluster: ecs.Cluster;
  public readonly service: ecs.FargateService;
  public readonly loadBalancer: elbv2.ApplicationLoadBalancer;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // VPC
    this.vpc = new ec2.Vpc(this, 'BackendVpc', {
      vpcName: 'ugc-backend-vpc',
      maxAzs: 2,
      natGateways: 1,
      subnetConfiguration: [
        {
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
          cidrMask: 24,
        },
        {
          name: 'Private',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
          cidrMask: 24,
        },
      ],
    });

    // ECS Cluster
    this.cluster = new ecs.Cluster(this, 'BackendCluster', {
      clusterName: 'ugc-backend-cluster',
      vpc: this.vpc,
      containerInsights: true,
    });

    // Import existing ECR Repository (created by CodeBuild)
    const repository = ecr.Repository.fromRepositoryName(
      this,
      'BackendRepo',
      'ugc-backend'
    );

    // Task execution role
    const executionRole = new iam.Role(this, 'TaskExecutionRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AmazonECSTaskExecutionRolePolicy'),
      ],
    });

    // Task role with permissions
    const taskRole = new iam.Role(this, 'TaskRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      description: 'Role for UGC Backend Fargate tasks',
    });

    // AgentCore Runtime invocation permission
    // Backend only needs to invoke the AgentCore Runtime
    // All AI operations (Bedrock, Browser Tool, Code Interpreter, Memory) and
    // deployment operations (S3, CloudFront, Lambda) are handled by AgentCore Runtime
    taskRole.addToPolicy(new iam.PolicyStatement({
      sid: 'AgentCoreRuntimeInvoke',
      effect: iam.Effect.ALLOW,
      actions: [
        'bedrock-agentcore:InvokeAgentRuntime',
      ],
      resources: [
        `arn:aws:bedrock-agentcore:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:runtime/*`,
      ],
    }));

    // CloudWatch Logs
    const logGroup = new logs.LogGroup(this, 'BackendLogs', {
      logGroupName: '/ecs/ugc-backend',
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Task Definition
    const taskDefinition = new ecs.FargateTaskDefinition(this, 'BackendTaskDef', {
      family: 'ugc-backend',
      memoryLimitMiB: 2048,
      cpu: 1024,
      executionRole: executionRole,
      taskRole: taskRole,
    });

    // Container
    const container = taskDefinition.addContainer('BackendContainer', {
      containerName: 'ugc-backend',
      image: ecs.ContainerImage.fromEcrRepository(repository, 'latest'),
      memoryLimitMiB: 2048,
      cpu: 1024,
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: 'ugc-backend',
        logGroup: logGroup,
      }),
      environment: {
        AWS_REGION: cdk.Aws.REGION,
        STATIC_S3_BUCKET: `ugc-static-${cdk.Aws.ACCOUNT_ID}-${cdk.Aws.REGION}`,
        STATIC_CLOUDFRONT_DOMAIN: 'd2x3r9mhi9wvmb.cloudfront.net',
        HOST: '0.0.0.0',
        PORT: '8000',
        // AgentCore Runtime configuration
        // Note: ARN includes runtime suffix from agentcore deploy
        AGENT_RUNTIME_ARN: `arn:aws:bedrock-agentcore:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:runtime/ugc_website_generator-r4ApYLEVE1`,
        AGENTCORE_QUALIFIER: 'DEFAULT',
      },
      portMappings: [
        {
          containerPort: 8000,
          protocol: ecs.Protocol.TCP,
        },
      ],
      healthCheck: {
        command: ['CMD-SHELL', 'curl -f http://localhost:8000/health || exit 1'],
        interval: cdk.Duration.seconds(30),
        timeout: cdk.Duration.seconds(5),
        retries: 3,
        startPeriod: cdk.Duration.seconds(60),
      },
    });

    // Security Group for ALB
    const albSecurityGroup = new ec2.SecurityGroup(this, 'AlbSecurityGroup', {
      vpc: this.vpc,
      description: 'Security group for ALB',
      allowAllOutbound: true,
    });
    albSecurityGroup.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(80), 'Allow HTTP');
    albSecurityGroup.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(443), 'Allow HTTPS');

    // Security Group for Fargate tasks
    const taskSecurityGroup = new ec2.SecurityGroup(this, 'TaskSecurityGroup', {
      vpc: this.vpc,
      description: 'Security group for Fargate tasks',
      allowAllOutbound: true,
    });
    taskSecurityGroup.addIngressRule(albSecurityGroup, ec2.Port.tcp(8000), 'Allow from ALB');

    // Application Load Balancer
    this.loadBalancer = new elbv2.ApplicationLoadBalancer(this, 'BackendAlb', {
      loadBalancerName: 'ugc-backend-alb',
      vpc: this.vpc,
      internetFacing: true,
      securityGroup: albSecurityGroup,
    });

    // Target Group
    const targetGroup = new elbv2.ApplicationTargetGroup(this, 'BackendTargetGroup', {
      targetGroupName: 'ugc-backend-tg',
      vpc: this.vpc,
      port: 8000,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targetType: elbv2.TargetType.IP,
      healthCheck: {
        path: '/health',
        interval: cdk.Duration.seconds(30),
        timeout: cdk.Duration.seconds(5),
        healthyThresholdCount: 2,
        unhealthyThresholdCount: 3,
      },
    });

    // Listener
    const listener = this.loadBalancer.addListener('HttpListener', {
      port: 80,
      defaultAction: elbv2.ListenerAction.forward([targetGroup]),
    });

    // Fargate Service
    this.service = new ecs.FargateService(this, 'BackendService', {
      serviceName: 'ugc-backend-service',
      cluster: this.cluster,
      taskDefinition: taskDefinition,
      desiredCount: 1,
      assignPublicIp: false,
      securityGroups: [taskSecurityGroup],
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      },
    });

    // Attach to target group
    this.service.attachToApplicationTargetGroup(targetGroup);

    // Auto Scaling
    const scaling = this.service.autoScaleTaskCount({
      minCapacity: 1,
      maxCapacity: 4,
    });

    scaling.scaleOnCpuUtilization('CpuScaling', {
      targetUtilizationPercent: 70,
      scaleInCooldown: cdk.Duration.seconds(60),
      scaleOutCooldown: cdk.Duration.seconds(60),
    });

    // Outputs
    new cdk.CfnOutput(this, 'BackendUrl', {
      value: `http://${this.loadBalancer.loadBalancerDnsName}`,
      description: 'Backend API URL',
      exportName: 'UgcBackendUrl',
    });

    new cdk.CfnOutput(this, 'EcrRepositoryUri', {
      value: repository.repositoryUri,
      description: 'ECR Repository URI for backend image',
      exportName: 'UgcBackendEcrUri',
    });

    new cdk.CfnOutput(this, 'ClusterName', {
      value: this.cluster.clusterName,
      description: 'ECS Cluster Name',
      exportName: 'UgcBackendClusterName',
    });

    new cdk.CfnOutput(this, 'ServiceName', {
      value: this.service.serviceName,
      description: 'ECS Service Name',
      exportName: 'UgcBackendServiceName',
    });
  }
}
