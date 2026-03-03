#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { StaticDeploymentStack } from '../lib/static-deployment-stack';
import { DynamicDeploymentStack } from '../lib/dynamic-deployment-stack';
import { BackendStack } from '../lib/backend-stack';
import { AgentCoreRuntimeStack } from '../lib/agentcore-runtime-stack';

const app = new cdk.App();

// Get environment from context or use defaults
const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT || process.env.AWS_ACCOUNT_ID,
  region: process.env.CDK_DEFAULT_REGION || process.env.AWS_REGION || 'us-east-1',
};

// Static Deployment Stack (S3 + CloudFront)
// For deploying generated static websites
new StaticDeploymentStack(app, 'UgcStaticDeploymentStack', {
  env,
  description: 'UGC AI Demo - Static Website Deployment Infrastructure (S3 + CloudFront)',
  tags: {
    Project: 'UGC-AI-Demo',
    Component: 'StaticDeployment',
  },
});

// Dynamic Deployment Stack (Lambda + Web Adapter)
// For deploying generated dynamic applications
new DynamicDeploymentStack(app, 'UgcDynamicDeploymentStack', {
  env,
  description: 'UGC AI Demo - Dynamic Application Deployment Infrastructure (Lambda + Web Adapter)',
  tags: {
    Project: 'UGC-AI-Demo',
    Component: 'DynamicDeployment',
  },
});

// Backend Stack (ECS Fargate)
// FastAPI backend service
new BackendStack(app, 'UgcBackendStack', {
  env,
  description: 'UGC AI Demo - Backend API Service (ECS Fargate)',
  tags: {
    Project: 'UGC-AI-Demo',
    Component: 'Backend',
  },
});

// AgentCore Runtime Stack
// IAM roles and supporting infrastructure for Agent in AgentCore Runtime
new AgentCoreRuntimeStack(app, 'UgcAgentCoreRuntimeStack', {
  env,
  description: 'UGC AI Demo - AgentCore Runtime Infrastructure',
  tags: {
    Project: 'UGC-AI-Demo',
    Component: 'AgentCore',
  },
});

app.synth();
