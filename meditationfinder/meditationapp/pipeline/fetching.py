import hashlib
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


MAX_COMPACT_TEXT_CHARS = 12000


class VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden_depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ["script", "style", "noscript", "svg"]:
            self.hidden_depth += 1

    def handle_endtag(self, tag):
        if tag in ["script", "style", "noscript", "svg"] and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data):
        if not self.hidden_depth:
            text = data.strip()
            if text:
                self.parts.append(text)

    def text(self):
        return " ".join(self.parts)


class LinkParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attrs_by_name = dict(attrs)
        href = attrs_by_name.get("href")
        if href:
            self.links.append(urljoin(self.base_url, href))


def fetch_html(url):
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; MindfulMeetupsBot/0.1; +https://mindfulmeetups.com)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=20) as response:
        html = response.read().decode("utf-8", errors="replace")
        return response.status, html


def compact_html(html):
    parser = VisibleTextParser()
    parser.feed(html)
    text = parser.text()
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_COMPACT_TEXT_CHARS]


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_internal_links(base_url, html):
    parser = LinkParser(base_url)
    parser.feed(html)
    base_host = normalized_host(base_url)
    links = []
    seen = set()
    for link in parser.links:
        cleaned_link = strip_fragment(link)
        if normalized_host(cleaned_link) == base_host and cleaned_link not in seen:
            links.append(cleaned_link)
            seen.add(cleaned_link)
    return links[:80]


def normalized_host(url):
    return urlparse(url).netloc.lower().removeprefix("www.")


def strip_fragment(url):
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl()
