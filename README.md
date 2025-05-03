# Anthropic News and Research Feed

An automated Atom feed generator for Anthropic's news and research pages.

## Features

- Scrapes [Anthropic's news](https://www.anthropic.com/news) and [research](https://www.anthropic.com/research) pages
- Generates an Atom feed updated every 4 hours via GitHub Actions
- Hosted on GitHub Pages for easy access
- Provides Atom, XML, and JSON feed formats
- Simple web interface to view recent articles

## Feed URLs

- Atom Feed: https://tcole.net/llm-news/feed.atom
- XML Feed: https://tcole.net/llm-news/feed.xml
- JSON Feed: https://tcole.net/llm-news/feed.json

## Local Development

### Prerequisites

- Python 3.8+
- pip (Python package manager)

### Setup

1. Clone the repository:
   ```
   git clone https://github.com/kelp/llm-news.git
   cd llm-news
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the feed generator:
   ```
   python src/main.py --output-dir ./ --cache-dir ./data --force-refresh
   ```

4. Open `index.html` in your browser to view the results

### Usage

```
python src/main.py [options]

Options:
  --output-dir DIR   Directory to save the generated feeds (default: .)
  --cache-dir DIR    Directory to store cached data (default: data)
  --force-refresh    Force refresh of all data
```

## How It Works

1. The scraper fetches and parses HTML from Anthropic's news and research pages
2. Article data (title, date, URL) is extracted and stored
3. The feed generator creates standard Atom, XML, and JSON feeds
4. GitHub Actions runs this process every 4 hours and commits the updated feeds
5. The web interface displays recent articles by reading the JSON feed

## Deployment

This project is designed to be deployed on GitHub Pages:

1. Fork this repository
2. Enable GitHub Pages in repository settings (Settings > Pages)
3. Select the main branch as the source
4. GitHub Actions will automatically update the feed every 4 hours

## License

[MIT License](LICENSE)

## Disclaimer

This is an unofficial feed generator not affiliated with or endorsed by Anthropic. It is provided for convenience only.