"""
Main script to run the scraper and feed generator.
"""
import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone

from scraper import AnthropicScraper
from feed_generator import AtomFeedGenerator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="Generate Atom feed for Anthropic news and research")
    parser.add_argument(
        "--output-dir", 
        default=".", 
        help="Directory to save the generated feeds"
    )
    parser.add_argument(
        "--cache-dir", 
        default="data", 
        help="Directory to store cached data"
    )
    parser.add_argument(
        "--force-refresh", 
        action="store_true",
        help="Force refresh of all data (ignore HTTP caching)"
    )
    parser.add_argument(
        "--check-updates", 
        action="store_true",
        help="Use conditional HTTP requests to check for updates (default behavior)"
    )
    parser.add_argument(
        "--max-age", 
        type=int, 
        default=14400,  # 4 hours in seconds
        help="Maximum age (in seconds) of cached data before forcing a check"
    )
    args = parser.parse_args()
    
    # Create directories if they don't exist
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.cache_dir, exist_ok=True)
    
    logger.info("Starting Anthropic feed generation")
    start_time = datetime.now(timezone.utc)
    
    # Initialize scraper
    scraper = AnthropicScraper(cache_dir=args.cache_dir)
    
    # Determine the refresh strategy based on args and cache age
    check_for_updates = True
    merge_with_cache = True
    
    # If force refresh is specified, don't use HTTP caching
    if args.force_refresh:
        logger.info("Force refresh specified, bypassing HTTP cache")
        check_for_updates = False
        merge_with_cache = False  # Don't merge with cache on force refresh
    
    # If not forcing, check cache age before proceeding
    if not args.force_refresh:
        # Load the cache to see if we have articles
        cached_articles = scraper.load_from_cache()
        
        if not cached_articles:
            logger.info("No cached articles found, will scrape website")
            # Will do a full scrape below
        else:
            # Check if we need to update based on cache age
            cache_file = os.path.join(args.cache_dir, "anthropic_articles.json")
            if os.path.exists(cache_file):
                cache_mtime = os.path.getmtime(cache_file)
                cache_age = time.time() - cache_mtime
                
                if cache_age > args.max_age:
                    logger.info(f"Cache is {cache_age:.1f}s old (max: {args.max_age}s), checking for updates")
                    # Will check for updates below
                else:
                    logger.info(f"Cache is {cache_age:.1f}s old (max: {args.max_age}s), using cached data")
                    # Just use cached articles without checking for updates
                    articles = cached_articles
                    check_for_updates = False  # Skip the update check
    
    # If we need to check for updates or don't have articles yet, scrape the website
    if check_for_updates or not 'articles' in locals():
        logger.info("Checking for updates or scraping Anthropic website...")
        articles = scraper.scrape_all(check_modified=check_for_updates, merge_with_cache=merge_with_cache)
        
    logger.info(f"Found {len(articles)} articles")
    
    # Generate the feed
    feed_generator = AtomFeedGenerator(output_dir=args.output_dir)
    
    # Determine the feed URL based on final hosting URL
    feed_url = "https://tcole.net/llm-news/feed.atom"
    
    logger.info(f"Generating Atom feed at {feed_url}")
    feed_generator.generate_feed(
        articles=articles,
        feed_id="anthropic-feed",
        title="Anthropic News and Research",
        author="Anthropic Feed Generator",
        feed_url=feed_url
    )
    
    # Report execution time
    execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(f"Feed generation completed in {execution_time:.2f} seconds")
    
    # Write last update time to a file
    with open(os.path.join(args.output_dir, "last_update.txt"), "w") as f:
        f.write(f"Last updated: {datetime.now(timezone.utc).isoformat()}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())