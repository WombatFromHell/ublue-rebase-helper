"""Unit tests for the core module."""


class TestCore:
    """Test core functionality."""

    def test_core_module_exists(self):
        """Test that the core module can be imported."""
        from src.urh.core import main

        assert main is not None
