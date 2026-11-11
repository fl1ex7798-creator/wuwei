"""MIT Admissions blogs -> CSV, independently through two browser engines."""
import argparse
import csv
import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.robotparser import RobotFileParser

from browsers import USER_AGENT, browser_backend
from parser import BASE, HEADERS, article_links, extract_article, next_page

LOG = logging.getLogger(__name__)


def write_csv(path, rows):
    """Only publish a CSV when real rows exist; preserve a prior result on failure."""
    if not rows:
        return
    temporary = path.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def crawl(engine, args):
    started = datetime.now(timezone.utc).isoformat()
    rows, sources, errors, warnings = [], [], [], []
    visited = set()
    current = "https://mitadmissions.org/robots.txt"
    try:
        with browser_backend(engine, args.browser, args.headed) as browser:
            _, robots_text = browser.get(current)
            if "user-agent:" not in robots_text.lower():
                raise RuntimeError("robots.txt could not be verified; stopping without crawling articles")
            rules = RobotFileParser()
            rules.parse(robots_text.splitlines())
            delay = max(args.delay, rules.crawl_delay(USER_AGENT) or 0)

            def fetch(url):
                if not rules.can_fetch(USER_AGENT, url):
                    raise RuntimeError(f"robots.txt disallows {url}")
                time.sleep(delay)
                LOG.info("[%s] %s", engine, url)
                return browser.get(url)[0]

            current = BASE
            links = []
            for _ in range(args.pages):
                if not current or current in visited:
                    break
                html = fetch(current)
                visited.add(current)
                found = article_links(html, current)
                if not found:
                    raise RuntimeError(f"No article links found at {current}; inspect live DOM")
                links.extend(url for url in found if url not in links)
                if args.limit and len(links) >= args.limit:
                    break
                current = next_page(html, current)
            if args.limit:
                links = links[:args.limit]
            for url in links:
                try:
                    row = extract_article(fetch(url), url)
                    rows.append(row)
                    sources.append({"csv_row": len(rows) + 1, "url": url})
                    if row["Comment Count"] == "":
                        warnings.append({"url": url, "message": "Comment count unavailable; cell left empty"})
                except Exception as exc:
                    LOG.error("[%s] %s: %s", engine, url, exc)
                    errors.append({"url": url, "error": str(exc)})
    except Exception as exc:
        LOG.error("[%s] %s", engine, exc)
        errors.append({"url": current, "error": str(exc)})
    output = args.output / f"{engine}.csv"
    write_csv(output, rows)
    manifest = {
        "engine": engine, "started_at_utc": started,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "requested_listing_pages": args.pages, "limit": args.limit,
        "listing_pages": sorted(visited), "rows": len(rows),
        "csv_written_this_run": bool(rows), "complete_for_requested_scope": bool(rows) and not errors,
        "sources": sources, "warnings": warnings, "errors": errors,
    }
    (args.output / f"{engine}.run.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    LOG.info("[%s] saved %d rows; %d failures; %d warnings", engine, len(rows), len(errors), len(warnings))
    return bool(rows) and not errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=["both", "playwright", "drissionpage"], default="both")
    parser.add_argument("--pages", type=int, default=1, help="Maximum listing pages per engine (default: 1)")
    parser.add_argument("--limit", type=int, default=0, help="Maximum articles per engine; 0 means all on selected pages")
    parser.add_argument("--delay", type=float, default=1.5, help="Minimum seconds between navigations")
    parser.add_argument("--output", type=Path, default=Path("results"))
    parser.add_argument("--browser", default=os.environ.get("CHROME_PATH") or shutil.which("chromium") or shutil.which("google-chrome"))
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    if args.pages < 1 or args.limit < 0 or args.delay < 0:
        parser.error("pages must be >= 1; limit and delay must be >= 0")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args.output.mkdir(parents=True, exist_ok=True)
    engines = ["playwright", "drissionpage"] if args.engine == "both" else [args.engine]
    results = [crawl(engine, args) for engine in engines]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
