#!/usr/bin/env python3
"""
News Digest Generator - Clean CLI Interface
A streamlined command-line tool for personalized news digests.
"""

import click
import sys
import os
import json
from datetime import datetime
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.database import DatabaseManager
from src.collector import ArticleCollector
# from ai_processor import AIProcessor  # Migrated to enhanced_ai_processor
from src.incremental_collector import IncrementalCollector
from src.enhanced_ai_processor import EnhancedAIProcessor
from src.user_interface import UserPreferencesManager, DigestGenerator
from config import AI_CATEGORIES, DATABASE_PATH

# Configure logging
logging.basicConfig(level=logging.WARNING)  # Quieter by default
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version='2.0.0')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.pass_context
def cli(ctx, verbose):
    """
    🗞️ News Digest Generator - Get personalized news digests powered by AI
    
    Common workflows:
      • Setup: news setup                    (first-time setup)
      • Add user: news user add email@domain.com
      • Send digest: news send user_id       (quick send)
      • Full pipeline: news run user_id      (collect + process + send)
      • Web interface: news web              (start web interface)
    """
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    if verbose:
        logging.getLogger().setLevel(logging.INFO)


# ============================================================================
# MAIN COMMANDS
# ============================================================================

@cli.command()
def setup():
    """🔧 First-time setup wizard - configure RSS feeds and categories."""
    click.echo("🚀 Welcome to News Digest Generator!")
    click.echo()
    
    try:
        db_manager = DatabaseManager()
        
        # Check if already set up
        feeds = db_manager.get_all_feeds()
        if feeds:
            click.echo(f"✅ System already configured with {len(feeds)} RSS feeds")
            if not click.confirm("Reconfigure system?"):
                return
        
        click.echo("📡 Setting up RSS feeds...")
        
        # Quick setup with default feeds
        from src.feed_setup import setup_default_feeds
        setup_default_feeds(db_manager)
        
        click.echo("✅ Setup complete!")
        click.echo()
        click.echo("Next steps:")
        click.echo("  1. Add a user: news user add your@email.com")
        click.echo("  2. Send digest: news send your_user_id")
        click.echo("  3. Start web interface: news web")
        
    except Exception as e:
        click.echo(f"❌ Setup failed: {e}", err=True)
        sys.exit(1)


