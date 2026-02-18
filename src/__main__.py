"""
Entry point for zipapp packaging of ublue-rebase-helper.

This file is copied to the staging directory during build and serves as the
__main__.py for the zipapp. The actual entry logic is in entry.py.
"""

from entry import main

if __name__ == "__main__":
    main()
