"""
Slack Bot Main Handler
Flask app for handling Slack events and commands.
"""

import os
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

    @app.event("app_mention")
    def handle_app_mentions(event, say):
        """
        Handle app mention events.
        """
        try:
            text = event.get("text", "")
            user = event.get("user", "")

            logger.info("Received app mention", text=text, user=user)

            # Simple response for mentions
            say(f"Hi <@{user}>! Use `/recon-analyze workspace=WORKSPACE_NAME` to analyze reconciliation data.")

        except Exception as e:
            logger.error("Error handling app mention", error=str(e))


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
        },
    })


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

