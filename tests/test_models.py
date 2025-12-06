"""Unit tests for the models module."""

from src.urh.models import GumCommand, ListItem, MenuItem


class TestModels:
    """Test models functionality."""

    def test_menu_item_display_text(self):
        """Test MenuItem display text formatting."""
        item = MenuItem("1", "Option 1")
        assert item.display_text == "1 - Option 1"

        item2 = MenuItem("test", "Test Option")
        assert item2.display_text == "test - Test Option"

    def test_list_item_display_text(self):
        """Test ListItem display text formatting (without key prefix)."""
        item = ListItem("1", "Option 1")
        assert item.display_text == "Option 1"  # No key prefix

        item2 = ListItem("test", "Test Option")
        assert item2.display_text == "Test Option"  # No key prefix

    def test_menu_item_value_property(self):
        """Test MenuItem value property."""
        item = MenuItem("1", "Option 1", value="some_value")
        assert item.value == "some_value"

        # Test default value
        item_default = MenuItem("2", "Option 2")
        assert item_default.value is None

    def test_gum_command_build(self):
        """Test GumCommand command building."""
        cmd = GumCommand(options=["Option 1", "Option 2"], header="Test Header")

        result = cmd.build()

        # Check that the command starts with gum choose
        assert result[:2] == ["gum", "choose"]

        # Check that options are included
        assert "Option 1" in result
        assert "Option 2" in result

        # Check that header is included
        assert "--header" in result

    def test_gum_command_with_persistent_header(self):
        """Test GumCommand with persistent header."""
        cmd = GumCommand(
            options=["Option 1", "Option 2"],
            header="Test Header",
            persistent_header="Persistent info",
        )

        result = cmd.build()

        # Check that both headers are included
        assert "--header" in result

        # The header should include both persistent and regular header
        header_idx = result.index("--header") + 1
        header_value = result[header_idx]
        assert "Test Header" in header_value
        assert "Persistent info" in header_value

    def test_gum_command_customization(self):
        """Test GumCommand with custom parameters."""
        cmd = GumCommand(
            options=["Option 1"],
            header="Test Header",
            cursor=">",
            selected_prefix="* ",
            height=15,
            timeout=600,
        )

        result = cmd.build()

        # Check custom cursor
        assert "--cursor" in result
        cursor_idx = result.index("--cursor") + 1
        assert result[cursor_idx] == ">"

        # Check custom height
        assert "--height" in result
        height_idx = result.index("--height") + 1
        assert result[height_idx] == "15"
