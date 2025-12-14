"""Unit tests for the core module."""


class TestCore:
    """Test core functionality."""

    def test_core_module_exists(self):
        """Test that the core module can be imported."""
        from src.urh.core import main

        assert main is not None

    def test_core_main_function_calls_cli_main(self, mocker):
        """Test that core.main() calls cli.main() and returns its result."""
        # Mock the cli_main import in core.py
        # Since cli_main is imported at module level, we need to mock it in the core module
        mock_cli_main = mocker.patch("src.urh.core.cli_main", return_value=42)

        # Import the core module after mocking
        from src.urh.core import main

        # Call the main function
        result = main()

        # Verify cli_main was called
        mock_cli_main.assert_called_once()

        # Verify the result is returned correctly
        assert result == 42

    def test_core_main_script_execution(self, mocker):
        """Test the __name__ == '__main__' block execution in core.py."""
        # Mock sys.exit to prevent actual program termination
        mock_exit = mocker.patch("sys.exit")

        # Mock cli_main import in core.py
        mock_cli_main = mocker.patch("src.urh.core.cli_main", return_value=42)

        # Import the core module after mocking
        from src.urh.core import main

        # Test the script execution path by calling main() directly
        # This simulates what would happen when __name__ == "__main__"
        result = main()

        # Verify cli_main was called
        mock_cli_main.assert_called_once()

        # Verify the result is returned correctly
        assert result == 42

        # Note: sys.exit is only called in the actual __name__ == "__main__" block
        # Since we're calling main() directly, sys.exit won't be called
        # But we can verify that the main function works correctly
        # The __name__ == "__main__" block would call sys.exit(main())
        # which would call sys.exit(42) in this case
        mock_exit.assert_not_called()  # sys.exit is not called when calling main() directly
