# Suggested Commands

## Python Execution
**IMPORTANT**: Use `/home/rahul/miniconda3/bin/python` instead of `python` to access the correct environment with all dependencies.

## Development Commands

### Setup and Installation
```bash
# Install dependencies
pip install -r requirements.txt

# First-time setup
/home/rahul/miniconda3/bin/python main.py setup

# Start web interface (recommended)
/home/rahul/miniconda3/bin/python main.py web
```

### Testing and Quality Assurance
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Test specific components
pytest tests/test_web_interface.py -v
pytest tests/test_enhanced_ai_processor.py -v
```

### CLI Operations
```bash
# Add new user
/home/rahul/miniconda3/bin/python main.py user add email@example.com

# Run full pipeline for user
/home/rahul/miniconda3/bin/python main.py run user_id

# Send quick digest
/home/rahul/miniconda3/bin/python main.py send user_id

# Preview digest
/home/rahul/miniconda3/bin/python main.py preview user_id --format html
```

### Development and Debugging
```bash
# Show database statistics
/home/rahul/miniconda3/bin/python main.py dev db-stats

# Test email configuration
/home/rahul/miniconda3/bin/python main.py dev test-email user_id

# List all users
/home/rahul/miniconda3/bin/python main.py user list
```

### File Operations
```bash
# List directory contents
ls -la

# Find files by pattern  
find . -name "*.py" -type f

# Search in files
grep -r "pattern" src/

# View logs
tail -f logs/application.log
```

### System Utilities
```bash
# Check Python version and path
which python
python --version

# Monitor system resources
ps aux | grep python
top

# Network testing
curl -I http://localhost:5000
```