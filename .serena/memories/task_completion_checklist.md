# Task Completion Checklist

## When completing ANY coding task, you MUST:

### 1. Run Tests
```bash
# Run comprehensive test suite
pytest tests/ -v

# Check test coverage
pytest tests/ --cov=src --cov-report=html
```

### 2. Lint and Format Check
```bash
# Currently no specific linting configured, but check for:
# - Python syntax errors
# - Import issues
# - Basic code quality
```

### 3. Verify Core Functionality
```bash
# Test main CLI interface
/home/rahul/miniconda3/bin/python main.py --help

# Test web interface startup
/home/rahul/miniconda3/bin/python main.py web
# (should start without errors)
```

### 4. Database and Configuration
```bash
# Verify database operations
/home/rahul/miniconda3/bin/python main.py dev db-stats

# Check environment setup
# Ensure .env file has required API keys for AI services
```

### 5. Integration Testing
```bash  
# Test user creation
/home/rahul/miniconda3/bin/python main.py user add test@example.com

# Test digest preview (should work even without API keys)
/home/rahul/miniconda3/bin/python main.py preview test_user --format text
```

### 6. Documentation Updates
- Update README.md if new features added
- Update CLAUDE.md if architecture changes
- Add docstrings for new classes/methods
- Update requirements.txt if new dependencies added

### 7. Error Handling Verification
- Test error cases (invalid user IDs, network failures)
- Verify graceful degradation when AI services unavailable
- Check logging output for appropriate error messages

### 8. Security Check
- No hardcoded API keys or secrets
- Proper input validation and sanitization
- Safe database query practices
- Secure email handling

## CRITICAL: Always use the correct Python path
Use `/home/rahul/miniconda3/bin/python` instead of `python` for all testing and verification!