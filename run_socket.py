#!/usr/bin/env python3
"""
Run script for recon analysis bot using Socket Mode.
Socket Mode doesn't require ngrok or public URL - bot connects to Slack.
"""

import sys
import os
import ssl
import re

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from src.bot.commands import CommandHandler
from src.utils.config_reader import get_config_value
from src.utils.logging import logger

# Fix SSL certificate issue on macOS for both HTTP and WebSocket
import os
# Disable SSL verification via environment variables (affects all SSL connections)
os.environ['PYTHONHTTPSVERIFY'] = '0'

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# Create unverified SSL context for WebSocket connections
_unverified_ssl_context = ssl._create_unverified_context()

# Monkey-patch websockets library to use unverified SSL context
# This is needed because Slack SDK uses websockets for Socket Mode connections
try:
    import websockets
    _original_ssl_context = websockets.client._ssl_context
    
    def _patched_ssl_context():
        return _unverified_ssl_context
    
    websockets.client._ssl_context = _patched_ssl_context
    logger.info("Patched websockets SSL context for unverified connections")
except (ImportError, AttributeError) as e:
    # websockets might not be imported yet or structure is different
    # We'll patch it when it's imported
    pass


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
    
    # Create Slack app with token verification disabled (for development)
    # This avoids SSL certificate issues during auth.test
    app = App(
        token=slack_bot_token,
        token_verification_enabled=False,  # Disable for development to avoid SSL issues
    )
    
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
    
    # Register list workspaces command handler
    @app.command("/recon-list-workspaces")
    def handle_list_workspaces_command(ack, body, respond):
        """Handle /recon-list-workspaces slash command."""
        try:
            # Acknowledge command immediately
            ack()
            
            logger.info("Received /recon-list-workspaces command")
            
            # Handle command
            response = command_handler.handle_list_workspaces()
            
            # Send response
            respond(response)
            
        except Exception as e:
            logger.error("Error handling /recon-list-workspaces command", error=str(e))
            respond({
                "response_type": "ephemeral",
                "text": f"Error: {str(e)}",
            })
    
    # Register app mention handler
    @app.event("app_mention")
    def handle_app_mentions(event, say):
        """Handle app mention events with natural language processing."""
        try:
            logger.info("=" * 60)
            logger.info("🔔 APP MENTION EVENT RECEIVED!")
            logger.info("=" * 60)
            
            # Acknowledge immediately
            text = event.get("text", "")
            user = event.get("user", "")
            channel_id = event.get("channel", "")
            
            logger.info(f"📨 Original text: {text}")
            logger.info(f"👤 User: {user}")
            logger.info(f"📢 Channel: {channel_id}")
            logger.info(f"📋 Full event keys: {list(event.keys())}")
            
            # Remove bot mention from text
            # Pattern: <@BOT_USER_ID> or <@BOT_USER_ID|bot_name>
            import re
            cleaned_text = re.sub(r"<@[^>]+>", "", text).strip()
            # Also remove "Recon Analysis Bot" text if present
            cleaned_text = re.sub(r"(?i)recon\s+analysis\s+bot", "", cleaned_text).strip()
            
            logger.info(f"🧹 Cleaned text: {cleaned_text}")
            
            # Handle mention with natural language processing
            logger.info("🔄 Processing mention with command handler...")
            response = command_handler.handle_mention(
                message_text=cleaned_text,
                user_id=user,
                channel_id=channel_id,
            )
            
            logger.info(f"✅ Response generated: {type(response).__name__}")
            
            # Send response
            if isinstance(response, dict) and "blocks" in response:
                logger.info("📤 Sending response with blocks")
                say(blocks=response["blocks"], text=response.get("text", ""))
            elif isinstance(response, dict) and "text" in response:
                logger.info("📤 Sending text response")
                say(text=response["text"])
            else:
                logger.info("📤 Sending string response")
                say(text=str(response))
            
            logger.info("✅ Response sent successfully!")
            
        except Exception as e:
            logger.error("❌ Error handling app mention", error=str(e), exc_info=True)
            say(f"Sorry, I encountered an error: {str(e)}")
    
    # Add a catch-all event handler to see ALL events
    @app.event({"type": re.compile(".*")})
    def handle_all_events(event, say):
        """Log all events for debugging."""
        event_type = event.get("type", "unknown")
        if event_type not in ["app_mention", "message"]:  # Don't log every message
            logger.debug(f"📥 Received event type: {event_type}")
    
    return app, slack_app_token


def main():
    """Main entry point for Socket Mode bot."""
    try:
        logger.info("Starting recon analysis bot in Socket Mode...")
        
        # Create app
        app, app_token = create_socket_mode_app()
        
        logger.info("Socket Mode app created successfully")
        logger.info(f"App token configured: {bool(app_token)}")
        
        # Create Socket Mode handler
        # SSL context for WebSocket is configured via monkey-patch above
        handler = SocketModeHandler(app, app_token)
        
        logger.info("Socket Mode handler created")
        logger.info("Bot is connecting to Slack via Socket Mode...")
        logger.info("Press Ctrl+C to stop the bot")
        logger.info("Waiting for Slack events...")
        logger.info("Note: SSL verification is disabled for development (macOS certificate issue)")
        
        # Start the handler (this blocks until stopped)
        handler.start()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()

