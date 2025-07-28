#!/usr/bin/env python3
"""Cron job entry point for automated email digest scheduling."""

import sys
import os
import logging
from datetime import datetime

# Add the project directory to Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

# Change to project directory
os.chdir(project_dir)

from src.scheduler import DigestScheduler

# Setup logging for cron
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cron_scheduler.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def send_daily_digest():
    """Send daily digest - to be called by cron."""
    try:
        logger.info("🌅 Starting daily digest cron job")
        scheduler = DigestScheduler()
        scheduler.send_daily_digests()
        logger.info("✅ Daily digest cron job completed successfully")
    except Exception as e:
        logger.error(f"❌ Daily digest cron job failed: {e}")
        sys.exit(1)

def send_weekly_digest():
    """Send weekly digest - to be called by cron."""
    try:
        logger.info("📅 Starting weekly digest cron job")
        scheduler = DigestScheduler()
        scheduler.send_weekly_digests()
        logger.info("✅ Weekly digest cron job completed successfully")
    except Exception as e:
        logger.error(f"❌ Weekly digest cron job failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python cron_scheduler.py [daily|weekly]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "daily":
        send_daily_digest()
    elif command == "weekly":
        send_weekly_digest()
    else:
        print("Invalid command. Use 'daily' or 'weekly'")
        sys.exit(1)