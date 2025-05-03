"""
Main script to run the scraper and feed generator.
"""
import argparse
import logging
import os
import sys
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
        help="Force refresh of all data"
    )
    args = parser.parse_args()
    
    # Create directories if they don't exist
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.cache_dir, exist_ok=True)
    
    logger.info("Starting Anthropic feed generation")
    start_time = datetime.now(timezone.utc)
    
    # Initialize scraper
    scraper = AnthropicScraper(cache_dir=args.cache_dir)
    
    # Either load from cache or force a refresh
    articles = []
    if not args.force_refresh:
        articles = scraper.load_from_cache()
    
    # If no articles in cache or force refresh, scrape them
    if not articles or args.force_refresh:
        logger.info("Scraping Anthropic website...")
        articles = scraper.scrape_all()
        
    logger.info(f"Found {len(articles)} articles")
    
    # Generate the feed
    feed_generator = AtomFeedGenerator(output_dir=args.output_dir)
    
    # Determine the feed URL based on GitHub Pages pattern
    feed_url = "https://kelp.github.io/llm-news/feed.atom"
    
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