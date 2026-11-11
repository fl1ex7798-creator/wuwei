"""Shared extraction logic; browser engines independently retrieve their own HTML."""
import json
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

HEADERS = ["Title", "Author", "Comment Count", "Time", "Article Content", "Images In Article"]
BASE = "https://mitadmissions.org/blogs/"


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def canonical(url):
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def article_links(html, url):
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("main, #main, #content") or soup
    links = []
    for a in root.select('a[href]'):
        target = canonical(urljoin(url, a["href"]))
        if urlsplit(target).hostname == "mitadmissions.org" and re.match(
            r"^/blogs/entry/[^/]+/?$", urlsplit(target).path
        ) and target not in links:
            links.append(target)
    return links


def next_page(html, url):
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select('a[rel~="next"], a.next, .pagination a, nav a'):
        target = canonical(urljoin(url, a.get("href", "")))
        if (urlsplit(target).hostname == "mitadmissions.org"
                and re.match(r"^/blogs/page/\d+/?$", urlsplit(target).path)
                and ("next" in " ".join(a.get("rel", [])).lower()
                     or "next" in " ".join(a.get("class", [])).lower()
                     or re.search(r"next|older|→|»", a.get_text(), re.I))):
            return target
    return None


def structured_article(soup):
    def walk(value):
        if isinstance(value, list):
            for item in value:
                yield from walk(item)
        elif isinstance(value, dict):
            kind = value.get("@type", [])
            if isinstance(kind, str):
                kind = [kind]
            if set(kind) & {"BlogPosting", "Article", "NewsArticle"}:
                yield value
            yield from walk(value.get("@graph", []))
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            found = next(walk(json.loads(script.string or script.get_text())), None)
            if found:
                return found
        except (ValueError, TypeError):
            continue
    return {}


def extract_article(html, url):
    soup = BeautifulSoup(html, "html.parser")
    data = structured_article(soup)

    def text(selector):
        node = soup.select_one(selector)
        return clean(node.get_text(" ", strip=True)) if node else ""

    def meta(selector):
        node = soup.select_one(selector)
        return clean(node.get("content", "")) if node else ""

    heading = soup.select_one("h1")
    title = clean(data.get("headline")) or (clean(heading.get_text(" ", strip=True)) if heading else "")
    author_data = data.get("author", [])
    if not isinstance(author_data, list):
        author_data = [author_data]
    authors = [clean(a.get("name", "") if isinstance(a, dict) else a) for a in author_data]
    author = "; ".join(a for a in authors if a) or meta('meta[name="author"]')
    if not author:
        nodes = soup.select('a[rel~="author"], .post-author, .entry-author, .author-name, .byline a, a[href*="/blogs/author/"]')
        author = "; ".join(dict.fromkeys(clean(n.get_text(" ", strip=True)) for n in nodes if clean(n.get_text())))

    timestamp = clean(data.get("datePublished")) or meta('meta[property="article:published_time"]')
    if not timestamp:
        node = soup.select_one("time[datetime], time, .post-date, .entry-date, .published")
        timestamp = clean(node.get("datetime") or node.get_text(" ", strip=True)) if node else ""

    count = data.get("commentCount", "")
    if count == "":
        for node in soup.select('a[href$="#comments"], a[href$="#disqus_thread"], .comments-count, .comment-count, #comments h2, #comments h3'):
            label = clean(node.get_text(" ", strip=True))
            match = re.search(r"\b(\d[\d,]*)\b", label)
            if match:
                count = int(match.group(1).replace(",", ""))
                break
            if re.search(r"no comments|leave a comment|be the first", label, re.I):
                count = 0
                break
    # Missing counts stay empty: unavailable does not mean zero.
    body = None
    for selector in (".entry-content", ".post-content", ".post__content", ".blog-post-content",
                     ".blog-entry-content", ".article-content", '[itemprop="articleBody"]',
                     ".post-body", ".post__body", ".article-body"):
        body = soup.select_one(selector)
        if body:
            break
    if body is None:
        raise ValueError("Article body selector did not match; inspect the live DOM before updating selectors")
    for unwanted in body.select("script, style, nav, .comments, #comments, #disqus_thread, .sharedaddy, .share-buttons"):
        unwanted.decompose()

    images = []
    for image in body.select("img"):
        source = image.get("data-src") or image.get("data-lazy-src") or image.get("src", "")
        if not source or source.startswith("data:"):
            srcset = image.get("data-srcset") or image.get("srcset", "")
            source = srcset.split(",")[-1].strip().split(" ")[0] if srcset else ""
        if source and not source.startswith("data:"):
            target = urljoin(url, source)
            if urlsplit(target).scheme in {"http", "https"} and target not in images:
                images.append(target)
    content = "\n".join(clean(line) for line in body.get_text("\n", strip=True).splitlines() if clean(line))
    missing = [key for key, value in (("Title", title), ("Author", author), ("Time", timestamp), ("Article Content", content)) if not value]
    if missing:
        raise ValueError("Missing required article fields: " + ", ".join(missing))
    return dict(zip(HEADERS, [title, author, count, timestamp, content, json.dumps(images, ensure_ascii=False)]))
