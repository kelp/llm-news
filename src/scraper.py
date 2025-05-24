"""
Scraper module for extracting articles from Anthropic's website.
"""
import json
import logging
import os
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
import random

import requests
from bs4 import BeautifulSoup

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class AnthropicScraper:
    """Scraper for Anthropic's news and research pages."""
    
    NEWS_URL = "https://www.anthropic.com/news"
    RESEARCH_URL = "https://www.anthropic.com/research"
    
    def __init__(self, cache_dir: str = "data", http_cache_filename: str = "http_cache.json"):
        """Initialize the scraper with cache directory and optional HTTP cache filename."""
        self.cache_dir = cache_dir
        self.http_cache_file = os.path.join(cache_dir, http_cache_filename)
        self.articles_cache_file = os.path.join(cache_dir, "anthropic_articles.json")
        self.http_cache = self._load_http_cache()
        os.makedirs(cache_dir, exist_ok=True)
    
    def _load_http_cache(self) -> Dict[str, Dict[str, Any]]:
        """Load HTTP cache from file."""
        if os.path.exists(self.http_cache_file):
            try:
                with open(self.http_cache_file, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                logger.info(f"Loaded HTTP cache with {len(cache)} entries")
                return cache
            except (IOError, json.JSONDecodeError) as e:
                logger.error(f"Error loading HTTP cache: {e}")
        return {}
    
    def _save_http_cache(self) -> None:
        """Save HTTP cache to file."""
        try:
            with open(self.http_cache_file, "w", encoding="utf-8") as f:
                json.dump(self.http_cache, f, indent=2)
            logger.info(f"Saved HTTP cache with {len(self.http_cache)} entries")
        except IOError as e:
            logger.error(f"Error saving HTTP cache: {e}")
            
    def fetch_page(self, url: str, check_modified: bool = True) -> Tuple[Optional[str], bool, Dict]:
        """
        Fetch HTML content from a URL with conditional request support.
        
        Args:
            url: The URL to fetch
            check_modified: Whether to use conditional requests (If-Modified-Since, If-None-Match)
            
        Returns:
            Tuple of (html_content, is_modified, response_metadata)
            - html_content: The HTML content (None if not modified or error)
            - is_modified: Whether the content has been modified since last fetch
            - response_metadata: Dictionary with ETag, Last-Modified, and other metadata
        """
        # Initialize headers with user agent
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; LLM-News/1.0; +https://github.com/kelp/llm-news)"
        }
        
        # Add conditional headers if we have cached metadata and check_modified is True
        url_cache = self.http_cache.get(url, {})
        
        if check_modified and url_cache:
            if "etag" in url_cache:
                headers["If-None-Match"] = url_cache["etag"]
            if "last_modified" in url_cache:
                headers["If-Modified-Since"] = url_cache["last_modified"]
        
        try:
            # First try a HEAD request to check if content has changed
            if check_modified and url_cache:
                try:
                    head_response = requests.head(url, headers=headers, timeout=10)
                    if head_response.status_code == 304:
                        logger.info(f"Content not modified for {url} (HEAD check)")
                        # Update last_checked timestamp
                        url_cache["last_checked"] = time.time()
                        self.http_cache[url] = url_cache
                        self._save_http_cache()
                        return None, False, url_cache
                except requests.RequestException as e:
                    logger.warning(f"HEAD request failed for {url}, falling back to GET: {e}")
            
            # Perform the GET request
            response = requests.get(url, headers=headers, timeout=30)
            
            # Handle 304 Not Modified
            if response.status_code == 304:
                logger.info(f"Content not modified for {url}")
                # Update last_checked timestamp
                url_cache["last_checked"] = time.time()
                self.http_cache[url] = url_cache
                self._save_http_cache()
                return None, False, url_cache
            
            # Handle successful response
            response.raise_for_status()
            
            # Extract and store response metadata
            metadata = {
                "last_checked": time.time(),
                "last_modified_check": time.time()
            }
            
            if "ETag" in response.headers:
                metadata["etag"] = response.headers["ETag"]
            
            if "Last-Modified" in response.headers:
                metadata["last_modified"] = response.headers["Last-Modified"]
            
            # If there's a Date header, store it
            if "Date" in response.headers:
                metadata["date"] = response.headers["Date"]
            
            # If there's a Content-Length header, store it
            if "Content-Length" in response.headers:
                metadata["content_length"] = response.headers["Content-Length"]
            
            # Update cache with new metadata
            self.http_cache[url] = metadata
            self._save_http_cache()
            
            return response.text, True, metadata
            
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return None, False, {}
    
    def extract_date_from_content(self, content, url_path=None):
        """
        Extract date information from content using multiple approaches.
        Returns a date string in ISO format.
        """
        # 1. Check for explicit time elements
        soup = BeautifulSoup(content, 'lxml') if isinstance(content, str) else content
        date_element = soup.select_one('time')
        
        # Found time element with datetime attribute
        if date_element and date_element.has_attr('datetime'):
            logger.info(f"Found date from datetime attribute: {date_element['datetime']}")
            return self._parse_date(date_element['datetime'])
            
        # Time element without datetime attribute
        if date_element:
            date_text = date_element.get_text(strip=True)
            logger.info(f"Found date from time element text: {date_text}")
            return self._parse_date(date_text)
        
        # 2. Look for text patterns that look like dates
        content_text = soup.get_text() if isinstance(soup, BeautifulSoup) else str(content)
        
        # Common date patterns
        date_patterns = [
            # Full ISO dates: 2023-01-15
            r'\b(\d{4}-\d{2}-\d{2})\b',
            # Month name formats: January 15, 2023 or Jan 15, 2023
            r'\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+20\d\d\b',
            # Day-first formats: 15 January 2023
            r'\b\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+20\d\d\b'
        ]
        
        for pattern in date_patterns:
            date_match = re.search(pattern, content_text)
            if date_match:
                logger.info(f"Found date from text pattern: {date_match.group(0)}")
                return self._parse_date(date_match.group(0))
        
        # 3. Try to extract from URL path if provided
        if url_path:
            # Check for patterns like /2023/01/ in the URL
            year_month_match = re.search(r'/(\d{4})/(\d{2})/', url_path)
            if year_month_match:
                year, month = year_month_match.groups()
                date_str = f"{year}-{month}-15"  # Assume middle of month
                logger.info(f"Found date from URL path: {date_str}")
                return self._parse_date(date_str)
            
            # Check for just year in URL
            year_match = re.search(r'/(\d{4})/', url_path)
            if year_match:
                year = year_match.group(1)
                date_str = f"{year}-06-15"  # Assume middle of year
                logger.info(f"Found year from URL path: {date_str}")
                return self._parse_date(date_str)
        
        # 4. Use intelligent estimation based on URL keywords
        if url_path:
            estimated_date = self.estimate_publication_date(url_path)
            logger.info(f"Using estimated date based on URL patterns: {estimated_date}")
            return estimated_date
            
        # 5. Final fallback - use a reasonable default (1 year ago)
        one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
        logger.warning("No date found, using default (1 year ago)")
        return one_year_ago.isoformat()
    
    def estimate_publication_date(self, url_path):
        """
        Estimate a publication date based on the URL path.
        Uses known product releases and terminology to make educated guesses.
        """
        # Extract year from URL if present (YYYY format)
        year_match = re.search(r'/(20\d\d)/', url_path)
        if year_match:
            year = int(year_match.group(1))
            # Random month and day in that year
            month = random.randint(1, 12)
            day = random.randint(1, 28)
            # Set to noon UTC
            return datetime(year, month, day, 12, 0, 0, tzinfo=timezone.utc).isoformat()
        
        # Check for specific keywords that indicate recent announcements
        recent_keywords = [
            'claude-3-7', '3-7-sonnet', 'alexa-plus', 'transparency-hub', 
            'series-e', 'anthropic-raises', 'web-search', 'max-plan', 
            'team-plan', 'android-app', 'ios', 'claude-3-5', '3-5-sonnet',
            'detecting-and-countering', 'march-2025', 'elections-ai-2024',
            'sonnet-3-7', 'claude-4', 'activating-asl3', 'asl3-protections',
            'safety-defenses', 'bug-bounty', 'web-search-api', 'ai-for-science'
        ]
        
        # Recent terms (0-6 months ago)
        if any(keyword in url_path.lower() for keyword in recent_keywords):
            days_ago = random.randint(0, 180)
            date = datetime.now(timezone.utc) - timedelta(days=days_ago)
            # Set to noon UTC
            date = date.replace(hour=12, minute=0, second=0, microsecond=0)
            return date.isoformat()
        
        # Check for terms indicating mid-term announcements
        midterm_keywords = [
            'claude-3-', 'tool-use', 'computer-use', 'citations', 'contextual-retrieval',
            'artifacts', 'prompt-caching', 'message-batches', 'workspaces',
            'styles', 'canada', 'brazil', 'europe', 'uk-government', 'haiku'
        ]
        
        # Mid-term (6-18 months ago)
        if any(keyword in url_path.lower() for keyword in midterm_keywords):
            days_ago = random.randint(180, 540)
            date = datetime.now(timezone.utc) - timedelta(days=days_ago)
            # Set to noon UTC
            date = date.replace(hour=12, minute=0, second=0, microsecond=0)
            return date.isoformat()
        
        # Check for terms indicating older announcements
        older_keywords = [
            'claude-2', 'claude-2-1', '100k-context', 'responsible-scaling',
            'claude-pro', 'claude-instant', 'amazon-bedrock', 'policy',
            'frontier', 'skt-partnership', 'zoom-partnership'
        ]
        
        # Older (18-36 months ago)
        if any(keyword in url_path.lower() for keyword in older_keywords):
            days_ago = random.randint(540, 1080)
            date = datetime.now(timezone.utc) - timedelta(days=days_ago)
            # Set to noon UTC
            date = date.replace(hour=12, minute=0, second=0, microsecond=0)
            return date.isoformat()
        
        # Very old (original Claude announcements)
        oldest_keywords = [
            'introducing-claude', 'slack', 'core-views', 'series-b', 'series-c'
        ]
        
        if any(keyword in url_path.lower() for keyword in oldest_keywords):
            days_ago = random.randint(1080, 1440)
            date = datetime.now(timezone.utc) - timedelta(days=days_ago)
            # Set to noon UTC
            date = date.replace(hour=12, minute=0, second=0, microsecond=0)
            return date.isoformat()
        
        # Default: random date in the past 2 years
        days_ago = random.randint(30, 730)
        date = datetime.now(timezone.utc) - timedelta(days=days_ago)
        # Set to noon UTC
        date = date.replace(hour=12, minute=0, second=0, microsecond=0)
        return date.isoformat()
    
    def parse_news_page(self, html: str) -> List[Dict]:
        """Parse the news page HTML and extract articles."""
        articles = []
        soup = BeautifulSoup(html, "lxml")
        
        # Try to find JSON data with publication info
        json_data = {}
        all_scripts = soup.select('script')
        for script in all_scripts:
            if not script.string:
                continue
                
            # Look for script content that might contain publication data
            script_content = script.string.strip()
            if 'publishedOn' in script_content or 'published' in script_content:
                try:
                    # Try to extract JSON from the script
                    # Look for content between large braces using non-greedy matching
                    matches = re.findall(r'\{.*?"publish.*?":.*?\}', script_content, re.DOTALL)
                    if matches:
                        # Log what we found for debugging
                        logger.info(f"Found {len(matches)} potential JSON objects with publish data")
                        with open(os.path.join(self.cache_dir, "potential_json.txt"), "w", encoding="utf-8") as f:
                            f.write(script_content[:1000])  # Save a sample
                except Exception as e:
                    logger.warning(f"Error examining script content: {e}")
        
        # Find all news article elements
        article_elements = soup.select("a[href^='/news/']")
        logger.info(f"Found {len(article_elements)} article elements on news page")
        
        for article in article_elements:
            # Skip duplicate articles
            href = article.get("href")
            if any(a.get("url", "").endswith(href) for a in articles):
                continue
                
            title_element = article.select_one("h3, h2")
            
            if not title_element:
                continue
                
            # Extract article data
            title = title_element.get_text(strip=True)
            url = f"https://www.anthropic.com{href}"
            
            # Extract date - first check for date in the article text
            article_text = article.get_text(strip=True)
            date = None
            
            # Look for date patterns in the article text
            date_patterns = [
                r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}',
                r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}',
                r'\d{1,2}/\d{1,2}/\d{4}',
                r'\d{4}-\d{2}-\d{2}'
            ]
            
            for pattern in date_patterns:
                date_match = re.search(pattern, article_text)
                if date_match:
                    date_str = date_match.group(0)
                    # Remove date from title if it's appended
                    if title.endswith(date_str):
                        title = title[:-len(date_str)].strip()
                    date = self._parse_date(date_str)
                    logger.info(f"Found date '{date_str}' in article text for '{title}'")
                    break
            
            # If no date found in article text, check parent and siblings
            if not date and article.parent:
                # First check the parent's full text
                parent_text = article.parent.get_text(strip=True)
                for pattern in date_patterns:
                    # Look for dates that are likely associated with this article
                    # by checking if the date appears after the title
                    if title in parent_text:
                        title_pos = parent_text.find(title)
                        search_text = parent_text[title_pos:]
                        date_match = re.search(pattern, search_text)
                        if date_match:
                            date_str = date_match.group(0)
                            date = self._parse_date(date_str)
                            logger.info(f"Found date '{date_str}' in parent text after title for '{title}'")
                            break
                
                # If still no date, check immediate siblings
                if not date:
                    # Get all siblings
                    siblings = list(article.parent.children)
                    article_index = siblings.index(article)
                    
                    # Check next few siblings for date
                    for i in range(article_index + 1, min(article_index + 5, len(siblings))):
                        sibling = siblings[i]
                        if hasattr(sibling, 'get_text'):
                            sibling_text = sibling.get_text(strip=True)
                            for pattern in date_patterns:
                                date_match = re.search(pattern, sibling_text)
                                if date_match:
                                    date_str = date_match.group(0)
                                    date = self._parse_date(date_str)
                                    logger.info(f"Found date '{date_str}' in sibling element for '{title}'")
                                    break
                            if date:
                                break
            
            # If still no date found, use the extraction function
            if not date:
                date = self.extract_date_from_content(article, href)
            
            articles.append({
                "title": title,
                "url": url,
                "date": date,
                "source": "news"
            })
            
        return articles
    
    def parse_research_page(self, html: str) -> List[Dict]:
        """Parse the research page HTML and extract articles."""
        articles = []
        soup = BeautifulSoup(html, "lxml")
        
        # Try to find dates from JSON data in the page
        from urllib.parse import urlparse
        
        # Create a combined function for research item detection
        def find_research_items():
            # Method 1: Look for publication cards
            research_cards = soup.select("div.publication-card, div.research-card, div[class*='publication'], div[class*='research']")
            
            # Method 2: Look for sections with publication-related terms
            if not research_cards:
                research_cards = soup.select("[id*='publication'], [class*='publication'], [id*='paper'], [class*='paper']")
            
            # Method 3: Look for links to research resources
            research_links = soup.select("a[href*='arxiv.org'], a[href*='transformer-circuits'], a[href*='.pdf'], a[href*='paper']")
            
            return research_cards, research_links
        
        research_cards, research_links = find_research_items()
        
        # Process research cards
        if research_cards:
            logger.info(f"Found {len(research_cards)} research cards")
            for card in research_cards:
                # Extract title, link, and date from each card
                title_element = card.select_one("h2, h3, h4, strong, b, [class*='title']")
                link_element = card.select_one("a[href]")
                
                if title_element and link_element:
                    title = title_element.get_text(strip=True)
                    url = link_element.get("href")
                    
                    # Make sure it's a full URL
                    if url and url.startswith("/"):
                        url = f"https://www.anthropic.com{url}"
                    
                    # Extract date using our comprehensive extraction function
                    date = self.extract_date_from_content(card, url)
                    
                    # Only add if we don't already have this exact URL and it's a valid URL
                    if url and not any(a.get("url") == url for a in articles):
                        articles.append({
                            "title": title,
                            "url": url,
                            "date": date,
                            "source": "research"
                        })
        
        # Process research links
        if research_links:
            logger.info(f"Found {len(research_links)} research links")
            for link in research_links:
                url = link.get("href")
                if not url:
                    continue
                
                # Skip navigation links, privacy policies, etc.
                if any(x in url.lower() for x in ["privacy", "terms", "contact", "about", "login", "sign", "home"]):
                    continue
                
                # Extract title - either from link text or from nearby heading
                title = link.get_text(strip=True)
                
                # If link text seems too short or generic, look for a better title nearby
                if not title or len(title) < 15 or title.lower() in ["read paper", "pdf", "arxiv", "link", "read more"]:
                    # Look for parent elements with better text
                    parent = link.parent
                    for _ in range(3):  # Look up to 3 levels up
                        if parent:
                            # Try to find a nearby heading first
                            nearby_heading = parent.find("h2") or parent.find("h3") or parent.find("h4")
                            if nearby_heading:
                                title = nearby_heading.get_text(strip=True)
                                break
                            
                            # Or use the parent's text if it's substantial
                            parent_text = parent.get_text(strip=True)
                            if len(parent_text) > 20 and len(parent_text) < 200:
                                title = parent_text
                                break
                                
                            parent = parent.parent
                
                # If we still don't have a good title, construct one from the URL
                if not title or len(title) < 10:
                    if "arxiv" in url:
                        # Extract arxiv ID
                        arxiv_match = re.search(r'(\d+\.\d+)', url)
                        if arxiv_match:
                            arxiv_id = arxiv_match.group(1)
                            title = f"Anthropic Research Paper (arXiv:{arxiv_id})"
                    else:
                        # Use URL path as title
                        path = urlparse(url).path
                        if path:
                            title_parts = path.strip('/').split('/')[-1].replace('-', ' ').replace('_', ' ')
                            if title_parts:
                                title = f"Anthropic Research: {title_parts.title()}"
                            else:
                                title = "Anthropic Research Paper"
                
                # Extract date using our comprehensive extraction function
                date = self.extract_date_from_content(link.parent, url)
                
                # For arXiv links, try to extract date from arXiv ID
                if "arxiv" in url and "arxiv.org" in url:
                    arxiv_match = re.search(r'(\d+\.\d+)', url)
                    if arxiv_match:
                        arxiv_id = arxiv_match.group(1)
                        # Extract year and month from arXiv ID (YYMM.nnnnn format)
                        if len(arxiv_id.split('.')[0]) >= 4:
                            arxiv_year = "20" + arxiv_id[:2]  # Convert YY to 20YY
                            arxiv_month = arxiv_id[2:4]       # Extract MM
                            try:
                                if 1 <= int(arxiv_month) <= 12:
                                    date = datetime(int(arxiv_year), int(arxiv_month), 15, tzinfo=timezone.utc).isoformat()
                                    logger.info(f"Extracted date from arXiv ID: {date}")
                            except ValueError:
                                pass  # If conversion fails, use the date we already have
                
                # Only add if we don't already have this exact URL and the title is meaningful
                if title and url and not any(a.get("url") == url for a in articles):
                    articles.append({
                        "title": title,
                        "url": url,
                        "date": date,
                        "source": "research"
                    })
        
        return articles
    
    def _parse_date(self, date_str: str) -> str:
        """Parse date from various formats to ISO format with timezone."""
        if not date_str:
            # Use noon UTC time instead of current time
            now = datetime.now(timezone.utc)
            noon_utc = now.replace(hour=12, minute=0, second=0, microsecond=0)
            return noon_utc.isoformat()
        
        # Clean up the date string
        date_str = date_str.strip()
        
        # If it's already in ISO format
        if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', date_str):
            # Check if it has timezone info
            if '+' in date_str or 'Z' in date_str:
                return date_str
            else:
                # Add UTC timezone and set to noon
                try:
                    dt = datetime.fromisoformat(date_str).replace(
                        hour=12, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
                    )
                    return dt.isoformat()
                except ValueError:
                    pass  # Continue to other formats if this fails
        
        try:
            # Handle various date formats
            formats = [
                "%B %d, %Y", "%b %d, %Y",           # January 15, 2023, Jan 15, 2023
                "%B %d %Y", "%b %d %Y",             # January 15 2023, Jan 15 2023
                "%d %B %Y", "%d %b %Y",             # 15 January 2023, 15 Jan 2023
                "%Y-%m-%d", "%Y/%m/%d",             # 2023-01-15, 2023/01/15
                "%d-%m-%Y", "%d/%m/%Y",             # 15-01-2023, 15/01/2023
                "%Y-%m",                            # 2023-01 (assume 1st of month)
                "%Y"                                # 2023 (assume middle of year)
            ]
            
            # Check for relative date formats like "3 months ago"
            relative_match = re.match(r'(\d+)\s+(day|week|month|year)s?\s+ago', date_str, re.IGNORECASE)
            if relative_match:
                num, unit = relative_match.groups()
                num = int(num)
                today = datetime.now(timezone.utc)
                
                if unit.lower() == 'day':
                    dt = today - timedelta(days=num)
                elif unit.lower() == 'week':
                    dt = today - timedelta(weeks=num)
                elif unit.lower() == 'month':
                    # Approximate months as 30 days
                    dt = today - timedelta(days=num*30)
                elif unit.lower() == 'year':
                    # Approximate years as 365 days
                    dt = today - timedelta(days=num*365)
                
                return dt.isoformat()
            
            # Try each format
            for fmt in formats:
                try:
                    # Special case for year-only format
                    if fmt == "%Y" and re.match(r'^\d{4}$', date_str):
                        year = int(date_str)
                        # Use middle of the year (July 1) at noon UTC
                        dt = datetime(year, 7, 1, 12, 0, 0)
                        dt = dt.replace(tzinfo=timezone.utc)
                        return dt.isoformat()
                    
                    # Special case for year-month format
                    if fmt == "%Y-%m" and re.match(r'^\d{4}-\d{2}$', date_str):
                        year, month = date_str.split('-')
                        # Use middle of the month (15th) at noon UTC
                        dt = datetime(int(year), int(month), 15, 12, 0, 0)
                        dt = dt.replace(tzinfo=timezone.utc)
                        return dt.isoformat()
                    
                    dt = datetime.strptime(date_str, fmt)
                    # Add UTC timezone and set to noon
                    dt = dt.replace(hour=12, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
                    return dt.isoformat()
                except ValueError:
                    continue
            
            # Try to extract year from string if nothing else works
            year_match = re.search(r'\b(20\d\d)\b', date_str)
            if year_match:
                year = int(year_match.group(1))
                # Use middle of the year if only year is available, at noon UTC
                dt = datetime(year, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
                return dt.isoformat()
                
            # If no format matches, return a reasonable default
            # Instead of current time, use 6 months ago as a conservative estimate
            now = datetime.now(timezone.utc)
            six_months_ago = now - timedelta(days=180)
            # Set to noon UTC
            six_months_ago = six_months_ago.replace(hour=12, minute=0, second=0, microsecond=0)
            logger.warning(f"Could not parse date '{date_str}', using default (6 months ago)")
            return six_months_ago.isoformat()
        except Exception as e:
            logger.error(f"Error parsing date '{date_str}': {e}")
            # Use 1 year ago as fallback instead of today
            now = datetime.now(timezone.utc)
            one_year_ago = now - timedelta(days=365)
            # Set to noon UTC
            one_year_ago = one_year_ago.replace(hour=12, minute=0, second=0, microsecond=0)
            return one_year_ago.isoformat()
    
    def fetch_article_content(self, url: str, check_modified: bool = True) -> Optional[str]:
        """
        Fetch the full content of an individual article.
        
        Args:
            url: The URL to fetch content from
            check_modified: Whether to use conditional requests
            
        Returns:
            The first paragraph of the article, or None if not available
        """
        html, modified, metadata = self.fetch_page(url, check_modified)
        
        if not html:
            if not modified and "content_cache" in self.http_cache.get(url, {}):
                # If content hasn't changed and we have cached content, use that
                logger.info(f"Using cached content for {url}")
                return self.http_cache[url]["content_cache"]
            else:
                logger.warning(f"Could not fetch article content from {url}")
                return None
        
        # Extract the first paragraph
        paragraph = self.extract_first_paragraph(html, url)
        
        # Cache the content for future use
        if paragraph and url in self.http_cache:
            self.http_cache[url]["content_cache"] = paragraph
            self._save_http_cache()
            
        return paragraph
    
    def extract_first_paragraph(self, html: str, url: str) -> Optional[str]:
        """Extract the first meaningful paragraph from article content."""
        soup = BeautifulSoup(html, "lxml")
        
        # Remove navigation, headers, footers, and other non-content elements
        for element in soup.select("nav, header, footer, .nav, .menu, .header, .footer"):
            element.decompose()
        
        # Look for the article body or main content area
        content_selectors = [
            "article", "main", ".article-body", ".post-content", ".entry-content",
            "[class*='article-content']", "[class*='post-content']", "[class*='entry-content']",
            "#content", ".content", "[class*='content-area']"
        ]
        
        content_area = None
        for selector in content_selectors:
            content_area = soup.select_one(selector)
            if content_area:
                break
                
        # If we couldn't find a content area, use the body
        if not content_area:
            content_area = soup.body
            
        if not content_area:
            logger.warning(f"Could not find content area in {url}")
            return None
            
        # Find paragraphs
        paragraphs = content_area.find_all("p")
        if not paragraphs:
            logger.warning(f"No paragraphs found in content area for {url}")
            return None
            
        # Find the first non-empty paragraph with substantial text
        for p in paragraphs:
            text = p.get_text(strip=True)
            # Skip empty paragraphs or very short ones that might be captions
            if text and len(text) > 30:
                return text
                
        # If we couldn't find a substantial paragraph, use the first non-empty one
        for p in paragraphs:
            text = p.get_text(strip=True)
            if text:
                return text
                
        return None
    
    def scrape_all(self, check_modified: bool = True, merge_with_cache: bool = True) -> List[Dict]:
        """
        Scrape both news and research pages and combine results.
        
        Args:
            check_modified: Whether to use conditional requests to check if content has changed
            merge_with_cache: Whether to merge results with cached articles
            
        Returns:
            List of article dictionaries
        """
        all_articles = []
        modified_content = False
        
        # Load cached articles if we're going to merge
        cached_articles = self.load_from_cache() if merge_with_cache else []
        cache_urls = {article.get("url", ""): article for article in cached_articles}
        
        # Scrape news page
        news_html, news_modified, news_metadata = self.fetch_page(self.NEWS_URL, check_modified)
        
        if news_html:
            # Page was fetched and has new content
            modified_content = True
            news_articles = self.parse_news_page(news_html)
            all_articles.extend(news_articles)
            logger.info(f"Scraped {len(news_articles)} news articles")
        elif news_metadata:
            # Page was checked but hasn't changed
            logger.info("News page hasn't changed since last check")
            # Add cached news articles to our results
            if merge_with_cache:
                news_articles = [a for a in cached_articles if a.get("source") == "news"]
                all_articles.extend(news_articles)
                logger.info(f"Using {len(news_articles)} cached news articles")
        
        # Scrape research page
        research_html, research_modified, research_metadata = self.fetch_page(self.RESEARCH_URL, check_modified)
        
        if research_html:
            # Page was fetched and has new content
            modified_content = True
            research_articles = self.parse_research_page(research_html)
            all_articles.extend(research_articles)
            logger.info(f"Scraped {len(research_articles)} research articles")
        elif research_metadata:
            # Page was checked but hasn't changed
            logger.info("Research page hasn't changed since last check")
            # Add cached research articles to our results
            if merge_with_cache:
                research_articles = [a for a in cached_articles if a.get("source") == "research"]
                all_articles.extend(research_articles)
                logger.info(f"Using {len(research_articles)} cached research articles")
        
        # If we have new content, we need to fetch article details
        if modified_content:
            # Filter out pages that aren't really articles
            filtered_articles = []
            excluded_patterns = [
                "/legal/", "privacy", "terms", "aup", "licenses", "cookie", 
                "about-us", "contact", "careers", "jobs", "faq", "login", 
                "signin", "signup", "register"
            ]
            
            for article in all_articles:
                url = article.get("url", "").lower()
                
                # Skip articles with excluded patterns in URL
                if any(pattern in url for pattern in excluded_patterns):
                    logger.info(f"Filtering out non-article URL: {url}")
                    continue
                    
                # Skip articles with missing or very short titles
                title = article.get("title", "")
                if not title or len(title) < 5:
                    logger.info(f"Filtering out article with invalid title: {url}")
                    continue
                    
                # If we already have this article in cache and it has a summary, reuse it
                if merge_with_cache and url in cache_urls and "summary" in cache_urls[url]:
                    article["summary"] = cache_urls[url]["summary"]
                    logger.info(f"Reusing cached summary for {title}")
                # Otherwise fetch the article content and extract the first paragraph
                elif url.startswith("https://www.anthropic.com"):
                    logger.info(f"Fetching content for article: {title}")
                    first_paragraph = self.fetch_article_content(url, check_modified)
                    if first_paragraph:
                        article["summary"] = first_paragraph
                        logger.info(f"Found first paragraph for {title} ({len(first_paragraph)} chars)")
                
                # Include this article in the filtered list
                filtered_articles.append(article)
                
            filtered_count = len(all_articles) - len(filtered_articles)
            if filtered_count > 0:
                logger.info(f"Filtered out {filtered_count} non-article pages")
                
            # Sort by date, most recent first
            filtered_articles.sort(key=lambda x: x.get("date", ""), reverse=True)
            
            # If we merged with cache, make sure we don't lose any articles
            if merge_with_cache:
                # Get URLs of our filtered articles
                filtered_urls = {article.get("url", "") for article in filtered_articles}
                
                # Add any cached articles that aren't in our filtered results
                for url, cached_article in cache_urls.items():
                    if url not in filtered_urls:
                        filtered_articles.append(cached_article)
                        logger.info(f"Keeping cached article not found in new scrape: {cached_article.get('title', '')}")
                
                # Re-sort after merging
                filtered_articles.sort(key=lambda x: x.get("date", ""), reverse=True)
                
            # Save to cache
            self._save_to_cache(filtered_articles)
            
            return filtered_articles
        else:
            # Nothing changed, return cached articles
            logger.info("No changes detected, using cached articles")
            return cached_articles
    
    def _save_to_cache(self, articles: List[Dict]) -> None:
        """
        Save scraped articles to cache file.
        Also updates the cache timestamp.
        """
        # Add timestamp to track when cache was last updated
        cache_data = {
            "timestamp": time.time(),
            "articles": articles
        }
        
        try:
            with open(self.articles_cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2)
            logger.info(f"Saved {len(articles)} articles to cache with timestamp")
        except IOError as e:
            logger.error(f"Error saving to cache: {e}")
    
    def load_from_cache(self) -> List[Dict]:
        """
        Load articles from cache if available.
        
        Returns:
            List of article dictionaries from cache, or empty list if cache doesn't exist
        """
        try:
            if os.path.exists(self.articles_cache_file):
                with open(self.articles_cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                
                # Check if we have the new format with timestamp
                if isinstance(cache_data, dict) and "articles" in cache_data:
                    articles = cache_data["articles"]
                    timestamp = cache_data.get("timestamp", "unknown")
                    logger.info(f"Loaded {len(articles)} articles from cache (timestamp: {timestamp})")
                else:
                    # Handle old format (just a list)
                    articles = cache_data
                    logger.info(f"Loaded {len(articles)} articles from cache (old format)")
                
                return articles
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Error loading from cache: {e}")
        
        return []


if __name__ == "__main__":
    # Test the scraper
    scraper = AnthropicScraper()
    articles = scraper.scrape_all()
    print(f"Scraped {len(articles)} total articles")
    for article in articles[:5]:
        print(f"{article['title']} - {article['date']} - {article['source']}")