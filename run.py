#!/usr/bin/env python3
"""
Run script for recon analysis bot.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.bot.slack_bot import create_app

if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", 3000))
    print(f"Starting recon analysis bot on port {port}")
    app.run(host="0.0.0.0", port=port, debug=True)

