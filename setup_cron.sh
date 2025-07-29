#!/bin/bash
# Setup script for automated email digest scheduling using cron

set -e

# Get the current directory (where the script is located)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_PATH=$(which python3)

echo "🌟 News Digest Cron Setup"
echo "=========================="
echo "Project directory: $PROJECT_DIR"
echo "Python path: $PYTHON_PATH"
echo ""

# Create cron entries
DAILY_CRON="0 21 * * * cd $PROJECT_DIR && $PYTHON_PATH cron_scheduler.py daily >> cron_scheduler.log 2>&1"
WEEKLY_CRON="0 9 * * 1 cd $PROJECT_DIR && $PYTHON_PATH cron_scheduler.py weekly >> cron_scheduler.log 2>&1"

echo "📅 Cron jobs to be installed:"
echo "   Daily digest:  Every day at 9:00 PM"
echo "   Weekly digest: Every Monday at 9:00 AM"
echo ""
echo "Cron entries:"
echo "   $DAILY_CRON"
echo "   $WEEKLY_CRON"
echo ""

# Check if user wants to proceed
read -p "Do you want to install these cron jobs? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Backup existing crontab
    echo "📋 Backing up existing crontab..."
    crontab -l > crontab_backup_$(date +%Y%m%d_%H%M%S).txt 2>/dev/null || echo "No existing crontab found"
    
    # Add new cron jobs
    echo "➕ Adding cron jobs..."
    
    # Get current crontab and add new entries
    (crontab -l 2>/dev/null || echo "") | grep -v "cron_scheduler.py" > temp_cron
    echo "$DAILY_CRON" >> temp_cron
    echo "$WEEKLY_CRON" >> temp_cron
    
    # Install new crontab
    crontab temp_cron
    rm temp_cron
    
    echo "✅ Cron jobs installed successfully!"
    echo ""
    echo "📊 To verify installation:"
    echo "   crontab -l"
    echo ""
    echo "📝 Logs will be written to:"
    echo "   $PROJECT_DIR/cron_scheduler.log"
    echo ""
    echo "🛠️ To remove cron jobs later:"
    echo "   crontab -e  # Edit and remove the lines containing 'cron_scheduler.py'"
    echo ""
    echo "🧪 To test manually:"
    echo "   cd $PROJECT_DIR"
    echo "   python3 cron_scheduler.py daily"
    echo "   python3 cron_scheduler.py weekly"
    
else
    echo "❌ Cron job installation cancelled"
    echo ""
    echo "💡 You can still use the scheduler interactively:"
    echo "   python main.py schedule start"
    echo "   python main.py schedule test-daily"
fi

echo ""
echo "📧 Make sure you have users with email addresses configured:"
echo "   python main.py user list"
echo "   python main.py schedule status"