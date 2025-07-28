#!/usr/bin/env python3
"""Development web server launcher with proper authentication bypass."""

import os
import sys

# Set development environment variables
os.environ['FLASK_ENV'] = 'development'
os.environ['DEBUG'] = 'True'
os.environ['TESTING_MODE'] = 'true'

# Add src to path for imports
sys.path.insert(0, 'src')

def main():
    """Launch the web interface in development mode."""
    print("🌐 Starting News Digest Web Interface (Development Mode)")
    print("   URL: http://localhost:5001")
    print("   Authentication: Bypassed for development")
    print("   Debug: Enabled")
    print("=" * 60)
    
    try:
        # Import and configure the Flask app
        from web_interface import app
        
        # Configure for development
        app.config['TESTING'] = True
        app.config['DEBUG'] = True
        app.config['ENV'] = 'development'
        
        print("✅ Flask app configured for development")
        print("✅ Background job manager started")
        print("✅ Authentication bypass enabled")
        print("\n🚀 Web server starting...")
        print("   Use X-User-ID header for API authentication")
        print("   Example: curl -H 'X-User-ID: TestCLI' http://localhost:5001/api/...")
        print()
        
        # Start the web server
        app.run(
            host='0.0.0.0',
            port=5001,
            debug=True,
            use_reloader=False,  # Avoid double startup in debug mode
            threaded=True
        )
        
    except ImportError as e:
        print(f"❌ Failed to import web interface: {e}")
        print("   Make sure you're in the correct directory and all dependencies are installed")
        return 1
    except Exception as e:
        print(f"❌ Failed to start web server: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())