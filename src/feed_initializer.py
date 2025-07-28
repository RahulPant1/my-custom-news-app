"""RSS feeds table initialization - DEPRECATED

This script was used to initialize feeds from config.py.
Now feeds are managed directly via CLI commands:

- Add feeds: python main.py feeds add <category> <url>
- List feeds: python main.py feeds list
- Validate feeds: python main.py validate --update-db

The RSS_FEEDS configuration has been removed from config.py in favor of 
database-driven feed management.
"""

import sys
import os
import logging

logger = logging.getLogger(__name__)

def main():
    print("⚠️  This initializer is deprecated!")
    print("📚 RSS feeds are now managed through the database.")
    print("")
    print("🔧 To manage feeds, use these commands:")
    print("   python main.py feeds add <category> <url>")
    print("   python main.py feeds list")
    print("   python main.py validate --update-db")
    print("")
    print("✅ Your existing feeds are already in the database.")

if __name__ == "__main__":
    main()