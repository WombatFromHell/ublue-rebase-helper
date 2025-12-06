"""
Core application logic for ublue-rebase-helper.
"""

from .cli import main as cli_main


def main():
    """
    Core main function that delegates to the CLI module.
    """
    return cli_main()


if __name__ == "__main__":
    import sys

    sys.exit(main())
