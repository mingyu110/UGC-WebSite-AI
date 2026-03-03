import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

/**
 * Configuration options for dynamic deployment Lambda functions.
 */
export interface DynamicFunctionConfig {
  /** Function name */
  functionName: string;
  /** Path to the application code */
  codePath: string;
  /** Application port (default: 3000) */
  port?: number;
  /** Memory size in MB (default: 1024) */
  memorySize?: number;
  /** Timeout in seconds (default: 30) */
  timeout?: number;
  /** Health check path for readiness (default: /) */
  readinessCheckPath?: string;
  /** Additional environment variables */
  environment?: { [key: string]: string };
}

/**
 * Stack for dynamic application deployment using Lambda + Web Adapter.
 *
 * This stack creates:
 * - S3 bucket for storing deployment packages
 * - IAM role for Lambda execution
 * - Lambda function with Web Adapter layer
 * - Function URL for HTTP access
 *
 * Use case: Next.js SSR, Express.js, Flask, FastAPI applications
 */
export class DynamicDeploymentStack extends cdk.Stack {
  public readonly deploymentBucket: s3.Bucket;
  public readonly lambdaRole: iam.Role;
  public readonly webAdapterLayer: lambda.ILayerVersion;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Lambda Web Adapter Layer ARN (region-dynamic)
    // https://github.com/awslabs/aws-lambda-web-adapter
    const webAdapterLayerArn = `arn:aws:lambda:${this.region}:753240598075:layer:LambdaAdapterLayerX86:26`;

    // Import the Lambda Web Adapter Layer
    this.webAdapterLayer = lambda.LayerVersion.fromLayerVersionArn(
      this,
      'WebAdapterLayer',
      webAdapterLayerArn
    );

    // S3 bucket for storing deployment packages
    this.deploymentBucket = new s3.Bucket(this, 'DeploymentBucket', {
      bucketName: `ugc-dynamic-deployments-${cdk.Aws.ACCOUNT_ID}-${cdk.Aws.REGION}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      lifecycleRules: [
        {
          expiration: cdk.Duration.days(30),
          enabled: true,
        },
      ],
    });

    // IAM role for Lambda functions
    this.lambdaRole = new iam.Role(this, 'LambdaExecutionRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      description: 'Execution role for UGC AI Demo Lambda functions',
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // Grant Lambda role access to deployment bucket
    this.deploymentBucket.grantRead(this.lambdaRole);

    // Example Lambda function with Web Adapter (template)
    // This serves as a reference for dynamic deployments
    // Note: Lambda Web Adapter requires a web server, not a Lambda handler
    // Per https://github.com/awslabs/aws-lambda-web-adapter
    // The asset directory contains:
    // - run.sh: Bootstrap script executed by Lambda Web Adapter
    // - server.js: Minimal HTTP server placeholder
    // Actual application code will be deployed via the agent tool
    const exampleFunction = new lambda.Function(this, 'ExampleWebApp', {
      functionName: 'ugc-dynamic-example',
      runtime: lambda.Runtime.NODEJS_20_X,
      architecture: lambda.Architecture.X86_64,
      handler: 'run.sh',
      // Use asset directory with proper run.sh and server.js
      code: lambda.Code.fromAsset('assets/dynamic-placeholder'),
      role: this.lambdaRole,
      memorySize: 1024,
      timeout: cdk.Duration.seconds(30),
      environment: {
        AWS_LAMBDA_EXEC_WRAPPER: '/opt/bootstrap',
        AWS_LWA_PORT: '3000',
        AWS_LWA_READINESS_CHECK_PATH: '/',
        NODE_ENV: 'production',
      },
      layers: [this.webAdapterLayer],
      description: 'UGC AI Demo - Example Dynamic Web Application',
    });

    // Function URL for HTTP access
    const functionUrl = exampleFunction.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE,
      cors: {
        allowedOrigins: ['*'],
        allowedMethods: [lambda.HttpMethod.ALL],
        allowedHeaders: ['*'],
        allowCredentials: false,
        maxAge: cdk.Duration.hours(1),
      },
    });

    // Outputs
    new cdk.CfnOutput(this, 'DeploymentBucketName', {
      value: this.deploymentBucket.bucketName,
      description: 'S3 bucket for deployment packages',
      exportName: 'UgcDynamicDeploymentBucket',
    });

    new cdk.CfnOutput(this, 'LambdaRoleArn', {
      value: this.lambdaRole.roleArn,
      description: 'IAM role ARN for Lambda functions',
      exportName: 'UgcDynamicLambdaRoleArn',
    });

    new cdk.CfnOutput(this, 'ExampleFunctionUrl', {
      value: functionUrl.url,
      description: 'Example Lambda Function URL',
      exportName: 'UgcDynamicExampleUrl',
    });

    new cdk.CfnOutput(this, 'WebAdapterLayerArn', {
      value: webAdapterLayerArn,
      description: 'Lambda Web Adapter Layer ARN',
      exportName: 'UgcDynamicWebAdapterLayer',
    });
  }

  /**
   * Creates a new Lambda function configured for dynamic web application deployment.
   * This method can be used by the agent to programmatically create new deployments.
   *
   * @param id - Unique identifier for the construct
   * @param config - Configuration options for the Lambda function
   * @returns Object containing the Lambda function and its Function URL
   */
  public createDynamicFunction(
    id: string,
    config: DynamicFunctionConfig
  ): { function: lambda.Function; functionUrl: lambda.FunctionUrl } {
    const port = config.port ?? 3000;
    const memorySize = config.memorySize ?? 1024;
    const timeout = config.timeout ?? 30;
    const readinessCheckPath = config.readinessCheckPath ?? '/';

    // Create the Lambda function with Web Adapter
    // Per https://github.com/awslabs/aws-lambda-web-adapter
    const fn = new lambda.Function(this, id, {
      functionName: config.functionName,
      runtime: lambda.Runtime.NODEJS_20_X,
      architecture: lambda.Architecture.X86_64,
      handler: 'run.sh',
      code: lambda.Code.fromAsset(config.codePath),
      role: this.lambdaRole,
      memorySize: memorySize,
      timeout: cdk.Duration.seconds(timeout),
      environment: {
        AWS_LAMBDA_EXEC_WRAPPER: '/opt/bootstrap',
        AWS_LWA_PORT: port.toString(),
        AWS_LWA_READINESS_CHECK_PATH: readinessCheckPath,
        NODE_ENV: 'production',
        ...config.environment,
      },
      layers: [this.webAdapterLayer],
      description: `UGC AI Demo - Dynamic deployment: ${config.functionName}`,
    });

    // Create Function URL with CORS configuration
    const functionUrl = fn.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE,
      cors: {
        allowedOrigins: ['*'],
        allowedMethods: [lambda.HttpMethod.ALL],
        allowedHeaders: ['*'],
        allowCredentials: false,
        maxAge: cdk.Duration.hours(1),
      },
    });

    // Output the Function URL
    new cdk.CfnOutput(this, `${id}Url`, {
      value: functionUrl.url,
      description: `Function URL for ${config.functionName}`,
    });

    return { function: fn, functionUrl };
  }
}
