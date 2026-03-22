"""Scrape historical posts from rapwords.tumblr.com."""

from __future__ import annotations

import re
import time
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from rapwords.config import TUMBLR_BASE_URL, TUMBLR_TOTAL_PAGES
from rapwords.models import FeaturedWord, PartOfSpeech, RapWordsPost


def _parse_pos(text: str) -> PartOfSpeech:
    t = text.strip().lower()
    for pos in PartOfSpeech:
        if t == pos.value or t.startswith(pos.value):
            return pos
    return PartOfSpeech.OTHER


def _extract_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    if "youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc:
        qs = parse_qs(parsed.query)
        if "v" in qs:
            return qs["v"][0]
        # youtu.be/VIDEO_ID format
        if parsed.path and len(parsed.path) > 1:
            return parsed.path.lstrip("/")
    return None


def _parse_word_definition(text: str, link: Tag | None) -> FeaturedWord | None:
    """Parse a word definition from text like 'syl·la·ble - Adjective - definition'."""
    wiktionary_url = None
    syllables = None

    if link:
        href = link.get("href", "")
        if "wiktionary" in href:
            wiktionary_url = href
        syllables = link.get_text(strip=True)

    # Normalize whitespace (non-breaking spaces, etc.)
    text = re.sub(r"[\xa0\u00a0]", " ", text)

    # The full text should contain: syllable-word - POS - definition
    # Split on ' - ' to extract parts
    parts = re.split(r"\s*-\s+", text, maxsplit=2)
    if len(parts) < 2:
        return None

    word_text = parts[0].strip()
    pos_text = parts[1].strip()
    definition = parts[2].strip() if len(parts) > 2 else ""

    # Clean the word: remove syllable dots, get the base word
    word = re.sub(r"[·\u00b7\u2027.]", "", syllables or word_text).strip().lower()
    if not word:
        return None

    return FeaturedWord(
        word=word,
        syllables=syllables,
        part_of_speech=_parse_pos(pos_text),
        definition=definition,
        wiktionary_url=wiktionary_url,
    )


def _parse_article(article: Tag) -> RapWordsPost | None:
    """Parse a single <article> tag into a RapWordsPost."""
    words: list[FeaturedWord] = []
    lyrics_lines: list[str] = []
    artist = ""
    song_title = ""
    youtube_url = None
    tumblr_date = None

    # Extract date from h5 > a
    h5 = article.find("h5")
    if h5:
        date_link = h5.find("a")
        if date_link:
            tumblr_date = date_link.get_text(strip=True)

    # Find wiktionary links for word definitions
    wikt_links = [
        a for a in article.find_all("a")
        if "wiktionary" in (a.get("href", "") or "")
    ]

    for wikt_link in wikt_links:
        # Get the full text line containing this word definition
        # The definition text is a sibling/adjacent text node
        parent = wikt_link.parent
        if parent and parent.name in ("p", "article", "div"):
            # Get the full text of the parent element up to the next structural element
            full_text = parent.get_text(separator=" ", strip=True) if parent.name == "p" else None
            if full_text is None:
                # Word definition is directly in the article, not wrapped in <p>
                # Extract text from the link and its following siblings
                text_parts = [wikt_link.get_text()]
                for sibling in wikt_link.next_siblings:
                    if isinstance(sibling, Tag) and sibling.name in ("blockquote", "p", "h5", "article"):
                        break
                    if isinstance(sibling, Tag) and "wiktionary" in (sibling.get("href", "") or ""):
                        break
                    text = sibling.get_text() if isinstance(sibling, Tag) else str(sibling)
                    text_parts.append(text)
                full_text = "".join(text_parts).strip()

            if full_text:
                word = _parse_word_definition(full_text, wikt_link)
                if word:
                    words.append(word)

    # Identify which <p> tags are definitions, lyrics, or attribution
    # by collecting the wiktionary-link parents as definition paragraphs
    def_parents = {wikt_link.parent for wikt_link in wikt_links if wikt_link.parent}

    # Extract lyrics and attribution from remaining <p> tags
    # Lyrics: <p> with <br> tags (not a definition paragraph)
    # Attribution: <p> starting with "-" or em-dash
    # Also check for lyrics in <blockquote>
    blockquote = article.find("blockquote")
    if blockquote:
        p = blockquote.find("p")
        target = p if p else blockquote
        for br in target.find_all("br"):
            br.replace_with("\n")
        raw_text = target.get_text()
        lyrics_lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

    for p in article.find_all("p"):
        if p in def_parents:
            continue
        # Check if this is inside a blockquote (already handled)
        if p.find_parent("blockquote"):
            continue

        text = p.get_text(strip=True)

        # Attribution line
        if text.startswith("-") or text.startswith("\u2013") or text.startswith("\u2014"):
            match = re.match(r'^[-\u2013\u2014]\s*(.+?)\s+on\s+["\u201c]?(.+?)["\u201d]?\s*$', text)
            if match:
                artist = match.group(1).strip()
                song_title = match.group(2).strip()

            yt_link = p.find("a", href=re.compile(r"youtu"))
            if yt_link:
                youtube_url = yt_link.get("href")
                if not song_title:
                    song_title = yt_link.get_text(strip=True)
            continue

        # Lyrics line: has <br> tags and is not a definition
        if not lyrics_lines and p.find("br"):
            for br in p.find_all("br"):
                br.replace_with("\n")
            raw_text = p.get_text()
            lyrics_lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

    if not words and not lyrics_lines:
        return None

    youtube_video_id = _extract_video_id(youtube_url) if youtube_url else None

    return RapWordsPost(
        id=0,  # assigned later
        words=words,
        lyrics_lines=lyrics_lines,
        artist=artist,
        song_title=song_title,
        youtube_url=youtube_url,
        youtube_video_id=youtube_video_id,
        tumblr_date=tumblr_date,
    )


def scrape_page(page_num: int) -> list[RapWordsPost]:
    """Scrape a single page of rapwords.tumblr.com."""
    url = f"{TUMBLR_BASE_URL}/page/{page_num}" if page_num > 1 else TUMBLR_BASE_URL
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = soup.find_all("article")
    posts = []
    for article in articles:
        post = _parse_article(article)
        if post:
            posts.append(post)
    return posts


def scrape_all(callback=None) -> list[RapWordsPost]:
    """Scrape all pages and return posts with sequential IDs.

    Args:
        callback: Optional function called with (page_num, total_pages) for progress.
    """
    all_posts: list[RapWordsPost] = []

    for page in range(1, TUMBLR_TOTAL_PAGES + 1):
        if callback:
            callback(page, TUMBLR_TOTAL_PAGES)
        posts = scrape_page(page)
        all_posts.extend(posts)
        if page < TUMBLR_TOTAL_PAGES:
            time.sleep(0.5)  # be polite

    # Assign sequential IDs (oldest first)
    all_posts.reverse()
    for i, post in enumerate(all_posts, start=1):
        post.id = i

    return all_posts
