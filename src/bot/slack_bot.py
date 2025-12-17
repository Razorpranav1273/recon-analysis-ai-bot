"""
Slack Bot Main Handler
Flask app for handling Slack events and commands.
"""

import os
import re
from flask import Flask, request, jsonify
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from src.bot.commands import CommandHandler
from src.utils.config_reader import get_config_value
from src.utils.logging import logger

# Initialize Flask app
flask_app = Flask(__name__)

# Initialize Slack app (lazy initialization to avoid token validation on import)
slack_signing_secret = get_config_value("slack.signing_secret", "")
slack_bot_token = get_config_value("slack.bot_token", "")

slack_app = None
if slack_signing_secret and slack_bot_token:
    try:
        slack_app = App(
            token=slack_bot_token,
            signing_secret=slack_signing_secret,
        )
    except Exception as e:
        logger.warning(f"Failed to initialize Slack app (will retry on first request): {e}")
        slack_app = None
else:
    logger.warning("Slack credentials not configured. Bot will not function properly.")

# Initialize command handler
command_handler = CommandHandler()


def _get_slack_app():
    """Get or initialize Slack app."""
    global slack_app
    if slack_app is None:
        slack_signing_secret = get_config_value("slack.signing_secret", "")
        slack_bot_token = get_config_value("slack.bot_token", "")
        if slack_signing_secret and slack_bot_token:
            try:
                slack_app = App(
                    token=slack_bot_token,
                    signing_secret=slack_signing_secret,
                )
                # Register handlers
                _register_slack_handlers(slack_app)
            except Exception as e:
                logger.warning(f"Failed to initialize Slack app: {e}")
                slack_app = None
        else:
            logger.warning("Slack credentials not configured")
    return slack_app


def _register_slack_handlers(app):
    """Register Slack event handlers."""
    @app.command("/recon-analyze")
    def handle_recon_analyze_command(ack, body, respond):
        """
        Handle /recon-analyze slash command.
        """
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

    @app.command("/recon-list-workspaces")
    def handle_list_workspaces_command(ack, body, respond):
        """
        Handle /recon-list-workspaces slash command.
        """
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

    @app.event("app_mention")
    def handle_app_mentions(event, say):
        """
        Handle app mention events.
        """
        try:
            text = event.get("text", "")
            user = event.get("user", "")
            channel = event.get("channel", "")

            logger.info("Received app mention", text=text, user=user, channel=channel)

            # Remove bot mention from text
            # Slack mentions look like: <@U123456> message text
            # Also handle "Recon Analysis Bot" text
            cleaned_text = re.sub(r"<@[^>]+>", "", text).strip()
            cleaned_text = re.sub(r"(?i)recon\s+analysis\s+bot", "", cleaned_text).strip()

            # Handle mention using command handler
            response = command_handler.handle_mention(
                message_text=cleaned_text,
                user_id=user,
                channel_id=channel,
            )

            # Send response
            if isinstance(response, dict) and "blocks" in response:
                say(blocks=response["blocks"], text=response.get("text", ""))
            elif isinstance(response, dict) and "text" in response:
                say(text=response["text"])
            else:
                say(text=str(response))

        except Exception as e:
            logger.error("Error handling app mention", error=str(e))
            say(f"Error: {str(e)}")


# Register handlers if Slack app is initialized
if slack_app:
    _register_slack_handlers(slack_app)


@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    """
    Handle Slack events endpoint.
    """
    try:
        app = _get_slack_app()
        handler = SlackRequestHandler(app)
        return handler.handle(request)
    except Exception as e:
        logger.error(f"Error handling Slack events: {e}")
        return jsonify({"error": "Slack app not initialized"}), 500


@flask_app.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint.
    """
    return jsonify({
        "status": "healthy",
        "service": "recon-analysis-bot",
        "version": "1.0.0",
    })


@flask_app.route("/", methods=["GET"])
def index():
    """
    Root endpoint.
    """
    return jsonify({
        "service": "recon-analysis-bot",
        "version": "1.0.0",
        "endpoints": {
            "/health": "Health check",
            "/slack/events": "Slack events endpoint",
            "/test/analyze": "Test endpoint for local analysis (POST)",
        },
    })


@flask_app.route("/test/analyze", methods=["POST"])
def test_analyze():
    """
    Test endpoint for local analysis.
    Accepts JSON with: workspace_name, file_type, unique_column_value, date_start, date_end
    """
    try:
        data = request.get_json() or {}
        
        workspace_name = data.get("workspace_name") or request.form.get("workspace_name")
        file_type = data.get("file_type") or request.form.get("file_type")
        unique_column_value = data.get("unique_column_value") or request.form.get("unique_column_value")
        date_start = data.get("date_start") or request.form.get("date_start")
        date_end = data.get("date_end") or request.form.get("date_end")
        
        if not workspace_name or not file_type or not unique_column_value:
            return jsonify({
                "error": "Missing required parameters",
                "required": ["workspace_name", "file_type", "unique_column_value"],
                "optional": ["date_start", "date_end"],
            }), 400
        
        # Build command text
        command_text = f"workspace={workspace_name} file_type={file_type} unique_value={unique_column_value}"
        if date_start:
            command_text += f" date_start={date_start}"
        if date_end:
            command_text += f" date_end={date_end}"
        
        logger.info("Test analyze request", workspace_name=workspace_name, file_type=file_type, unique_column_value=unique_column_value)
        
        # Handle command
        response = command_handler.handle_recon_analyze(
            command_text=command_text,
            user_id="test_user",
            channel_id="test_channel",
        )
        
        return jsonify(response)
        
    except Exception as e:
        logger.error("Error in test analyze endpoint", error=str(e))
        return jsonify({
            "error": str(e),
        }), 500


def create_app() -> Flask:
    """
    Create and configure Flask app.

    Returns:
        Configured Flask app
    """
    logger.info("Creating Flask app for recon analysis bot")
    return flask_app


if __name__ == "__main__":
    # Run Flask app
    port = int(os.getenv("PORT", 3000))
    logger.info(f"Starting recon analysis bot on port {port}")
    flask_app.run(host="0.0.0.0", port=port, debug=True)

