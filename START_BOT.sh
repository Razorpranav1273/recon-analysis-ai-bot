#!/bin/bash
# Start script for Socket Mode bot with tokens
#
# IMPORTANT: Set your Slack tokens as environment variables before running this script:
#   export SLACK_BOT_TOKEN="your-bot-token"
#   export SLACK_APP_TOKEN="your-app-token"
#   export APP_ENV=dev
#
# Or create a .env file and source it before running this script.

cd /Users/nithin.borusu/Documents/repos/recon-analysis-ai-bot

# Check if tokens are set
if [ -z "$SLACK_BOT_TOKEN" ]; then
    echo "ERROR: SLACK_BOT_TOKEN environment variable is not set"
    echo "Please set it before running this script:"
    echo "  export SLACK_BOT_TOKEN=\"your-bot-token\""
    exit 1
fi

if [ -z "$SLACK_APP_TOKEN" ]; then
    echo "ERROR: SLACK_APP_TOKEN environment variable is not set"
    echo "Please set it before running this script:"
    echo "  export SLACK_APP_TOKEN=\"your-app-token\""
    exit 1
fi

# Set APP_ENV if not already set
export APP_ENV=${APP_ENV:-dev}

# Activate virtual environment
source .venv/bin/activate

# Stop any existing bot processes
pkill -f "run_socket.py" 2>/dev/null
pkill -f "run.py" 2>/dev/null
sleep 1

echo "============================================================"
echo "Starting Recon Analysis Bot (Socket Mode)"
echo "============================================================"
echo ""
echo "✅ Tokens configured"
echo "✅ Environment: $APP_ENV"
echo ""
echo "Bot is connecting to Slack..."
echo "Watch for: 'Bot is connecting to Slack via Socket Mode...'"
echo "Watch for: 'Waiting for Slack events...'"
echo ""
echo "Press Ctrl+C to stop the bot"
echo ""

# Start the bot
python run_socket.py

