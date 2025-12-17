#!/usr/bin/env python3
"""
Run script for recon analysis bot using Socket Mode.
Socket Mode doesn't require ngrok or public URL - bot connects to Slack.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from src.bot.commands import CommandHandler
from src.utils.config_reader import get_config_value
from src.utils.logging import logger


def create_socket_mode_app():
    """Create and configure Slack app for Socket Mode."""
    # Get tokens from config
    slack_bot_token = get_config_value("slack.bot_token", "")
    slack_app_token = get_config_value("slack.app_token", "")
    
    if not slack_bot_token:
        logger.error("SLACK_BOT_TOKEN not configured. Set it in config or environment.")
        raise ValueError("SLACK_BOT_TOKEN is required")
    
    if not slack_app_token:
        logger.error("SLACK_APP_TOKEN not configured. Set it in config or environment.")
        raise ValueError("SLACK_APP_TOKEN is required for Socket Mode")
    
    # Create Slack app
    app = App(token=slack_bot_token)
    
    # Initialize command handler
    command_handler = CommandHandler()
    
    # Register slash command handler
    @app.command("/recon-analyze")
    def handle_recon_analyze_command(ack, body, respond):
        """Handle /recon-analyze slash command."""
        try:
            # Acknowledge command immediately
            ack()
            
            # Get command details
            command_text = body.get("text", "")
            user_id = body.get("user_id", "")
            channel_id = body.get("channel_id", "")
            
            logger.info(
                "Received /recon-analyze command",
                command_text=command_text,
                user_id=user_id,
                channel_id=channel_id,
            )
            
            # Handle command
            response = command_handler.handle_recon_analyze(
                command_text=command_text, user_id=user_id, channel_id=channel_id
            )
            
            # Send response
            respond(response)
            
        except Exception as e:
            logger.error("Error handling /recon-analyze command", error=str(e))
            respond({
                "response_type": "ephemeral",
                "text": f"Error: {str(e)}",
            })
    
    # Register app mention handler
    @app.event("app_mention")
    def handle_app_mentions(event, say):
        """Handle app mention events."""
        try:
            text = event.get("text", "")
            user = event.get("user", "")
            
            logger.info("Received app mention", text=text, user=user)
            
            # Simple response for mentions
            say(f"Hi <@{user}>! Use `/recon-analyze workspace=WORKSPACE_NAME` to analyze reconciliation data.")
            
        except Exception as e:
            logger.error("Error handling app mention", error=str(e))
    
    return app, slack_app_token


def main():
    """Main entry point for Socket Mode bot."""
    try:
        logger.info("Starting recon analysis bot in Socket Mode...")
        
        # Create app
        app, app_token = create_socket_mode_app()
        
        # Create Socket Mode handler
        handler = SocketModeHandler(app, app_token)
        
        logger.info("Bot is connecting to Slack via Socket Mode...")
        logger.info("Press Ctrl+C to stop the bot")
        
        # Start the handler (this blocks until stopped)
        handler.start()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise


if __name__ == "__main__":
    main()

