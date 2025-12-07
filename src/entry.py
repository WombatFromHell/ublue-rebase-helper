"""
Entry point for zipapp packaging of ublue-rebase-helper.
"""

import os
import sys

# Add the parent directory to the path so modules can be found
sys.path.insert(0, os.path.dirname(__file__))

from urh.cli import main as cli_main


def main():
    """Entry point for zipapp."""
    return cli_main()


if __name__ == "__main__":
    main()
