# Quotes Scraper

A small, well-behaved web scraper that crawls [quotes.toscrape.com](http://quotes.toscrape.com)
and saves quotes (text, author, tags) to a CSV file.

Built to be safe to re-run: each run merges new quotes into the existing
CSV instead of overwriting it, and skips duplicates automatically.

## Features

- **Resumable / incremental** — re-running the script only appends *new*
  quotes; existing rows are loaded and deduplicated by quote text.
- **Retries with exponential backoff** — network hiccups are retried up
  to 3 times before a page is skipped.
- **Pagination-safe** — stops gracefully if the "next" button is missing
  or malformed instead of crashing.
- **Polite by default** — 1 second delay between page requests, a
  realistic User-Agent header, and a configurable page limit.
- **Configurable via CLI** — control max pages, output file, and log
  verbosity without touching the code.

## Installation

```bash
git clone https://github.com/<your-username>/quotes-toscrape-scraper.git
cd quotes-toscrape-scraper
pip install -r requirements.txt
```

**requirements.txt**
## Usage

```bash
python scraper.py
```

### Options

| Flag           | Default       | Description                          |
|----------------|---------------|---------------------------------------|
| `--max-pages`  | `10`          | Maximum number of pages to scrape     |
| `--output`     | `quotes.csv`  | Output CSV file path                  |
| `--log-level`  | `INFO`        | `DEBUG`, `INFO`, `WARNING`, `ERROR`   |

Example:

```bash
python scraper.py --max-pages 5 --output data/quotes.csv --log-level DEBUG
```

## Output

A CSV file with the following columns:

| text | author | tags |
|------|--------|------|
| "The world as we have created it..." | Albert Einstein | change, deep-thoughts, thinking, world |

## How it works

1. Loads any existing rows from the output CSV (for dedup).
2. Crawls pages starting from the site root, following the "Next" button
   until either there's no next page or `--max-pages` is reached.
3. Parses each quote card into `text`, `author`, and `tags`.
4. Filters out quotes already present in the existing CSV.
5. Merges old + new rows and writes the full result back to disk.

## License

MIT
