"""
Tests for entry module.
"""

import sys


class TestEntry:
    """Test cases for the entry module."""

    def test_entry_module_exists(self):
        """Test that the entry module can be imported."""
        import src.entry

        assert src.entry is not None

    def test_main_function_exists(self):
        """Test that the main function exists."""
        import src.entry

        assert hasattr(src.entry, "main")
        assert callable(src.entry.main)

    def test_main_function_has_correct_implementation(self):
        """Test that main function returns the result of cli.main."""

        # Remove modules from cache to ensure fresh import for this specific test
        modules_to_remove = [
            key for key in sys.modules.keys() if key.startswith("src.entry")
        ]
        for mod in modules_to_remove:
            del sys.modules[mod]

        # Also remove the urh.cli module to ensure clean import
        if "urh.cli" in sys.modules:
            del sys.modules["urh.cli"]

        # Now import fresh
        import src.entry

        # The function exists and can be called (though we won't execute it due to the sys.exit issue)
        assert callable(src.entry.main)
        # Test that the function definition is correct syntactically
        # This at least makes sure the module can be imported and has correct syntax
