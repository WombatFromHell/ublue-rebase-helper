"""Unit tests for the validators module."""


class TestValidators:
    """Test validators functionality."""

    def test_validators_module_exists(self):
        """Test that the validators module can be imported."""
        from src.urh.validators import is_valid_deployment_info

        assert is_valid_deployment_info is not None
