"""
Tests for Analysis Modules
"""

import pytest
from src.analysis.recon_status_analyzer import ReconStatusAnalyzer
from src.analysis.gap_analyzer import GapAnalyzer
from src.analysis.rule_analyzer import RuleAnalyzer


def test_recon_status_analyzer_initialization():
    """Test recon status analyzer initialization."""
    analyzer = ReconStatusAnalyzer()
    assert analyzer.data_fetcher is not None


def test_gap_analyzer_initialization():
    """Test gap analyzer initialization."""
    analyzer = GapAnalyzer()
    assert analyzer.data_fetcher is not None


def test_rule_analyzer_initialization():
    """Test rule analyzer initialization."""
    analyzer = RuleAnalyzer()
    assert analyzer.data_fetcher is not None

