"""
Entry point for zipapp packaging of ublue-rebase-helper.
"""

import os
import sys

# Handle both zipapp execution and direct import scenarios
# When running as zipapp or when imported as src.entry, ensure the parent directory is in sys.path
if __name__ == "__main__" or __name__ == "src.entry":
    # When running as zipapp or script, ensure the parent directory is in sys.path
    # This allows the zipapp to find the urh package
    if not any(os.path.dirname(__file__) in p for p in sys.path):
        sys.path.insert(0, os.path.dirname(__file__))

from urh.cli import main as cli_main


def main():
    """Entry point for zipapp."""
    return cli_main()


if __name__ == "__main__":
    main()
