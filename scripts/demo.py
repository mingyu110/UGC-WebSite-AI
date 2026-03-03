#!/usr/bin/env python3
"""
UGC AI Demo - Complete Demonstration Script

This script demonstrates the full workflow of the Website Generator Agent:
1. Initialize the agent with memory support
2. Generate a static website (landing page)
3. Generate a dynamic website (Next.js app)
4. Show deployment options

Usage:
    python scripts/demo.py [--static-only] [--dynamic-only] [--no-deploy]
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agent import WebsiteGeneratorAgent, AgentPhase


# Demo configurations
STATIC_DEMO = {
    "description": """
    Create a modern landing page for a SaaS product called "CloudSync".

    Requirements:
    - Hero section with headline and CTA button
    - Features section with 3 feature cards
    - Pricing section with 3 tiers (Basic, Pro, Enterprise)
    - Footer with links and newsletter signup

    Style: Modern, clean, using a blue (#3498db) color scheme
    """,
    "website_type": "static",
    "style_preferences": {
        "primary_color": "#3498db",
        "secondary_color": "#2ecc71",
        "font": "Inter",
        "style": "modern",
    },
}

DYNAMIC_DEMO = {
    "description": """
    Create a Next.js dashboard application with:

    - Login page with authentication
    - Dashboard page showing user stats
    - API routes for data fetching
    - Server-side rendering for SEO

    Include proper TypeScript types and Tailwind CSS styling.
    """,
    "website_type": "dynamic",
    "style_preferences": {
        "primary_color": "#6366f1",
        "font": "Inter",
        "style": "dashboard",
    },
}


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")


def print_step(step: int, text: str):
    """Print a step indicator."""
    print(f"\n[Step {step}] {text}")
    print("-" * 40)


def print_result(result: dict):
    """Print a formatted result."""
    print("\nResult:")
    print(json.dumps(result, indent=2, default=str))


async def demo_static_website(agent: WebsiteGeneratorAgent, deploy: bool = False):
    """Demonstrate static website generation."""
    print_header("Static Website Demo: Landing Page")

    print("Description:")
    print(STATIC_DEMO["description"])

    print_step(1, "Generating website...")

    result = await agent.generate_website(
        description=STATIC_DEMO["description"],
        website_type=STATIC_DEMO["website_type"],
        style_preferences=STATIC_DEMO["style_preferences"],
        auto_deploy=deploy,
    )

    print_step(2, "Generation complete!")
    print(f"Phase: {agent.phase}")
    print(f"Deployment Type: {result.get('deployment_type', 'N/A')}")
    print(f"Status: {result.get('status', 'N/A')}")

    if result.get("plan"):
        print_step(3, "Website Plan:")
        print(json.dumps(result["plan"], indent=2, default=str)[:500] + "...")

    if result.get("code"):
        print_step(4, "Generated Files:")
        for filename in result["code"].keys():
            print(f"  - {filename}")

    if deploy and result.get("url"):
        print_step(5, "Deployment Complete!")
        print(f"URL: {result['url']}")

    return result


async def demo_dynamic_website(agent: WebsiteGeneratorAgent, deploy: bool = False):
    """Demonstrate dynamic website generation."""
    print_header("Dynamic Website Demo: Next.js Dashboard")

    print("Description:")
    print(DYNAMIC_DEMO["description"])

    print_step(1, "Generating website...")

    result = await agent.generate_website(
        description=DYNAMIC_DEMO["description"],
        website_type=DYNAMIC_DEMO["website_type"],
        style_preferences=DYNAMIC_DEMO["style_preferences"],
        auto_deploy=deploy,
    )

    print_step(2, "Generation complete!")
    print(f"Phase: {agent.phase}")
    print(f"Deployment Type: {result.get('deployment_type', 'N/A')}")
    print(f"Status: {result.get('status', 'N/A')}")

    if result.get("plan"):
        print_step(3, "Website Plan:")
        print(json.dumps(result["plan"], indent=2, default=str)[:500] + "...")

    if result.get("code"):
        print_step(4, "Generated Files:")
        for filename in result["code"].keys():
            print(f"  - {filename}")

    if deploy and result.get("url"):
        print_step(5, "Deployment Complete!")
        print(f"URL: {result['url']}")

    return result


async def demo_conversation(agent: WebsiteGeneratorAgent):
    """Demonstrate conversation continuation."""
    print_header("Conversation Demo: Iterative Refinement")

    print_step(1, "Initial request...")
    result = await agent.generate_website(
        description="Create a simple portfolio website",
        website_type="static",
    )
    print(f"Status: {result.get('status')}")

    print_step(2, "Follow-up request: Change colors...")
    result = await agent.continue_conversation(
        "Change the primary color to purple and add a dark mode toggle"
    )
    print(f"Status: {result.get('status')}")

    print_step(3, "Follow-up request: Add section...")
    result = await agent.continue_conversation(
        "Add a testimonials section with 3 client quotes"
    )
    print(f"Status: {result.get('status')}")

    return result


async def demo_rollback(agent: WebsiteGeneratorAgent):
    """Demonstrate code rollback functionality."""
    print_header("Rollback Demo: Version Management")

    print_step(1, "Generate initial version...")
    await agent.generate_website(
        description="Create a simple landing page",
        website_type="static",
    )

    print_step(2, "Generate updated version...")
    await agent.continue_conversation("Add an animated hero section")

    print_step(3, "Check version history...")
    versions = await agent.memory.list_code_versions()
    print(f"Available versions: {len(versions)}")
    for v in versions:
        print(f"  - {v['version_id']}: {v.get('description', 'N/A')[:50]}")

    if len(versions) >= 2:
        print_step(4, "Rolling back to previous version...")
        result = await agent.rollback()
        print(f"Rollback status: {result.get('status')}")
        print(f"Restored version: {result.get('version_id')}")

    return versions


async def demo_status(agent: WebsiteGeneratorAgent):
    """Demonstrate agent status check."""
    print_header("Status Demo: Agent State")

    status = await agent.get_status()
    print("Current Agent Status:")
    print(json.dumps(status, indent=2, default=str))

    return status


async def main():
    """Main demo entry point."""
    parser = argparse.ArgumentParser(description="UGC AI Demo Script")
    parser.add_argument("--static-only", action="store_true", help="Only run static demo")
    parser.add_argument("--dynamic-only", action="store_true", help="Only run dynamic demo")
    parser.add_argument("--conversation", action="store_true", help="Run conversation demo")
    parser.add_argument("--rollback", action="store_true", help="Run rollback demo")
    parser.add_argument("--deploy", action="store_true", help="Actually deploy (requires AWS)")
    parser.add_argument("--model", default="anthropic.claude-sonnet-4-20250514-v1:0", help="Model ID")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    args = parser.parse_args()

    print_header("UGC AI Website Generator - Demo")

    print("Configuration:")
    print(f"  Model: {args.model}")
    print(f"  Region: {args.region}")
    print(f"  Deploy: {args.deploy}")

    # Initialize agent
    print_step(0, "Initializing WebsiteGeneratorAgent...")

    try:
        agent = WebsiteGeneratorAgent(
            model_id=args.model,
            region=args.region,
            user_id="demo-user",
        )
        print(f"Agent initialized with session: {agent.session_id}")
    except Exception as e:
        print(f"Warning: Agent initialization with mock mode: {e}")
        # Create with defaults for demo
        agent = WebsiteGeneratorAgent()

    # Run demos based on arguments
    if args.conversation:
        await demo_conversation(agent)
    elif args.rollback:
        await demo_rollback(agent)
    elif args.static_only:
        await demo_static_website(agent, deploy=args.deploy)
    elif args.dynamic_only:
        await demo_dynamic_website(agent, deploy=args.deploy)
    else:
        # Run full demo
        await demo_static_website(agent, deploy=args.deploy)

        # Create new agent for dynamic demo
        agent2 = WebsiteGeneratorAgent(
            model_id=args.model,
            region=args.region,
            user_id="demo-user",
        )
        await demo_dynamic_website(agent2, deploy=args.deploy)

    # Show final status
    await demo_status(agent)

    print_header("Demo Complete!")
    print("\nNext steps:")
    print("  1. Run with --deploy to actually deploy to AWS")
    print("  2. Run with --conversation to see iterative refinement")
    print("  3. Run with --rollback to see version management")
    print("  4. Check generated files in the agent's memory")


if __name__ == "__main__":
    asyncio.run(main())
