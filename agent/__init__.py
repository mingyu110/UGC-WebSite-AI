"""
UGC AI Demo - Agent Module

This module contains the agent implementation for website generation,
designed to run on AWS Bedrock AgentCore Runtime.

The main components are:
- agentcore_handler: Entry point for AgentCore Runtime
- agentcore_client: Client for invoking AgentCore Runtime from backend
- server: FastAPI backend service
- model_router: Intelligent model routing for cost optimization
- tools: Website generation and deployment tools
"""

__version__ = "0.1.0"
