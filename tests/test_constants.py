"""Unit tests for the constants module."""


class TestConstants:
    """Test constants functionality."""

    def test_constants_module_exists(self):
        """Test that the constants module can be imported."""
        from src.urh.constants import DEFAULT_CONFIG_PATH, MAX_TAGS_DISPLAY

        assert DEFAULT_CONFIG_PATH is not None
        assert MAX_TAGS_DISPLAY is not None
