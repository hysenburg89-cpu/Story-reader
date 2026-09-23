#!/usr/bin/env python3
"""
Xossipy Clean Reader
A local Streamlit app to browse xossipy.com without ads/popups.
Features: dark/light mode, multi-page threads, save as .txt
"""

import re
import io
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
from datetime import datetime

import requests
import streamlit as st
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE = "https://xossipy.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://xossipy.com/",
}
TIMEOUT = 20

st.set_page_config(
    page_title="Xossipy Clean Reader",
    page_icon="?",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def is_xossipy(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        return "xossipy.com" in host
    except Exception:
        return False


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    return url


def fetch(url: str) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text
    except Exception as e:
        st.error(f"Failed to fetch page: {e}")
        return None


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_page_type(url: str) -> str:
    path = urlparse(url).path.lower()
    if "thread-" in path or "showthread" in path:
        return "thread"
    if "forum-" in path or path.rstrip("/").endswith("forum.php"):
        return "forum"
    if path in ("/", "/index.php", "/forum.php"):
        return "index"
    return "other"


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------
def parse_index_or_forum(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Extract forum categories or thread list."""
    items = []

    # Thread list (forum-*.html style)
    for row in soup.select("tr.inline_row, tr[class*='inline'], table.tborder tr"):
        link = row.select_one("a[href*='thread-']")
        if not link:
            continue
        title = clean_text(link.get_text())
        href = urljoin(base_url, link.get("href", ""))
        meta = clean_text(row.get_text())
        items.append({"type": "thread", "title": title, "url": href, "meta": meta[:120]})

    if items:
        return items

    # Category / forum list (forum.php)
    for a in soup.select("a[href*='forum-']"):
        title = clean_text(a.get_text())
        if not title or len(title) < 3:
            continue
        href = urljoin(base_url, a.get("href", ""))
        if any(x["url"] == href for x in items):
            continue
        items.append({"type": "forum", "title": title, "url": href, "meta": ""})

    return items


def parse_thread(soup: BeautifulSoup, base_url: str) -> dict:
    """Extract thread title, posts, and pagination."""
    title_el = soup.select_one("title")
    title = clean_text(title_el.get_text()) if title_el else "Untitled"
    title = re.sub(r"\s*[-|].*$", "", title).strip() or "Untitled"

    posts = []
    for post in soup.select("div.post"):
        author_el = post.select_one(
            ".post_author strong a, .author_information strong a, "
            ".post_author a, .author_information a, span.largetext a"
        )
        author = clean_text(author_el.get_text()) if author_el else "Anonymous"

        date_el = post.select_one(".post_date, span.post_date")
        date = clean_text(date_el.get_text()) if date_el else ""

        body_el = post.select_one(".post_body, .post_content")
        if not body_el:
            continue

        for junk in body_el.select("blockquote, .signature, script, style, .mycode_quote"):
            junk.decompose()

        body = body_el.get_text(separator="\n", strip=True)
        body = re.sub(r"\n{3,}", "\n\n", body)

        if body:
            posts.append({"author": author, "date": date, "body": body})

    # Pagination
    pages = []
    for a in soup.select(".pagination a, .pagination_page, a.pagination_next, a.pagination_last"):
        href = a.get("href")
        if not href:
            continue
        full = urljoin(base_url, href)
        label = clean_text(a.get_text()) or "Next"
        if full not in [p["url"] for p in pages]:
            pages.append({"label": label, "url": full})

    return {"title": title, "posts": posts, "pages": pages}


def posts_to_text(data: dict) -> str:
    lines = [
        data["title"],
        "=" * len(data["title"]),
        f"Fetched: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]
    for i, p in enumerate(data["posts"], 1):
        lines.append(f"--- Post #{i} by {p['author']} ({p['date']}) ---")
        lines.append(p["body"])
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
def apply_theme(dark: bool):
    if dark:
        st.markdown(
            """
            <style>
            .stApp { background-color: #0e1117; color: #e0e0e0; }
            .main .block-container { padding-top: 1.5rem; }
            h1, h2, h3 { color: #f0f0f0 !important; }
            .post-card {
                background: #1a1d24;
                border: 1px solid #2a2e38;
                border-radius: 10px;
                padding: 1.2rem 1.4rem;
                margin-bottom: 1.2rem;
            }
            .post-meta { color: #9aa0a6; font-size: 0.85rem; margin-bottom: 0.6rem; }
            .post-body { line-height: 1.65; white-space: pre-wrap; font-size: 1.05rem; }
            a { color: #7cb3ff !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <style>
            .post-card {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 10px;
                padding: 1.2rem 1.4rem;
                margin-bottom: 1.2rem;
            }
            .post-meta { color: #6c757d; font-size: 0.85rem; margin-bottom: 0.6rem; }
            .post-body { line-height: 1.65; white-space: pre-wrap; font-size: 1.05rem; }
            </style>
            """,
            unsafe_allow_html=True,
        )


def main():
    # Sidebar
    with st.sidebar:
        st.title("? Xossipy Reader")
        st.caption("Clean local reader ¨C no ads, no popups")

        dark = st.toggle("Dark mode", value=True)
        apply_theme(dark)

        st.divider()
        st.markdown("**Quick links**")
        if st.button("Forum Index", use_container_width=True):
            st.session_state["url"] = f"{BASE}/forum.php"
            st.rerun()
        if st.button("English Stories", use_container_width=True):
            st.session_state["url"] = f"{BASE}/forum-17.html"
            st.rerun()
        if st.button("Hindi Stories", use_container_width=True):
            st.session_state["url"] = f"{BASE}/forum-18.html"
            st.rerun()
        if st.button("Telugu Stories", use_container_width=True):
            st.session_state["url"] = f"{BASE}/forum-15.html"
            st.rerun()
        if st.button("Tamil Stories", use_container_width=True):
            st.session_state["url"] = f"{BASE}/forum-19.html"
            st.rerun()

        st.divider()
        st.markdown(
            """
            **How to use**
            1. Paste any xossipy.com URL  
            2. Click **Load**  
            3. Browse threads or read stories  
            4. Use **Save as TXT** to download
            """
        )

    # Main area
    st.title("Xossipy Clean Reader")

    default_url = st.session_state.get("url", f"{BASE}/forum.php")
    col1, col2 = st.columns([5, 1])
    with col1:
        url_input = st.text_input(
            "Paste URL",
            value=default_url,
            placeholder="https://xossipy.com/thread-12345.html",
            label_visibility="collapsed",
        )
    with col2:
        load = st.button("Load", type="primary", use_container_width=True)

    if load or (url_input and url_input != st.session_state.get("last_loaded")):
        url = normalize_url(url_input)
        if not is_xossipy(url):
            st.warning("Please enter a valid xossipy.com URL.")
            return

        st.session_state["url"] = url
        st.session_state["last_loaded"] = url

        with st.spinner("Fetching clean content¡­"):
            html = fetch(url)
            if not html:
                return
            soup = BeautifulSoup(html, "lxml")
            page_type = get_page_type(url)

            if page_type == "thread":
                data = parse_thread(soup, url)
                st.session_state["thread_data"] = data
                st.session_state["page_type"] = "thread"
            else:
                items = parse_index_or_forum(soup, url)
                st.session_state["list_items"] = items
                st.session_state["page_type"] = "list"
                st.session_state["list_title"] = soup.title.get_text() if soup.title else "Forum"

    # Render content
    page_type = st.session_state.get("page_type")

    if page_type == "thread":
        data = st.session_state.get("thread_data", {})
        st.subheader(data.get("title", "Thread"))

        # Save button
        txt = posts_to_text(data)
        st.download_button(
            label="? Save story as TXT",
            data=txt.encode("utf-8"),
            file_name=re.sub(r"[^\w\s-]", "", data.get("title", "story"))[:60].strip() + ".txt",
            mime="text/plain",
            use_container_width=False,
        )

        # Pagination
        pages = data.get("pages", [])
        if pages:
            st.markdown("**Pages:**")
            cols = st.columns(min(len(pages), 8))
            for i, p in enumerate(pages[:8]):
                with cols[i]:
                    if st.button(p["label"], key=f"page_{i}", use_container_width=True):
                        st.session_state["url"] = p["url"]
                        st.rerun()

        st.divider()

        for i, post in enumerate(data.get("posts", []), 1):
            st.markdown(
                f"""
                <div class="post-card">
                    <div class="post-meta">#{i} ¡¤ <b>{post['author']}</b> ¡¤ {post['date']}</div>
                    <div class="post-body">{post['body']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if not data.get("posts"):
            st.info("No posts found on this page. The site structure may have changed or the page requires login.")

    elif page_type == "list":
        items = st.session_state.get("list_items", [])
        st.subheader(st.session_state.get("list_title", "Forum"))

        if not items:
            st.info("No threads or forums detected. Try a different URL or open a specific category.")
        else:
            for item in items:
                icon = "?" if item["type"] == "forum" else "?"
                if st.button(f"{icon}  {item['title']}", key=item["url"], use_container_width=True):
                    st.session_state["url"] = item["url"]
                    st.rerun()

    else:
        st.info("Paste a xossipy.com URL above and click **Load** to start.")


if __name__ == "__main__":
    main()
