# Code Style and Conventions

## Code Organization
- **src/** directory contains all main source code
- **tests/** directory for comprehensive test coverage
- **templates/** for Flask HTML templates  
- **static/** for CSS, JS, and other static assets
- **logs/** for application logging output

## Python Style
- **PEP 8 compliance** for code formatting
- **Type hints** used extensively throughout codebase
- **Docstrings** for classes and complex functions
- **Logging** using structured logging with different levels
- **Error handling** with custom exception classes in `src/core/exceptions.py`

## Module Structure
- **Classes** are the primary organizational unit
- **Factory patterns** used for service creation (email, AI adapters)
- **Adapter patterns** for AI service integration
- **Manager classes** for complex operations (DatabaseManager, EmailManager)
- **Repository patterns** for data access

## Import Organization
- Standard library imports first
- Third-party imports second  
- Local imports last
- Use `from src.module import Class` format for internal imports

## Configuration Management
- **Environment variables** in `.env` file (never commit!)
- **config.py** for application-wide constants
- **Settings modules** in `src/settings/` for specialized config
- **YAML configuration** for AI model settings

## Database Conventions
- **SQLite** as primary database
- **Schema migrations** handled in setup process
- **Connection pooling** for performance
- **Prepared statements** for security
- **Transaction management** for data integrity

## Error Handling
- **Custom exceptions** defined in `src/core/exceptions.py`  
- **Decorator-based error handling** for common patterns
- **Comprehensive logging** with context information
- **Graceful fallbacks** for AI service failures

## Testing Approach
- **pytest** framework with fixtures
- **Mocking** for external dependencies (AI APIs, RSS feeds)
- **Coverage reporting** with minimum thresholds
- **Integration tests** for end-to-end workflows
- **Unit tests** for individual components

## Naming Conventions
- **snake_case** for functions and variables
- **PascalCase** for classes
- **UPPER_CASE** for constants
- **Descriptive names** that explain purpose
- **Consistent naming** across similar operations