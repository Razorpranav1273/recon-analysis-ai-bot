"""
Tests for Slack Bot
"""

import pytest
from src.bot.slack_bot import create_app


def test_flask_app_creation():
    """Test Flask app creation."""
    app = create_app()
    assert app is not None


def test_health_endpoint():
    """Test health check endpoint."""
    app = create_app()
    with app.test_client() as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "healthy"

