"""Local fixtures only. These are not live MIT crawl results."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from crawl import write_csv
from parser import BASE, HEADERS, article_links, extract_article, next_page

FIXTURE = Path(__file__).parent / "fixtures" / "article.html"


class CrawlerTests(unittest.TestCase):
    def test_article_and_csv_round_trip(self):
        row = extract_article(FIXTURE.read_text(), BASE + "entry/example/")
        self.assertEqual(list(row), HEADERS)
        self.assertEqual(row["Author"], "Example Author")
        self.assertEqual(row["Comment Count"], 12)
        self.assertEqual(row["Time"], "2026-01-01T10:00:00Z")
        self.assertNotIn("Excluded", row["Article Content"])
        self.assertIn('\n', row["Article Content"])
        self.assertEqual(json.loads(row["Images In Article"]), [
            "https://mitadmissions.org/images/example.jpg", "https://example.org/lazy.png"])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "result.csv"
            write_csv(path, [row])
            with path.open(encoding="utf-8-sig", newline="") as stream:
                restored = list(csv.DictReader(stream))
            self.assertEqual(restored[0]["Article Content"], row["Article Content"])
            self.assertEqual(restored[0]["Title"], row["Title"])

    def test_links_deduplicated_and_pagination(self):
        html = '<main><a href="/blogs/entry/one/">One</a><a href="/blogs/entry/one/#comments">Comments</a><a href="https://example.org/blogs/entry/wrong/">External</a><a href="/blogs/author/person/">Author</a></main><a rel="next" href="/blogs/page/2/">Next</a>'
        self.assertEqual(article_links(html, BASE), [BASE + "entry/one/"])
        self.assertEqual(next_page(html, BASE), BASE + "page/2/")

    def test_unavailable_comments_are_not_zero(self):
        html = '<h1>Test</h1><meta name="author" content="Author"><time datetime="2026-01-01"></time><div class="entry-content"><p>Content</p></div>'
        self.assertEqual(extract_article(html, BASE)["Comment Count"], "")

    def test_invalid_or_blocked_page_is_rejected(self):
        with self.assertRaises(ValueError):
            extract_article('<h1>Access denied</h1>', BASE)

    def test_failure_does_not_create_fake_csv(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "result.csv"
            write_csv(path, [])
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
