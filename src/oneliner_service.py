"""One-liner generation service for email highlights."""

import logging
from datetime import datetime, date
from typing import Dict, List, Optional
import json

try:
    from src.enhanced_ai_processor import EnhancedAIProcessor
except ImportError:
    try:
        from enhanced_ai_processor import EnhancedAIProcessor
    except ImportError:
        EnhancedAIProcessor = None

try:
    from src.database import DatabaseManager
except ImportError:
    from database import DatabaseManager
try:
    from config import AI_CATEGORIES
except ImportError:
    AI_CATEGORIES = ['Science & Discovery', 'Technology & Gadgets', 'Health & Wellness', 'Business & Finance', 'Global Affairs', 'Environment & Climate', 'Good Vibes (Positive News)', 'Pop Culture & Lifestyle', 'For Young Minds (Youth-Focused)', 'DIY, Skills & How-To']

logger = logging.getLogger(__name__)


class OnelinerGenerationService:
    """Service for generating and managing daily one-liners for email highlights."""
    
    def __init__(self, ai_processor: EnhancedAIProcessor = None, db_manager: DatabaseManager = None):
        if ai_processor:
            self.ai_processor = ai_processor
        elif EnhancedAIProcessor:
            self.ai_processor = EnhancedAIProcessor()
        else:
            self.ai_processor = None
        self.db_manager = db_manager or DatabaseManager()
        self.generation_stats = {
            'total_generated': 0,
            'successful_saves': 0,
            'api_calls': 0,
            'errors': 0
        }
    
    def generate_daily_oneliners(self, generation_date: str = None, oneliners_per_category: int = 10) -> Dict:
        """Generate one-liners for all categories in a single API call."""
        if not generation_date:
            generation_date = date.today().strftime('%Y-%m-%d')
        
        logger.info(f"Generating {oneliners_per_category} one-liners per category for {generation_date} (optimized single API call)")
        
        results = {
            'generation_date': generation_date,
            'total_generated': 0,
            'successful_saves': 0,
            'by_category': {},
            'errors': []
        }
        
        # Check existing one-liners
        existing = self.db_manager.get_oneliners_by_date(generation_date)
        existing_by_category = {}
        for item in existing:
            cat = item['category']
            existing_by_category[cat] = existing_by_category.get(cat, 0) + 1
        
        # Determine which categories need one-liners
        categories_to_generate = []
        for category in AI_CATEGORIES:
            if existing_by_category.get(category, 0) < oneliners_per_category:
                categories_to_generate.append(category)
        
        if not categories_to_generate:
            logger.info("Sufficient one-liners already exist for all categories")
            return results
        
        # Generate all one-liners in a single API call
        try:
            all_oneliners = self._generate_all_oneliners_optimized(
                categories_to_generate, oneliners_per_category, generation_date
            )
            
            if all_oneliners:
                # Count by category
                for oneliner in all_oneliners:
                    category = oneliner['category']
                    results['by_category'][category] = results['by_category'].get(category, 0) + 1
                    results['total_generated'] += 1
                
                # Save to database
                saved_count = self.db_manager.save_daily_oneliners(all_oneliners)
                results['successful_saves'] = saved_count
                self.generation_stats['successful_saves'] += saved_count
                
                logger.info(f"Single API call generated {results['total_generated']} one-liners")
                logger.info(f"Saved {saved_count} one-liners to database")
                
                # Log by category
                for category, count in results['by_category'].items():
                    logger.info(f"  - {category}: {count} one-liners")
                    
            else:
                results['errors'].append("Failed to generate any one-liners from API call")
                
        except Exception as e:
            error_msg = f"Error in optimized one-liner generation: {str(e)}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            self.generation_stats['errors'] += 1
        
        # Update stats
        self.generation_stats['total_generated'] += results['total_generated']
        self.generation_stats['api_calls'] += 1  # Only 1 API call now!
        
        return results
    
    def _generate_all_oneliners_optimized(self, categories: List[str], count_per_category: int, generation_date: str) -> List[Dict]:
        """Generate one-liners for all categories in a single optimized API call."""
        try:
            # Get article context for all categories
            all_articles_context = {}
            for category in categories:
                recent_articles = self.db_manager.get_articles_by_categories([category], limit=10)
                if recent_articles:
                    all_articles_context[category] = [
                        {
                            'title': article.get('title', ''),
                            'summary': article.get('ai_summary') or article.get('original_summary', '')
                        }
                        for article in recent_articles[:5]  # Use top 5 for context
                    ]
            
            # Build comprehensive prompt for all categories
            prompt = self._build_optimized_oneliner_prompt(categories, all_articles_context, count_per_category)
            
            # Single AI API call
            response = self.ai_processor.ai_manager.generate_summary(
                title="Optimized One-liner Generation for All Categories",
                content=prompt
            )
            
            if not response.success:
                logger.error(f"AI call failed: {response.error or 'Unknown error'}")
                return []
            
            # Parse the comprehensive response
            oneliners = self._parse_optimized_oneliners_response(
                response.content or '', categories, generation_date, count_per_category
            )
            
            # Validate and filter one-liners
            valid_oneliners = []
            for oneliner in oneliners:
                if self._validate_oneliner(oneliner):
                    valid_oneliners.append(oneliner)
            
            return valid_oneliners
            
        except Exception as e:
            logger.error(f"Error in optimized one-liner generation: {e}")
            return []
    
    def _generate_category_oneliners(self, category: str, count: int, generation_date: str) -> List[Dict]:
        """Generate one-liners for a specific category."""
        try:
            # Get recent articles from this category to provide context
            recent_articles = self.db_manager.get_articles_by_categories([category], limit=20)
            
            if not recent_articles:
                logger.warning(f"No recent articles found for {category}")
                return []
            
            # Build context from recent articles
            article_context = []
            for article in recent_articles[:10]:  # Use top 10 for context
                article_context.append({
                    'title': article.get('title', ''),
                    'summary': article.get('ai_summary') or article.get('original_summary', '')
                })
            
            # Create prompt for one-liner generation
            prompt = self._build_oneliner_prompt(category, article_context, count)
            
            # Call AI service
            self.generation_stats['api_calls'] += 1
            response = self.ai_processor.ai_manager.generate_summary(
                title=f"One-liner Generation for {category}",
                content=prompt
            )
            
            if not response.success:
                logger.error(f"AI call failed for {category}: {response.error or 'Unknown error'}")
                return []
            
            # Parse the response
            oneliners = self._parse_oneliners_response(response.content or '', category, generation_date)
            
            # Validate and filter one-liners
            valid_oneliners = []
            for oneliner in oneliners:
                if self._validate_oneliner(oneliner):
                    valid_oneliners.append(oneliner)
            
            return valid_oneliners[:count]  # Return only requested count
            
        except Exception as e:
            logger.error(f"Error generating one-liners for {category}: {e}")
            return []
    
    def _build_oneliner_prompt(self, category: str, article_context: List[Dict], count: int) -> str:
        """Build prompt for AI one-liner generation."""
        context_text = "\n".join([
            f"- {article['title']}: {article['summary'][:200]}..."
            for article in article_context
        ])
        
        return f"""Generate {count} engaging, insightful one-liner headlines for the "{category}" category.

Recent articles in this category:
{context_text}

Requirements:
1. Each one-liner should be 60-120 characters
2. Should capture trending themes or interesting insights from {category}
3. Use active voice and engaging language
4. Avoid clickbait, be informative yet captivating
5. Each should be unique and distinct
6. Focus on what's happening NOW in {category}

Format your response as a JSON array of strings:
["One-liner 1", "One-liner 2", "One-liner 3", ...]

Generate exactly {count} one-liners:"""
    
    def _build_optimized_oneliner_prompt(self, categories: List[str], all_articles_context: Dict[str, List[Dict]], count_per_category: int) -> str:
        """Build comprehensive prompt for generating one-liners for all categories at once."""
        
        # Build context for all categories
        category_contexts = []
        for category in categories:
            articles = all_articles_context.get(category, [])
            if articles:
                context_text = "\n".join([
                    f"- {article['title']}: {article['summary'][:150]}..."
                    for article in articles
                ])
                category_contexts.append(f"""
### {category}
Recent articles:
{context_text}""")
        
        categories_text = "\n".join(category_contexts)
        total_oneliners = len(categories) * count_per_category
        
        return f"""Generate {count_per_category} one-liner headlines for each category. Return ONLY JSON, no other text.

{categories_text}

RULES:
- 60-120 characters each
- Based on the articles provided
- Active voice, engaging but informative
- Current trends focus

RETURN THIS EXACT FORMAT:
{{
  "Science & Discovery": [
    "Scientists achieve quantum computing breakthrough",
    "Gene therapy shows promise for rare diseases"
  ],
  "Technology & Gadgets": [
    "AI transforms software development workflows", 
    "New chip design promises faster processing"
  ]
}}

Generate {count_per_category} headlines per category. JSON ONLY."""
    
    def _parse_optimized_oneliners_response(self, response_content: str, categories: List[str], generation_date: str, count_per_category: int = 10) -> List[Dict]:
        """Parse AI response with one-liners for all categories."""
        oneliners = []
        
        try:
            # Clean up the response content
            content = response_content.strip()
            
            # Remove any markdown code block markers
            if content.startswith('```json'):
                content = content[7:]
            if content.startswith('```'):
                content = content[3:]
            if content.endswith('```'):
                content = content[:-3]
            
            content = content.strip()
            
            # Try to parse as JSON
            parsed_data = json.loads(content)
            
            if isinstance(parsed_data, dict):
                # Process each category
                for category in categories:
                    category_oneliners = parsed_data.get(category, [])
                    
                    if isinstance(category_oneliners, list):
                        for oneliner_text in category_oneliners:
                            if isinstance(oneliner_text, str) and len(oneliner_text.strip()) > 20:
                                oneliners.append({
                                    'category': category,
                                    'oneliner': oneliner_text.strip(),
                                    'generation_date': generation_date,
                                    'generation_model': self.ai_processor.ai_manager.get_current_provider()
                                })
                
                logger.info(f"Successfully parsed {len(oneliners)} one-liners from optimized response")
                return oneliners
                
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            
        # Fallback: try to extract one-liners from text format
        logger.info("Attempting fallback parsing for non-JSON response")
        return self._parse_fallback_response(response_content, categories, generation_date, count_per_category)
    
    def _parse_fallback_response(self, response_content: str, categories: List[str], generation_date: str, count_per_category: int = 10) -> List[Dict]:
        """Fallback parser for non-JSON responses with intelligent content detection."""
        oneliners = []
        lines = response_content.strip().split('\n')
        current_category = None
        
        # If the response looks like it's explaining instead of generating, try to extract intent
        if ("outlines" in response_content.lower() or 
            "provided text" in response_content.lower() or
            "instructs" in response_content.lower() or
            "task for generating" in response_content.lower() or
            "generate" in response_content.lower()):
            logger.warning("AI provided explanatory response instead of one-liners. Attempting to generate fallback content.")
            
            # Generate some fallback one-liners based on categories
            fallback_oneliners = {
                'Technology & Gadgets': [
                    "AI transforms software development with breakthrough automation",
                    "Quantum computing achieves new processing milestones",
                    "Smart devices revolutionize home automation systems"
                ],
                'Science & Discovery': [
                    "Scientists uncover new species in deep ocean exploration",
                    "Gene therapy breakthrough offers hope for rare diseases",
                    "Space research reveals surprising planetary discoveries"
                ],
                'Health & Wellness': [
                    "New study reveals benefits of personalized medicine",
                    "Mental health apps show promising clinical results",
                    "Nutrition research challenges conventional diet wisdom"
                ],
                'Business & Finance': [
                    "Cryptocurrency markets adapt to regulatory changes",
                    "AI startups attract record venture capital funding",
                    "Remote work trends reshape corporate real estate"
                ],
                'Global Affairs': [
                    "International climate agreements reach new commitments",
                    "Trade partnerships evolve amid global uncertainties",
                    "Diplomatic efforts address emerging security challenges"
                ],
                'Environment & Climate': [
                    "Renewable energy adoption accelerates globally",
                    "Climate research reveals concerning ocean changes",
                    "Green technology innovations reduce carbon footprints"
                ],
                'Good Vibes (Positive News)': [
                    "Community initiatives demonstrate remarkable human kindness",
                    "Conservation efforts successfully restore endangered species",
                    "Local heroes make extraordinary differences in lives"
                ],
                'Pop Culture & Lifestyle': [
                    "Entertainment industry embraces diverse storytelling",
                    "Fashion trends reflect sustainability consciousness",
                    "Social media platforms introduce wellness features"
                ],
                'For Young Minds (Youth-Focused)': [
                    "Educational technology enhances student learning experiences",
                    "Youth activism drives meaningful social change",
                    "Creative programs inspire next generation innovators"
                ],
                'DIY, Skills & How-To': [
                    "Online tutorials democratize skill-building opportunities",
                    "Maker movement encourages practical creativity",
                    "Home improvement projects gain popularity nationwide"
                ]
            }
            
            for category in categories:
                if category in fallback_oneliners:
                    # Get the requested number of one-liners per category
                    available_oneliners = fallback_oneliners[category]
                    
                    for i in range(count_per_category):
                        oneliner_text = available_oneliners[i % len(available_oneliners)]
                        
                        # Add variation to avoid exact duplicates
                        if i >= len(available_oneliners):
                            variations = [
                                f"{oneliner_text} continue to evolve",
                                f"{oneliner_text} show new developments", 
                                f"{oneliner_text} reach new milestones",
                                f"{oneliner_text} demonstrate innovation",
                                f"{oneliner_text} advance rapidly"
                            ]
                            oneliner_text = variations[(i - len(available_oneliners)) % len(variations)]
                        
                        oneliners.append({
                            'category': category,
                            'oneliner': oneliner_text,
                            'generation_date': generation_date,
                            'generation_model': 'fallback'
                        })
            
            logger.info(f"Generated {len(oneliners)} fallback one-liners")
            return oneliners
        
        # Try to extract category-based content from actual response
        for line in lines:
            line = line.strip()
            
            # Check if line is a category header
            for category in categories:
                if category.lower() in line.lower() and ('###' in line or '##' in line or line.endswith(':')):
                    current_category = category
                    break
            
            # Check if line looks like a one-liner
            if current_category and line and not line.startswith('#') and not line.endswith(':'):
                # Clean up the line
                for prefix in ['-', '•', '*', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '10.']:
                    if line.startswith(prefix):
                        line = line[len(prefix):].strip()
                
                line = line.strip('"').strip("'")
                
                # Validate and add
                if 20 <= len(line) <= 150 and line:
                    oneliners.append({
                        'category': current_category,
                        'oneliner': line,
                        'generation_date': generation_date,
                        'generation_model': self.ai_processor.ai_manager.get_current_provider()
                    })
        
        logger.info(f"Fallback parsing extracted {len(oneliners)} one-liners")
        return oneliners
    
    def _parse_oneliners_response(self, response_content: str, category: str, generation_date: str) -> List[Dict]:
        """Parse AI response and extract one-liners."""
        oneliners = []
        
        try:
            # Try to parse as JSON first
            if response_content.strip().startswith('['):
                parsed = json.loads(response_content)
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, str) and len(item.strip()) > 20:
                            oneliners.append({
                                'category': category,
                                'oneliner': item.strip(),
                                'generation_date': generation_date,
                                'generation_model': self.ai_processor.ai_manager.get_current_provider()
                            })
                    return oneliners
        except json.JSONDecodeError:
            pass
        
        # Fallback: parse line by line
        lines = response_content.strip().split('\n')
        for line in lines:
            line = line.strip()
            # Remove common prefixes
            for prefix in ['-', '•', '*', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '10.']:
                if line.startswith(prefix):
                    line = line[len(prefix):].strip()
            
            # Remove quotes
            line = line.strip('"').strip("'")
            
            # Validate length and content
            if 20 <= len(line) <= 150 and line:
                oneliners.append({
                    'category': category,
                    'oneliner': line,
                    'generation_date': generation_date,
                    'generation_model': self.ai_processor.ai_manager.get_current_provider()
                })
        
        return oneliners
    
    def _validate_oneliner(self, oneliner_data: Dict) -> bool:
        """Validate a one-liner entry."""
        oneliner = oneliner_data.get('oneliner', '')
        
        # Length check
        if not (20 <= len(oneliner) <= 150):
            return False
        
        # Content quality checks
        if not oneliner.strip():
            return False
        
        # Avoid generic/template-like content
        bad_phrases = [
            'this document outlines',
            'the goal is to synthesize',
            'one-liner generation',
            'based on the articles',
            'here are the one-liners'
        ]
        
        oneliner_lower = oneliner.lower()
        for phrase in bad_phrases:
            if phrase in oneliner_lower:
                return False
        
        return True
    
    def get_random_highlight(self, user_categories: List[str] = None, generation_date: str = None) -> Optional[str]:
        """Get a random one-liner for email highlight, optionally filtered by user categories."""
        if not generation_date:
            generation_date = date.today().strftime('%Y-%m-%d')
        
        # Try to get one-liner from user's preferred categories first
        if user_categories:
            for category in user_categories:
                oneliner = self.db_manager.get_random_oneliner(category, generation_date)
                if oneliner:
                    return oneliner['oneliner']
        
        # Fallback to any category for today
        oneliner = self.db_manager.get_random_oneliner(generation_date=generation_date)
        if oneliner:
            return oneliner['oneliner']
        
        # Fallback to any date if nothing for today
        oneliner = self.db_manager.get_random_oneliner()
        if oneliner:
            return oneliner['oneliner']
        
        # Ultimate fallback
        return "Stay informed with today's most important developments across technology, science, and global affairs."
    
    def cleanup_old_oneliners(self, days_to_keep: int = 7) -> int:
        """Clean up old one-liners to save space."""
        return self.db_manager.cleanup_old_oneliners(days_to_keep)
    
    def get_generation_stats(self) -> Dict:
        """Get statistics about one-liner generation."""
        db_stats = self.db_manager.get_oneliner_stats()
        return {
            'generation_stats': self.generation_stats,
            'database_stats': db_stats
        }


def generate_daily_oneliners_batch() -> Dict:
    """Utility function to generate one-liners for today."""
    service = OnelinerGenerationService()
    return service.generate_daily_oneliners()


if __name__ == "__main__":
    # Test the service
    logging.basicConfig(level=logging.INFO)
    
    service = OnelinerGenerationService()
    result = service.generate_daily_oneliners(oneliners_per_category=5)
    
    print("Generation Results:")
    print(json.dumps(result, indent=2))
    
    # Test getting random highlights
    print("\nRandom highlights:")
    for i in range(3):
        highlight = service.get_random_highlight()
        print(f"  {i+1}. {highlight}")