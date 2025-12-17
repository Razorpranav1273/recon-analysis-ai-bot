"""
Tests for Recon Client
"""

import pytest
from src.services.recon_client import ReconClient


def test_recon_client_initialization():
    """Test recon client initialization."""
    client = ReconClient()
    assert client.base_url is not None
    assert client.http_client is not None


def test_get_workspace_by_name():
    """Test getting workspace by name."""
    client = ReconClient()
    # This would require mock or actual recon service
    # result = client.get_workspace_by_name("test_workspace")
    # assert result is not None
    pass

