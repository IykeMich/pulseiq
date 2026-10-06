"""Shared fixtures. Tests use the committed artifacts in artifacts/ (run python -m src.train first)."""
import pytest

from src.analyzer import PulseAnalyzer


@pytest.fixture(scope="session")
def analyzer():
    return PulseAnalyzer.load()
