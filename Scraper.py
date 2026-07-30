
import argparse
import csv
import logging
import re
import time

import requests
from bs4 import BeautifulSoup



BASE_URL = "http://quotes.toscrape.com"
DEFAULT_CSV = "quotes.csv"
DEFAULT_MAX_PAGES = 10
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = 2.0
REQUEST_TIMEOUT = 10

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}

log = logging.getLogger(__name__)


def configure_logging(level: str = "INFO") -> None:
    """Configure root logger with a timestamped format."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def fetch_page(url: str) -> BeautifulSoup | None:
    """
    Fetch *url* and return a BeautifulSoup object.
    Retries up to RETRY_ATTEMPTS times with exponential back-off.  (Fix #3)
    """
    delay = RETRY_BACKOFF
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.exceptions.RequestException as exc:
            if attempt < RETRY_ATTEMPTS:
                log.warning(
                    "Attempt %d/%d failed for %s — %s. Retrying in %.1fs ...",
                    attempt, RETRY_ATTEMPTS, url, exc, delay,
                )
                time.sleep(delay)
                delay *= 2
            else:
                log.error("All %d attempts failed for %s — %s", RETRY_ATTEMPTS, url, exc)
    return None


def clean_text(element, default: str = "N/A") -> str:
    """Return normalised inner text of *element*, or *default* if absent."""
    if element is None:
        return default
    return " ".join(element.get_text(strip=True).split()) or default


def parse_page(soup: BeautifulSoup) -> list[dict]:
    """Extract all quote cards from *soup* and return a list of dicts."""
    results = []
    for card in soup.find_all("div", class_="quote"):
        raw_text = clean_text(card.find("span", class_="text"))
        text = re.sub(r'^["\u201c]|["\u201d]$', "", raw_text).strip()
        author = clean_text(card.find("small", class_="author"))
        tags = ", ".join(clean_text(t) for t in card.find_all("a", class_="tag"))
        results.append({"text": text, "author": author, "tags": tags})
    return results


def get_next_url(soup: BeautifulSoup) -> str | None:
    """
    Return the absolute URL of the next page, or None.
    Guarded against a missing <a> inside the 'next' button.  (Fix #6)
    """
    btn = soup.find("li", class_="next")
    if not btn:
        return None
    anchor = btn.find("a")
    if not anchor or not anchor.get("href"):
        log.warning("Found 'next' button but no valid <a href> inside it.")
        return None
    return BASE_URL + anchor["href"]


def scrape_all(max_pages: int = DEFAULT_MAX_PAGES) -> list[dict]:   # Fix #4
    """Scrape up to *max_pages* pages and return all quotes."""
    all_data: list[dict] = []
    url: str | None = BASE_URL
    page = 1

    while url and page <= max_pages:
        log.info("Fetching page %d: %s", page, url)
        soup = fetch_page(url)
        if not soup:
            log.error("Stopping early — could not fetch page %d.", page)
            break

        items = parse_page(soup)
        all_data.extend(items)
        log.info("  +%d items -> total %d", len(items), len(all_data))

        url = get_next_url(soup)
        page += 1
        time.sleep(1)   # be polite

    return all_data


def load_existing(filename: str) -> tuple[list[dict], set[str]]:
    """
    Load rows already saved in *filename*.
    Returns the existing rows (for merging) and a set of texts (for dedup).
    """
    try:
        with open(filename, "r", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        keys = {row["text"] for row in rows}
        log.info("Loaded %d existing records from '%s'.", len(rows), filename)
        return rows, keys
    except FileNotFoundError:
        log.info("No existing file '%s' — starting fresh.", filename)
        return [], set()


def save_csv(data: list[dict], filename: str = DEFAULT_CSV) -> None:
    """
    Write the fully merged *data* to *filename*.
    Caller must pass the combined old+new dataset.  (Fix #7)
    """
    if not data:
        log.warning("No data to save.")
        return

    with open(filename, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(data[0].keys()))
        writer.writeheader()
        writer.writerows(data)

    log.info("Saved %d rows to '%s'.", len(data), filename)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scraper",
        description="Scrape quotes from quotes.toscrape.com into a CSV file.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        metavar="N",
        help=f"Maximum number of pages to scrape (default: {DEFAULT_MAX_PAGES}).",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_CSV,
        metavar="FILE",
        help=f"Output CSV file path (default: {DEFAULT_CSV}).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    configure_logging(args.log_level)

    existing_rows, existing_keys = load_existing(args.output)   # Fix #2
    fresh = scrape_all(max_pages=args.max_pages)

    new_items = [q for q in fresh if q["text"] not in existing_keys]
    log.info("%d new quote(s) found since last run.", len(new_items))

    merged = existing_rows + new_items   # Fix #2 + #7
    save_csv(merged, filename=args.output)

if __name__ == "__main__":
    main()