@cli.command()
def web():
    """🌐 Start the web interface (recommended for most users)."""
    try:
        click.echo("🌐 Starting web interface...")
        click.echo("📍 Open your browser to: http://localhost:5000")
        click.echo("⏹️  Press Ctrl+C to stop")
        
        # Import and start web interface
        from src.web_interface import app
        app.run(host='localhost', port=5000, debug=False)
        
    except KeyboardInterrupt:
        click.echo("\n👋 Web interface stopped")
    except Exception as e:
        click.echo(f"❌ Web interface failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('user_id')
@click.option('--articles', '-n', type=int, help='Number of articles (default: user preference)')
@click.option('--categories', '-c', multiple=True, help='Specific categories only')
@click.option('--no-collect', is_flag=True, help='Use existing articles (no collection)')
def send(user_id, articles, categories, no_collect):
    """📧 Send digest email to user (quick send using existing articles)."""
    click.echo(f"📧 Sending digest to: {user_id}")
    
    try:
        # Check user exists
        db_manager = DatabaseManager()
        user_prefs = db_manager.get_user_preferences(user_id)
        if not user_prefs:
            click.echo(f"❌ User '{user_id}' not found")
            click.echo("💡 Add user first: news user add email@domain.com")
            sys.exit(1)
        
        # Send email using enhanced AI system
        from src.email_delivery_refactored import RefactoredEmailDeliveryManager
        from src.enhanced_ai_processor import EnhancedAIProcessor
        
        ai_processor = EnhancedAIProcessor()
        email_manager = RefactoredEmailDeliveryManager(db_manager, ai_processor)
        
        # Generate digest data
        digest_gen = DigestGenerator(db_manager)
        articles_list = digest_gen.get_personalized_articles(user_id, articles)
        
        if not articles_list:
            click.echo("⚠️ No articles found for user's categories")
            if not no_collect:
                click.echo("🔄 Try running: news collect first")
            sys.exit(1)
        
        # Convert to email format
        digest_data = {
            'categories': {},
            'user_id': user_id,
            'generated_at': datetime.now().isoformat()
        }
        
        # Group by category with deduplication (each article appears only once)
        user_categories = user_prefs['selected_categories']
        by_category = {cat: [] for cat in user_categories}
        processed_articles = set()  # Track by article ID to prevent duplicates
        
        # Sort articles by date to prioritize newer ones
        sorted_articles = sorted(articles_list, key=lambda x: x.get('date_collected', ''), reverse=True)
        
        for article in sorted_articles:
            article_id = article.get('id')
            
            # STRICT deduplication - skip if already processed
            if article_id in processed_articles:
                continue
                
            # Get article categories
            article_categories = article.get('ai_categories', [])
            if isinstance(article_categories, str):
                import json
                try:
                    article_categories = json.loads(article_categories)
                except:
                    article_categories = ['General']
            
            # Find the FIRST matching category for this article from user's preferences
            # This ensures each article goes to exactly one category
            best_category = None
            for user_cat in user_categories:
                if user_cat in article_categories:
                    best_category = user_cat
                    break
            
            # If matched, add to that category and mark as processed
            if best_category:
                by_category[best_category].append(article)
                processed_articles.add(article_id)
        
        # Remove empty categories and limit articles per category
        for cat, cat_articles in by_category.items():
            if cat_articles:
                digest_data['categories'][cat] = cat_articles[:5]
        
        success, message = email_manager.deliver_digest_email(user_id, digest_data)
        
        if success:
            click.echo(f"✅ {message}")
        else:
            click.echo(f"❌ Failed: {message}")
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('user_id')
@click.option('--articles', '-n', type=int, default=15, help='Articles per feed')
@click.option('--skip-ai', is_flag=True, help='Skip AI processing')
def run(user_id, articles, skip_ai):
    """🚀 Full pipeline: collect articles, process with AI, and send digest."""
    click.echo(f"🚀 Running full pipeline for: {user_id}")
    
    try:
        # Step 1: Collect articles
        click.echo("📡 Step 1: Collecting articles...")
        collector = IncrementalCollector()
        stats = collector.run_incremental_collection(max_per_feed=articles)
        new_count = stats['new'] + stats['updated']
        click.echo(f"✅ Collected {new_count} articles")
        
        # Step 2: AI Processing (optional)
        if not skip_ai and new_count > 0:
            click.echo("🤖 Step 2: AI processing...")
            processor = EnhancedAIProcessor()
            ai_stats = processor.run_enhanced_processing_cycle()
            click.echo(f"✅ Processed {ai_stats['processed']} articles")
        
        # Step 3: Send digest
        click.echo("📧 Step 3: Sending digest...")
        # Use the send command logic
        ctx = click.get_current_context()
        ctx.invoke(send, user_id=user_id, articles=None, categories=(), no_collect=True)
        
    except Exception as e:
        click.echo(f"❌ Pipeline failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--articles', '-n', type=int, default=15, help='Articles per feed')
@click.option('--categories', '-c', multiple=True, help='Specific categories only')
def collect(articles, categories):
    """📡 Collect articles from RSS feeds."""
    click.echo("📡 Collecting articles from RSS feeds...")
    
    try:
        collector = IncrementalCollector()
        stats = collector.run_incremental_collection(
            max_per_feed=articles,
            categories=list(categories) if categories else None
        )
        
        total = stats['new'] + stats['updated']
        click.echo(f"✅ Collection complete!")
        click.echo(f"   📄 {stats['new']} new articles")
        click.echo(f"   🔄 {stats['updated']} updated articles")
        click.echo(f"   ⏭️ {stats['skipped']} skipped (duplicates)")
        if stats.get('errors', 0) > 0:
            click.echo(f"   ❌ {stats['errors']} errors")
            
    except Exception as e:
        click.echo(f"❌ Collection failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--batch-size', '-b', type=int, default=50, help='Process articles in batches')
def process(batch_size):
    """🤖 Process articles with AI (categorization and summarization)."""
    click.echo("🤖 Processing articles with AI...")
    
    try:
        processor = EnhancedAIProcessor()
        stats = processor.run_enhanced_processing_cycle(batch_size)
        
        click.echo(f"✅ AI processing complete!")
        click.echo(f"   📄 {stats['processed']} articles processed")
        if 'total_cost' in stats:
            click.echo(f"   💰 ${stats['total_cost']:.4f} total cost")
            
    except Exception as e:
        click.echo(f"❌ AI processing failed: {e}", err=True)
        sys.exit(1)




@cli.command()
@click.argument('user_id')
@click.option('--format', type=click.Choice(['text', 'html']), default='text', help='Preview format')
@click.option('--save', help='Save preview to file')
@click.option('--count', type=int, help='Number of articles')
def preview(user_id, format, save, count):
    """👁️ Preview digest for user without sending email."""
    
    click.echo(f"👁️ Generating {format} preview for: {user_id}")
    
    try:
        db_manager = DatabaseManager()
        
        # Check if user exists
        user_prefs = db_manager.get_user_preferences(user_id)
        if not user_prefs:
            click.echo(f"❌ User '{user_id}' not found. Create user first with: news user add")
            sys.exit(1)
        
        # Generate digest
        digest_gen = DigestGenerator(db_manager)
        
        # Update format preference temporarily
        original_format = user_prefs.get('preferred_output_format', 'text')
        output_format = 'email' if format == 'html' else format
        
        if output_format != original_format:
            prefs_manager = UserPreferencesManager(db_manager)
            prefs_manager.update_user_preferences(user_id, preferred_output_format=output_format)
        
        # Add article count override if provided
        if count:
            click.echo(f"📊 Using article override: {count} articles (instead of user default)")
            
        result = digest_gen.generate_digest(user_id, article_count_override=count)
        
        # Restore original format
        if output_format != original_format:
            prefs_manager.update_user_preferences(user_id, preferred_output_format=original_format)
        
        # Output result
        content = result.get('content', str(result)) if isinstance(result, dict) else str(result)
        
        if save:
            with open(save, 'w', encoding='utf-8') as f:
                f.write(content)
            click.echo(f"✅ Preview saved to: {save}")
        else:
            click.echo(content)
        
    except Exception as e:
        click.echo(f"❌ Preview failed: {e}", err=True)
        sys.exit(1)


@cli.group()
def user():
    """User management commands."""
    pass


@user.command('add')
@click.argument('email')
@click.option('--id', 'user_id', help='Custom user ID')
@click.option('--count', type=int, default=10, help='Articles per digest')
def add_user(email, user_id, count):
    """Add a new user with email and preferences."""
    
    try:
        # Validate email format
        if '@' not in email or '.' not in email.split('@')[1]:
            click.echo("❌ Invalid email format", err=True)
            sys.exit(1)
        
        prefs_manager = UserPreferencesManager()
        
        # Show available categories
        click.echo("📂 Available categories:")
        for i, cat in enumerate(AI_CATEGORIES, 1):
            click.echo(f"  {i:2d}. {cat}")
        
        # Interactive category selection
        if click.confirm("\nSelect categories interactively?"):
            category_input = click.prompt("Enter category numbers (comma-separated)", type=str)
            try:
                indices = [int(x.strip()) - 1 for x in category_input.split(',')]
                categories = [AI_CATEGORIES[i] for i in indices if 0 <= i < len(AI_CATEGORIES)]
            except (ValueError, IndexError):
                click.echo("⚠️ Invalid selection. Using defaults.")
                categories = ['Technology & Gadgets', 'Science & Discovery']
        else:
            categories = ['Technology & Gadgets', 'Science & Discovery']
        
        # Create user
        created_user_id = prefs_manager.create_user(
            user_id=user_id,
            email=email,
            categories=categories,
            articles_per_digest=count,
            preferred_output_format='email'
        )
        
        click.echo(f"✅ User created: {created_user_id}")
        click.echo(f"📧 Email: {email}")
        click.echo(f"📂 Categories: {', '.join(categories)}")
        click.echo(f"📊 Articles per digest: {count}")
        
    except Exception as e:
        click.echo(f"❌ Failed to create user: {e}", err=True)
        sys.exit(1)


@user.command('list')
def list_users():
    """List all users."""
    
    try:
        db_manager = DatabaseManager()
        users = db_manager.get_all_users()
        
        if not users:
            click.echo("👥 No users found.")
            click.echo("💡 Create a user with: news user add <email>")
            return
        
        click.echo(f"👥 Found {len(users)} users:")
        click.echo("=" * 60)
        
        for user in users:
            click.echo(f"🆔 {user['user_id']}")
            if user.get('email'):
                click.echo(f"📧 {user['email']}")
            click.echo(f"📂 Categories: {', '.join(user['selected_categories'])}")
            click.echo(f"📊 Articles per digest: {user['articles_per_digest']}")
            click.echo("-" * 40)
        
    except Exception as e:
        click.echo(f"❌ Error listing users: {e}", err=True)


@user.command('remove')
@click.argument('user_id')
@click.option('--yes', is_flag=True, help='Skip confirmation')
def remove_user(user_id, yes):
    """Remove a user."""
    
    try:
        db_manager = DatabaseManager()
        user_prefs = db_manager.get_user_preferences(user_id)
        
        if not user_prefs:
            click.echo(f"❌ User '{user_id}' not found", err=True)
            sys.exit(1)
        
        if not yes:
            click.echo(f"⚠️ This will permanently delete user '{user_id}'.")
            if not click.confirm("Continue?"):
                click.echo("Cancelled.")
                return
        
        # Remove user
        if hasattr(db_manager, 'remove_user'):
            success = db_manager.remove_user(user_id)
            if success:
                click.echo(f"✅ User '{user_id}' removed")
            else:
                click.echo(f"❌ Failed to remove user '{user_id}'")
        else:
            click.echo("❌ User removal not implemented")
        
    except Exception as e:
        click.echo(f"❌ Error removing user: {e}", err=True)


@user.command('show')
@click.argument('user_id')
def show_user(user_id):
    """Show user details."""
    
    try:
        db_manager = DatabaseManager()
        user_prefs = db_manager.get_user_preferences(user_id)
        
        if not user_prefs:
            click.echo(f"❌ User '{user_id}' not found", err=True)
            sys.exit(1)
        
        click.echo(f"👤 User: {user_id}")
        click.echo("=" * 50)
        click.echo(f"📧 Email: {user_prefs.get('email', 'Not set')}")
        click.echo(f"📂 Categories: {', '.join(user_prefs['selected_categories'])}")
        click.echo(f"📊 Articles per digest: {user_prefs['articles_per_digest']}")
        click.echo(f"📄 Output format: {user_prefs['preferred_output_format']}")
        
        # Show email preferences if available
        if hasattr(db_manager, 'get_email_preferences'):
            email_prefs = db_manager.get_email_preferences(user_id)
            if email_prefs:
                click.echo(f"📧 Email enabled: {'Yes' if email_prefs.get('email_enabled', True) else 'No'}")
                click.echo(f"📅 Delivery frequency: {email_prefs.get('delivery_frequency', 'daily')}")
        
        # Show basic engagement stats if available
        if hasattr(db_manager, 'get_user_engagement_summary'):
            engagement = db_manager.get_user_engagement_summary(user_id, 30)
            if engagement and any(v > 0 for v in engagement.values()):
                click.echo(f"\n📈 30-day engagement:")
                click.echo(f"   📧 Emails sent: {engagement.get('total_emails', 0)}")
                click.echo(f"   👍 Articles liked: {engagement.get('total_likes', 0)}")
                click.echo(f"   👎 Articles disliked: {engagement.get('total_dislikes', 0)}")
        
    except Exception as e:
        click.echo(f"❌ Error showing user: {e}", err=True)


@user.command('edit')
@click.argument('user_id')
@click.option('--email', help='Update email address')
@click.option('--count', type=int, help='Articles per digest')
@click.option('--format', type=click.Choice(['text', 'markdown', 'email']), help='Output format')
def edit_user(user_id, email, count, format):
    """Edit user preferences."""
    
    try:
        db_manager = DatabaseManager()
        user_prefs = db_manager.get_user_preferences(user_id)
        
        if not user_prefs:
            click.echo(f"❌ User '{user_id}' not found", err=True)
            sys.exit(1)
        
        prefs_manager = UserPreferencesManager(db_manager)
        updates = {}
        
        # Update email address
        if email:
            if '@' not in email or '.' not in email.split('@')[1]:
                click.echo("❌ Invalid email format", err=True)
                sys.exit(1)
            
            if hasattr(db_manager, 'update_user_email'):
                if db_manager.update_user_email(user_id, email):
                    click.echo(f"✅ Email updated: {email}")
                else:
                    click.echo("❌ Failed to update email")
                    sys.exit(1)
            else:
                updates['email'] = email
                click.echo(f"📧 Email will be updated: {email}")
        
        # Handle other updates
        if count:
            updates['articles_per_digest'] = count
            click.echo(f"📊 Articles per digest: {count}")
        
        if format:
            updates['preferred_output_format'] = format
            click.echo(f"📄 Output format: {format}")
        
        # Apply updates
        if updates:
            prefs_manager.update_user_preferences(user_id, **updates)
            click.echo(f"✅ User preferences updated!")
        elif not email:
            click.echo("ℹ️ No updates specified.")
        
    except Exception as e:
        click.echo(f"❌ Error updating user: {e}", err=True)
        sys.exit(1)



# Development and maintenance commands
@cli.group()
def dev():
    """Development and debugging commands."""
    pass


@dev.command('test-email')
@click.argument('user_id')
def test_email(user_id):
    """Test email configuration."""
    
    try:
        from src.email_delivery_refactored import RefactoredEmailDeliveryManager
        
        db_manager = DatabaseManager()
        user_prefs = db_manager.get_user_preferences(user_id)
        
        if not user_prefs:
            click.echo(f"❌ User '{user_id}' not found", err=True)
            sys.exit(1)
        
        email_manager = RefactoredEmailDeliveryManager(db_manager, None)
        config_status = email_manager.get_configuration_status()
        
        if config_status['configured']:
            click.echo("✅ Email configuration valid")
        else:
            click.echo("❌ Email configuration issues:")
            for error in config_status['errors']:
                click.echo(f"   - {error}")
        
    except Exception as e:
        click.echo(f"❌ Error testing email: {e}", err=True)


@dev.command('db-stats')
def db_stats():
    """Show database statistics."""
    
    try:
        db_manager = DatabaseManager()
        
        # Get basic counts
        users = db_manager.get_all_users()
        articles = db_manager.get_all_articles()
        
        click.echo("📊 Database Statistics")
        click.echo("=" * 30)
        click.echo(f"👥 Users: {len(users) if users else 0}")
        click.echo(f"📰 Articles: {len(articles) if articles else 0}")
        
        # Show category distribution if articles exist
        if articles:
            categories = {}
            for article in articles:
                if article.get('ai_categories'):
                    for cat in article['ai_categories']:
                        categories[cat] = categories.get(cat, 0) + 1
            
            if categories:
                click.echo("\n📂 Category Distribution:")
                for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                    click.echo(f"   {cat}: {count}")
        
    except Exception as e:
        click.echo(f"❌ Error getting stats: {e}", err=True)


# Main entry point
if __name__ == '__main__':
    cli()
