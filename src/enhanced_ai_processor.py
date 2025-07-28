"""Enhanced AI processor with multi-API support and improved functionality."""

import json
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime

try:
    from .database import DatabaseManager
except ImportError:
    from src.database import DatabaseManager
try:
    from .llm_router import LLMRouter
    USE_LLM_ROUTER = True
except ImportError:
    try:
        from llm_router.llm_router import LLMRouter
        USE_LLM_ROUTER = True
    except ImportError:
        from ai_adapters import AIServiceManager, create_ai_manager
        USE_LLM_ROUTER = False
try:
    from config import AI_CATEGORIES, AI_USE_BATCH_SUMMARIES, AI_SUMMARY_BATCH_SIZE
except ImportError:
    AI_CATEGORIES = ['Science & Discovery', 'Technology & Gadgets', 'Health & Wellness', 'Business & Finance', 'Global Affairs', 'Environment & Climate', 'Good Vibes (Positive News)', 'Pop Culture & Lifestyle', 'For Young Minds (Youth-Focused)', 'DIY, Skills & How-To']
    AI_USE_BATCH_SUMMARIES = True
    AI_SUMMARY_BATCH_SIZE = 5

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedAIProcessor:
    """Enhanced AI processor with multi-provider support and advanced features."""
    
    def __init__(self, ai_config: Dict[str, str] = None, db_manager: DatabaseManager = None):
        self.db_manager = db_manager or DatabaseManager()
        
        # Initialize AI manager using LLM router with ai_config.yaml
        use_llm_router = USE_LLM_ROUTER
        if use_llm_router:
            try:
                self.ai_manager = LLMRouter("ai_config.yaml")
                logger.info("Using LLM Router with ai_config.yaml provider sequence")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM Router: {e}, falling back to old system")
                use_llm_router = False
        
        if not use_llm_router:
            # Fallback to old system
            if ai_config:
                self.ai_manager = create_ai_manager(ai_config)
            else:
                # Fallback to environment variables
                import os
                fallback_config = {
                    'openai_key': os.getenv('OPENAI_API_KEY'),
                    'anthropic_key': os.getenv('ANTHROPIC_API_KEY'),
                    'google_key': os.getenv('GOOGLE_API_KEY'),
                }
                self.ai_manager = create_ai_manager(fallback_config)
        
        self.processing_stats = {
            'classified': 0,
            'summarized': 0,
            'trends_detected': 0,
            'errors': 0,
            'api_calls': 0,
            'total_cost': 0.0
        }
        
        # Store whether we're using the new LLM router
        self.using_llm_router = use_llm_router and isinstance(self.ai_manager, LLMRouter)
    
    def _query_ai(self, prompt: str, operation_type: str = "general") -> str:
        """Unified method to query AI using either LLM router or old system."""
        try:
            if self.using_llm_router:
                return self.ai_manager.query(prompt)
            else:
                # Old system - use appropriate method based on operation type
                if operation_type == "classify":
                    return self.ai_manager.classify_article("", prompt)  # Hack for old interface
                elif operation_type == "summarize":
                    return self.ai_manager.generate_summary("", prompt)  # Hack for old interface
                else:
                    # Fallback to summary method
                    return self.ai_manager.generate_summary("", prompt)
        except Exception as e:
            logger.error(f"AI query failed for {operation_type}: {e}")
            raise
    
    def classify_article_enhanced(self, title: str, summary: str, existing_categories: List[str] = None) -> List[str]:
        """Enhanced article classification with validation and fallbacks."""
        # If already classified and confidence is high, skip re-classification
        if existing_categories and len(existing_categories) > 0:
            # Validate existing categories
            valid_existing = [cat for cat in existing_categories if cat in AI_CATEGORIES]
            if valid_existing:
                logger.debug(f"Using existing categories: {valid_existing}")
                return valid_existing
        
        # Use AI service
        try:
            if self.using_llm_router:
                # Use LLM router with proper prompt
                classification_prompt = f"""Classify this news article into relevant categories from this list: {AI_CATEGORIES}

Title: {title}
Summary: {summary}

Return only a JSON array of the most relevant category names from the list above. Maximum 3 categories. Example: ["Science & Discovery", "Technology & Gadgets"]"""
                
                response_text = self._query_ai(classification_prompt, "classify")
                
                # Validate response before parsing
                if not isinstance(response_text, str):
                    logger.warning(f"AI classification returned non-string response: {type(response_text)} - {response_text}")
                    raise ValueError(f"Non-string response: {type(response_text)}")
                
                # Additional validation for boolean responses
                if isinstance(response_text, bool):
                    logger.warning(f"AI classification returned boolean instead of JSON: {response_text}")
                    raise ValueError("Boolean response instead of JSON string")
                
                # Try to parse JSON with error handling
                try:
                    categories = json.loads(response_text)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse classification JSON: {response_text[:100]}... Error: {e}")
                    raise ValueError(f"Invalid JSON in classification response: {e}")
                
                # Validate that categories is a list
                if not isinstance(categories, list):
                    logger.warning(f"AI classification returned non-list: {type(categories)} - {categories}")
                    raise ValueError(f"Expected list, got {type(categories)}")
                
                # Validate list contents
                valid_categories = [cat for cat in categories if isinstance(cat, str) and cat in AI_CATEGORIES]
                if not valid_categories:
                    logger.warning(f"No valid categories found in response: {categories}")
                    raise ValueError("No valid categories in response")
                
                categories = valid_categories
                
                self.processing_stats['classified'] += 1
                self.processing_stats['api_calls'] += 1
                logger.debug(f"Classified '{title[:50]}...' as: {categories} (via LLM Router)")
                return categories
            else:
                # Use old system
                response = self.ai_manager.classify_article(title, summary)
                self.processing_stats['api_calls'] += 1
                self.processing_stats['total_cost'] += response.cost_estimate
                
                if response.success:
                    try:
                        categories = json.loads(response.content)
                        self.processing_stats['classified'] += 1
                        logger.debug(f"Classified '{title[:50]}...' as: {categories} (via {response.provider})")
                        return categories
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid classification response: {response.content}")
        
        except Exception as e:
            logger.warning(f"AI classification failed: {e}")
        
        # Fallback: rule-based classification
        self.processing_stats['errors'] += 1
        return self._rule_based_classification(title, summary)
    
    def _rule_based_classification(self, title: str, summary: str) -> List[str]:
        """Simple rule-based classification as fallback."""
        text = f"{title} {summary}".lower()
        
        # Define comprehensive keywords for each category
        category_keywords = {
            "Technology & Gadgets": ["tech", "ai", "artificial intelligence", "software", "app", "digital", "computer", "smartphone", "gadget", "internet", "cyber", "data", "algorithm", "coding", "programming", "blockchain", "robotics", "virtual reality", "machine learning"],
            "Science & Discovery": ["research", "study", "scientist", "discovery", "experiment", "science", "laboratory", "analysis", "breakthrough", "innovation", "findings", "academic", "peer-reviewed", "methodology", "hypothesis", "astronomy", "physics", "chemistry", "biology"],
            "Health & Wellness": ["health", "medical", "doctor", "treatment", "disease", "wellness", "fitness", "medicine", "hospital", "patient", "symptom", "diagnosis", "therapy", "nutrition", "mental health", "vaccine", "virus", "bacteria", "epidemic", "pandemic"],
            "Business & Finance": ["business", "company", "market", "economy", "financial", "investment", "stock", "corporate", "earnings", "profit", "revenue", "ceo", "startup", "industry", "trade", "commerce", "banking", "cryptocurrency", "merger", "acquisition"],
            "Global Affairs": ["government", "politics", "international", "country", "president", "policy", "diplomatic", "nation", "election", "democracy", "conflict", "war", "peace", "treaty", "sanctions", "embassy", "foreign", "minister", "parliament", "congress"],
            "Environment & Climate": ["climate", "environment", "green", "carbon", "pollution", "sustainable", "renewable", "energy", "solar", "wind", "emissions", "global warming", "conservation", "biodiversity", "ecosystem", "recycling", "ocean", "forest", "wildlife", "earth"],
            "Good Vibes (Positive News)": ["celebration", "achievement", "success", "award", "positive", "help", "rescue", "hero", "kindness", "charity", "volunteer", "donation", "milestone", "record", "victory", "accomplish", "inspire", "uplifting", "heartwarming", "triumph"],
            "Pop Culture & Lifestyle": ["celebrity", "movie", "music", "fashion", "lifestyle", "culture", "entertainment", "film", "tv", "television", "actor", "actress", "singer", "album", "concert", "festival", "style", "trend", "art", "theater"],
            "For Young Minds (Youth-Focused)": ["education", "student", "school", "learning", "kids", "children", "teenager", "youth", "university", "college", "academic", "classroom", "teacher", "curriculum", "scholarship", "graduation", "skills", "training", "development"],
            "DIY, Skills & How-To": ["tutorial", "how to", "diy", "guide", "tips", "skill", "craft", "build", "make", "create", "step", "instruction", "repair", "fix", "project", "handmade", "workshop", "technique", "method", "practice"]
        }
        
        # Score each category based on keyword matches
        category_scores = {}
        for category, keywords in category_keywords.items():
            score = sum(2 if keyword in title.lower() else 1 for keyword in keywords if keyword in text)
            if score > 0:
                category_scores[category] = score
        
        # Sort categories by score and take top 2
        if category_scores:
            sorted_categories = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
            result = [cat for cat, score in sorted_categories[:2]]
        else:
            result = ["Technology & Gadgets"]  # Default fallback
        
        logger.info(f"Rule-based classification: {result} (scores: {category_scores})")
        return result
    
    def generate_summary_enhanced(self, title: str, original_summary: str, 
                                existing_summary: str = None, force_resummarize: bool = False) -> str:
        """Enhanced summary generation with quality checks and fallbacks."""
        if existing_summary and not force_resummarize:
            return existing_summary
        
        # Use AI service
        response = self.ai_manager.generate_summary(title, original_summary)
        self.processing_stats['api_calls'] += 1
        self.processing_stats['total_cost'] += response.cost_estimate
        
        if response.success and len(response.content) > 20:
            self.processing_stats['summarized'] += 1
            logger.debug(f"Summarized '{title[:50]}...' (via {response.provider})")
            return response.content
        
        # Fallback
        self.processing_stats['errors'] += 1
        return self._fallback_summary(title, original_summary)

    def _fallback_summary(self, title: str, original_summary: str) -> str:
        """Create fallback summary when AI fails."""
        if not original_summary:
            return f"News about {title[:100]}..."
        
        # Clean and truncate original summary
        import re
        cleaned = re.sub(r'<[^>]+>', '', original_summary)  # Remove HTML
        cleaned = re.sub(r'\\s+', ' ', cleaned).strip()  # Normalize whitespace
        
        # Truncate to reasonable length
        if len(cleaned) > 200:
            cleaned = cleaned[:197] + "..."
        
        return cleaned
    
    def detect_trends_enhanced(self, articles: List[Dict], min_articles: int = 5) -> Dict[str, List[str]]:
        """Enhanced trend detection with better filtering and validation."""
        if len(articles) < min_articles:
            logger.info(f"Not enough articles ({len(articles)}) for trend detection")
            return {}
        
        # Filter and prepare articles
        trend_articles = []
        for article in articles[:25]:  # Limit for API efficiency
            if article.get('title') and article.get('original_summary'):
                trend_articles.append(article)
        
        if len(trend_articles) < min_articles:
            return {}
        
        # Use AI service
        try:
            response = self.ai_manager.detect_trends(trend_articles)
            self.processing_stats['api_calls'] += 1
            self.processing_stats['total_cost'] += response.cost_estimate
        except Exception as e:
            logger.error(f"Trend detection API call failed: {e}")
            self.processing_stats['errors'] += 1
            return self._simple_trend_detection(trend_articles)
        
        if response.success:
            try:
                # Validate response before parsing
                if not isinstance(response.content, str):
                    logger.warning(f"Trend detection returned non-string response: {type(response.content)} - {response.content}")
                    raise ValueError(f"Non-string response: {type(response.content)}")
                
                # Additional validation for boolean responses
                if isinstance(response.content, bool):
                    logger.warning(f"Trend detection returned boolean instead of JSON: {response.content}")
                    raise ValueError("Boolean response instead of JSON string")
                
                trends = json.loads(response.content)
                if isinstance(trends, dict) and trends:
                    # Validate and filter trends
                    validated_trends = self._validate_trends(trends)
                    if validated_trends:
                        self.processing_stats['trends_detected'] += sum(len(v) for v in validated_trends.values())
                        logger.info(f"Detected {len(validated_trends)} trending topics (via {response.provider})")
                        return validated_trends
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                logger.warning(f"Invalid trends response (type: {type(response.content)}, content: {repr(response.content)[:100]}...): {e}")
        
        # Fallback: simple keyword-based trend detection
        logger.info("Using fallback trend detection")
        self.processing_stats['errors'] += 1
        return self._simple_trend_detection(trend_articles)
    
    def _validate_trends(self, trends: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Validate and clean trend detection results."""
        validated = {}
        
        for category, topics in trends.items():
            # Validate category
            if category not in AI_CATEGORIES:
                continue
            
            # Clean and validate topics
            clean_topics = []
            for topic in topics:
                if isinstance(topic, str) and len(topic.strip()) > 3:
                    clean_topics.append(topic.strip()[:100])  # Limit length
            
            if clean_topics:
                validated[category] = clean_topics[:5]  # Limit topics per category
        
        return validated
    
    def _simple_trend_detection(self, articles: List[Dict]) -> Dict[str, List[str]]:
        """Simple keyword-based trend detection as fallback."""
        from collections import Counter
        import re
        
        # Extract keywords from titles
        all_words = []
        for article in articles:
            title = article.get('title', '')
            # Extract meaningful words (3+ chars, not common words)
            words = re.findall(r'\\b[A-Za-z]{3,}\\b', title.lower())
            filtered_words = [w for w in words if w not in {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'her', 'was', 'one', 'our', 'had', 'but', 'day', 'get', 'use', 'man', 'new', 'now', 'way', 'may', 'say'}]
            all_words.extend(filtered_words)
        
        # Find most common words (potential trends)
        word_counts = Counter(all_words)
        common_words = [word for word, count in word_counts.most_common(10) if count >= 3]
        
        if common_words:
            return {AI_CATEGORIES[0]: common_words[:5]}  # Return under first category
        
        return {}
    
    def process_article_batch_enhanced(self, articles: List[Dict], 
                                  force_reprocess: bool = False) -> Tuple[List[Dict], Dict[str, int]]:
        """Enhanced batch processing with better error handling and statistics."""
        logger.info(f"Enhanced processing of {len(articles)} articles")
        
        processed_articles = []
        processing_stats = {'processed': 0, 'skipped': 0, 'errors': 0}
        
        for i, article in enumerate(articles):
            try:
                # Progress logging
                if (i + 1) % 10 == 0:
                    logger.info(f"Processing article {i+1}/{len(articles)}")
                
                title = article.get('title', '')
                original_summary = article.get('original_summary', '')
                
                # Skip articles without sufficient content
                if not title or len(title.strip()) < 5:
                    logger.debug(f"Skipping article with insufficient title: {title}")
                    processing_stats['skipped'] += 1
                    continue
                
                # Check if already processed (unless forcing reprocess)
                has_ai_data = article.get('ai_categories') and article.get('ai_summary')
                if has_ai_data and not force_reprocess:
                    processed_articles.append(article)
                    processing_stats['skipped'] += 1
                    continue
                
                # Process with AI
                existing_categories = article.get('ai_categories', [])
                ai_categories = self.classify_article_enhanced(
                    title, original_summary, existing_categories
                )
                
                existing_summary = article.get('ai_summary')
                ai_summary = self.generate_summary_enhanced(
                    title, original_summary, existing_summary, force_reprocess
                )
                
                # Update article
                article['ai_categories'] = ai_categories
                article['ai_summary'] = ai_summary
                article['date_processed'] = datetime.utcnow().isoformat()
                
                processed_articles.append(article)
                processing_stats['processed'] += 1
            
            except Exception as e:
                logger.error(f"Error processing article {article.get('id')}: {e}")
                processing_stats['errors'] += 1
        
        return processed_articles, processing_stats
    
    def process_article_batch_with_batch_summaries(self, articles: List[Dict], 
                                                 force_reprocess: bool = False, 
                                                 batch_size: int = 8) -> Tuple[List[Dict], Dict[str, int]]:
        """Enhanced batch processing using AI batch summarization to reduce API costs."""
        logger.info(f"Enhanced batch processing of {len(articles)} articles with batch summaries (batch_size={batch_size})")
        
        processed_articles = []
        processing_stats = {'processed': 0, 'skipped': 0, 'errors': 0, 'batch_calls': 0}
        
        # First pass: classify articles individually (classification is fast and needs to be precise)
        articles_needing_summary = []
        for i, article in enumerate(articles):
            try:
                title = article.get('title', '')
                original_summary = article.get('original_summary', '')
                
                # Skip articles without sufficient content
                if not title or len(title.strip()) < 5:
                    logger.debug(f"Skipping article with insufficient title: {title}")
                    processing_stats['skipped'] += 1
                    continue
                
                # Check if already processed (unless forcing reprocess)
                has_ai_data = article.get('ai_categories') and article.get('ai_summary')
                if has_ai_data and not force_reprocess:
                    processed_articles.append(article)
                    processing_stats['skipped'] += 1
                    continue
                
                # Classify article
                existing_categories = article.get('ai_categories', [])
                ai_categories = self.classify_article_enhanced(
                    title, original_summary, existing_categories
                )
                article['ai_categories'] = ai_categories
                
                # Add to batch for summarization if needed
                existing_summary = article.get('ai_summary')
                if not existing_summary or force_reprocess:
                    articles_needing_summary.append(article)
                else:
                    article['date_processed'] = datetime.utcnow().isoformat()
                    processed_articles.append(article)
                    processing_stats['processed'] += 1
                    
            except Exception as e:
                logger.error(f"Error preprocessing article {article.get('id')}: {e}")
                processing_stats['errors'] += 1
        
        # Second pass: batch summarization
        if articles_needing_summary:
            logger.info(f"Processing {len(articles_needing_summary)} articles with batch summarization")
            
            # Process in batches
            for batch_start in range(0, len(articles_needing_summary), batch_size):
                batch_end = min(batch_start + batch_size, len(articles_needing_summary))
                batch_articles = articles_needing_summary[batch_start:batch_end]
                
                try:
                    logger.info(f"Processing batch {batch_start//batch_size + 1}: articles {batch_start+1}-{batch_end}")
                    
                    # Get batch summaries
                    response = self.ai_manager.generate_batch_summaries(batch_articles)
                    processing_stats['batch_calls'] += 1
                    self.processing_stats['api_calls'] += 1
                    self.processing_stats['total_cost'] += response.cost_estimate
                    
                    if response.success:
                        try:
                            # Debug: check the type and value of response.content
                            logger.debug(f"Batch response content type: {type(response.content)}, value: {response.content}")
                            
                            # Ensure response.content is a string before parsing
                            if isinstance(response.content, bool):
                                logger.error(f"Batch {batch_start//batch_size + 1}: Received boolean response content: {response.content}, falling back to individual processing")
                                raise json.JSONDecodeError("Response content is boolean, not JSON string", "", 0)
                            elif not isinstance(response.content, str):
                                logger.error(f"Batch {batch_start//batch_size + 1}: Received non-string response content: {type(response.content)}, falling back to individual processing")
                                raise json.JSONDecodeError("Response content is not a string", "", 0)
                            
                            summaries = json.loads(response.content)
                            
                            # Validate that summaries is a list
                            if not isinstance(summaries, list):
                                logger.error(f"Expected list of summaries, got {type(summaries)}: {summaries}")
                                raise json.JSONDecodeError("Response is not a JSON array", "", 0)
                            
                            # Apply summaries to articles
                            for i, article in enumerate(batch_articles):
                                if i < len(summaries):
                                    article['ai_summary'] = summaries[i]
                                    self.processing_stats['summarized'] += 1
                                else:
                                    # Fallback for missing summaries
                                    article['ai_summary'] = self._fallback_summary(
                                        article.get('title', ''), 
                                        article.get('original_summary', '')
                                    )
                                    self.processing_stats['errors'] += 1
                                
                                article['date_processed'] = datetime.utcnow().isoformat()
                                processed_articles.append(article)
                                processing_stats['processed'] += 1
                                
                            logger.info(f"Batch processed successfully: {len(summaries)} summaries generated (via {response.provider})")
                            
                        except (json.JSONDecodeError, TypeError, ValueError) as e:
                            logger.error(f"Batch {batch_start//batch_size + 1}: Failed to parse batch summary response (content type: {type(response.content)}, content: {repr(response.content)[:200]}...): {e}, falling back to individual processing")
                            # Fallback to individual processing for this batch
                            for article in batch_articles:
                                try:
                                    ai_summary = self.generate_summary_enhanced(
                                        article.get('title', ''), 
                                        article.get('original_summary', ''), 
                                        force_resummarize=True
                                    )
                                    article['ai_summary'] = ai_summary
                                    article['date_processed'] = datetime.utcnow().isoformat()
                                    processed_articles.append(article)
                                    processing_stats['processed'] += 1
                                except Exception as e:
                                    logger.error(f"Individual fallback failed for article {article.get('id')}: {e}")
                                    processing_stats['errors'] += 1
                    else:
                        logger.error(f"Batch summarization failed: {response.error}, falling back to individual processing")
                        # Fallback to individual processing
                        for article in batch_articles:
                            try:
                                ai_summary = self.generate_summary_enhanced(
                                    article.get('title', ''), 
                                    article.get('original_summary', ''), 
                                    force_resummarize=True
                                )
                                article['ai_summary'] = ai_summary
                                article['date_processed'] = datetime.utcnow().isoformat()
                                processed_articles.append(article)
                                processing_stats['processed'] += 1
                            except Exception as e:
                                logger.error(f"Individual fallback failed for article {article.get('id')}: {e}")
                                processing_stats['errors'] += 1
                                
                except Exception as e:
                    logger.error(f"Batch processing failed for batch {batch_start//batch_size + 1}: {e}")
                    # Fallback to individual processing for this batch
                    for article in batch_articles:
                        try:
                            ai_summary = self.generate_summary_enhanced(
                                article.get('title', ''), 
                                article.get('original_summary', ''), 
                                force_resummarize=True
                            )
                            article['ai_summary'] = ai_summary
                            article['date_processed'] = datetime.utcnow().isoformat()
                            processed_articles.append(article)
                            processing_stats['processed'] += 1
                        except Exception as fallback_e:
                            logger.error(f"Individual fallback failed for article {article.get('id')}: {fallback_e}")
                            # Use basic fallback summary
                            article['ai_summary'] = self._fallback_summary(
                                article.get('title', ''), 
                                article.get('original_summary', '')
                            )
                            article['date_processed'] = datetime.utcnow().isoformat()
                            processed_articles.append(article)
                            processing_stats['processed'] += 1
                            processing_stats['errors'] += 1
        
        logger.info(f"Batch processing complete: {processing_stats['processed']} processed, {processing_stats['batch_calls']} batch API calls")
        return processed_articles, processing_stats

    def run_enhanced_processing_cycle(self, batch_size: int = 50, 
                                    force_reprocess: bool = False,
                                    use_batch_summaries: bool = None,
                                    summary_batch_size: int = None) -> Dict[str, int]:
        """Run complete enhanced AI processing cycle."""
        logger.info("Starting enhanced AI processing cycle")
        
        # Use configuration defaults if not specified
        if use_batch_summaries is None:
            use_batch_summaries = AI_USE_BATCH_SUMMARIES
        if summary_batch_size is None:
            summary_batch_size = AI_SUMMARY_BATCH_SIZE
        
        # Get articles to process
        import sqlite3
        with sqlite3.connect(self.db_manager.db_path) as conn:
            cursor = conn.cursor()
            
            if force_reprocess:
                query = '''
                    SELECT id, title, original_summary, ai_categories, ai_summary
                    FROM articles 
                    WHERE original_summary IS NOT NULL
                    ORDER BY date_collected DESC
                    LIMIT ?
                '''
            else:
                query = '''
                    SELECT id, title, original_summary, ai_categories, ai_summary
                    FROM articles 
                    WHERE (ai_categories IS NULL OR ai_summary IS NULL)
                    AND original_summary IS NOT NULL
                    ORDER BY date_collected DESC
                    LIMIT ?
                '''
            
            cursor.execute(query, (batch_size,))
            rows = cursor.fetchall()
        
        if not rows:
            logger.info("No articles to process")
            return {'processed': 0, 'updated': 0, 'trends': 0, 'trending_articles': 0}
        
        # Convert to article dicts
        articles = []
        for row in rows:
            articles.append({
                'id': row[0],
                'title': row[1],
                'original_summary': row[2],
                'ai_categories': json.loads(row[3]) if row[3] else None,
                'ai_summary': row[4]
            })
        
        # Process with enhanced AI
        if use_batch_summaries:
            logger.info(f"Using batch summarization with batch size: {summary_batch_size}")
            processed_articles, process_stats = self.process_article_batch_with_batch_summaries(
                articles, force_reprocess, summary_batch_size
            )
        else:
            logger.info("Using individual article processing")
            processed_articles, process_stats = self.process_article_batch_enhanced(
                articles, force_reprocess
            )
        
        # Update database
        updated_count = self.db_manager.update_articles_bulk(processed_articles)
        
        # Detect trends
        trending_topics = self.detect_trends_enhanced(processed_articles)
        trending_articles_count = self._update_trending_flags(trending_topics)
        
        # Consolidate stats
        final_stats = {
            'processed': process_stats['processed'],
            'updated': updated_count,
            'trends': len(trending_topics),
            'trending_articles': trending_articles_count,
            'api_calls': self.processing_stats['api_calls'],
            'total_cost': self.processing_stats['total_cost']
        }
        
        logger.info(f"Enhanced processing cycle complete: {final_stats}")
        return final_stats
    
    def _update_trending_flags(self, trending_topics: Dict[str, List[str]]) -> int:
        """Update trending flags in database."""
        if not trending_topics:
            return 0
        
        updated_count = 0
        
        import sqlite3
        with sqlite3.connect(self.db_manager.db_path) as conn:
            cursor = conn.cursor()
            
            # Reset trending flags
            cursor.execute("UPDATE articles SET trending_flag = 0")
            
            # Mark trending articles
            for category, topics in trending_topics.items():
                for topic in topics:
                    cursor.execute('''
                        UPDATE articles 
                        SET trending_flag = 1 
                        WHERE (LOWER(title) LIKE ? OR LOWER(ai_summary) LIKE ?) 
                        AND ai_categories LIKE ?
                    ''', (f'%{topic.lower()}%', f'%{topic.lower()}%', f'%{category}%'))
                    
                    updated_count += cursor.rowcount
            
            conn.commit()
        
        logger.info(f"Updated trending flags for {updated_count} articles")
        return updated_count
    
    def get_processing_stats(self) -> Dict:
        """Get comprehensive processing statistics."""
        ai_stats = self.ai_manager.get_usage_stats()
        
        return {
            'processing_stats': self.processing_stats,
            'ai_service_stats': ai_stats,
            'available_adapters': self.ai_manager.get_available_adapters()
        }


def main():
    """Run enhanced AI processing."""
    import os
    
    # Configuration
    ai_config = {
        'openai_key': os.getenv('OPENAI_API_KEY'),
        'anthropic_key': os.getenv('ANTHROPIC_API_KEY'),
        'google_key': os.getenv('GOOGLE_API_KEY')
    }
    
    try:
        processor = EnhancedAIProcessor(ai_config)
        stats = processor.run_enhanced_processing_cycle()
        
        print("\n" + "="*60)
        print("ENHANCED AI PROCESSING RESULTS")
        print("="*60)
        print(f"Articles processed: {stats['processed']}")
        print(f"Database updates: {stats['updated']}")
        print(f"Trends detected: {stats['trends']}")
        print(f"Trending articles: {stats['trending_articles']}")
        print(f"API calls made:. {stats['api_calls']}")
        print(f"Estimated cost: ${stats['total_cost']:.4f}")
        print("="*60)
        
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure you have at least one AI API key configured")


if __name__ == "__main__":
    main()
