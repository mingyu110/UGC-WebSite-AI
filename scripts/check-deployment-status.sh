#!/bin/bash
# Check deployment status of all components

echo "=========================================="
echo "UGC AI Demo - Deployment Status"
echo "=========================================="
echo ""

echo "1. AgentCore Runtime (Main Agent)"
echo "------------------------------------------"
cd agent
../../.venv/bin/python -c "from bedrock_agentcore_starter_toolkit.cli.cli import main; main()" status 2>&1 | grep -E "(Agent Name|Agent ARN|Endpoint|Status)" || echo "Failed to get status"
cd ..
echo ""

echo "2. MCP Server - Static Deployment"
echo "------------------------------------------"
cd mcp_servers/deploy_static_runtime
../../.venv/bin/python -c "from bedrock_agentcore_starter_toolkit.cli.cli import main; main()" status 2>&1 | grep -E "(Agent Name|Agent ARN|Endpoint|Status)" || echo "Failed to get status"
cd ../..
echo ""

echo "3. MCP Server - Dynamic Deployment"
echo "------------------------------------------"
cd mcp_servers/deploy_dynamic_runtime
../../.venv/bin/python -c "from bedrock_agentcore_starter_toolkit.cli.cli import main; main()" status 2>&1 | grep -E "(Agent Name|Agent ARN|Endpoint|Status)" || echo "Failed to get status"
cd ../..
echo ""

echo "4. MCP Gateway Targets"
echo "------------------------------------------"
cd mcp_servers/deploy_static_runtime
../../.venv/bin/python -c "from bedrock_agentcore_starter_toolkit.cli.cli import main; main()" gateway list-mcp-gateway-targets --id ugc-deploy-gateway-ygktmphkkl --region us-east-1 2>&1 | grep -E "(targetId|name|status)" || echo "Failed to get targets"
cd ../..
echo ""

echo "=========================================="
echo "Summary:"
echo "- AgentCore Runtime: ugc_website_generator-r4ApYLEVE1"
echo "- Static MCP Server: deploy_static_mcp_oauth-2cv1a5AHUZ (UPDATED with Context Messaging)"
echo "- Dynamic MCP Server: deploy_dynamic_mcp_oauth-qLuoEcD9kp"
echo "- Gateway: ugc-deploy-gateway-ygktmphkkl"
echo "=========================================="
