#!/usr/bin/env python3
"""
Helper script to list all available workspaces from the recon service.
This helps you find the correct workspace name to use with the bot.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.services.recon_client import ReconClient
from src.utils.config_reader import get_config_value
from src.utils.logging import logger


def list_workspaces():
    """List all available workspaces."""
    try:
        # Initialize recon client
        recon_client = ReconClient()
        
        # Get workspaces
        url = f"{recon_client.base_url}/api/v1/workspaces"
        response = recon_client.http_client.get(url)
        
        if not response["success"]:
            print(f"❌ Error fetching workspaces: {response.get('error', 'Unknown error')}")
            return
        
        # Parse response
        response_data = response.get("data", {})
        if isinstance(response_data, list):
            workspaces = response_data
        elif isinstance(response_data, dict):
            workspaces = response_data.get("data", response_data.get("workspaces", []))
        else:
            workspaces = []
        
        if not workspaces:
            print("⚠️  No workspaces found. Make sure:")
            print("   1. The recon service is running")
            print("   2. RECON_API_KEY is set correctly")
            print("   3. The base_url in config is correct")
            return
        
        print(f"\n✅ Found {len(workspaces)} workspace(s):\n")
        print("=" * 80)
        print(f"{'Workspace Name':<40} {'Workspace ID':<20} {'Merchant ID':<20}")
        print("=" * 80)
        
        for workspace in workspaces:
            name = workspace.get("name", "N/A")
            workspace_id = workspace.get("id", "N/A")
            merchant_id = workspace.get("merchant_id", "N/A")
            print(f"{name:<40} {workspace_id:<20} {merchant_id:<20}")
        
        print("=" * 80)
        print(f"\n💡 To use with the bot, type:")
        print(f"   /recon-analyze workspace=<WORKSPACE_NAME>")
        print(f"\n   Example: /recon-analyze workspace={workspaces[0].get('name', 'WORKSPACE_NAME')}")
        
    except Exception as e:
        logger.error(f"Failed to list workspaces: {e}")
        print(f"❌ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Check if recon service is running")
        print("2. Verify RECON_API_KEY environment variable")
        print("3. Check config/dev.toml base_url setting")


if __name__ == "__main__":
    list_workspaces()

