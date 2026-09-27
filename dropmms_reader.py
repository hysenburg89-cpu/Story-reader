#!/usr/bin/env python3
"""
DropMMS Clean Image Viewer
A Streamlit app to browse image galleries on dropmms.net without ads or popups.
"""

import re
from urllib.parse import urljoin, urlparse
import requests
import streamlit as st
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE = "https://dropmms.net"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://dropmms.net/",
}
TIMEOUT = 20

st.set_page_config(
    page_title="DropMMS Clean Viewer",
    page_icon="🖼️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def is_dropmms(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        return "dropmms.net" in host
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
    return re.sub(r"\s+", " ", text).strip()


def get_page_type(url: str) -> str:
    path = urlparse(url).path.lower()
    if "thread-" in path or "showthread" in path:
        return "thread"
    return "list"


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------
def parse_gallery_or_list(soup: BeautifulSoup, base_url: str) -> dict:
    """Extract threads/galleries and pagination from listing pages."""
    items = []
    seen_urls = set()

    for row in soup.select("tr"):
        link_candidates = row.select(
            "span[id^='tid_'] a, a[id^='tid_'], span.subject_old a, span.subject_new a, a[href*='thread-']"
        )
        for link in link_candidates:
            title = clean_text(link.get_text())
            href = urljoin(base_url, link.get("href", ""))

            if not title or title.isdigit() or href in seen_urls:
                continue

            if any(action in href for action in ["action=lastpost", "action=newpost", "page="]):
                continue

            # Look for thumbnail image inside the row if present
            def parse_gallery_or_list(soup: BeautifulSoup, base_url: str) -> dict:
    """Extract forum categories, threads/galleries, and pagination from listing pages."""
    items = []
    seen_urls = set()

    # 1. Look for Threads/Galleries first
    for row in soup.select("tr"):
        link_candidates = row.select(
            "span[id^='tid_'] a, a[id^='tid_'], span.subject_old a, span.subject_new a, td.trow1 a[href*='thread-'], td.trow2 a[href*='thread-']"
        )
        for link in link_candidates:
            title = clean_text(link.get_text())
            href = urljoin(base_url, link.get("href", ""))

            if not title or title.isdigit() or href in seen_urls:
                continue

            if any(action in href for action in ["action=lastpost", "action=newpost", "page="]):
                continue

            seen_urls.add(href)
            items.append({"type": "thread", "title": title, "url": href, "thumb": None})
            break

    # 2. Extract Forum/Category links (specifically for index pages like index2.php / forum.php)
    # Search for links containing 'forum-' or 'forumdisplay.php'
    category_links = soup.select("a[href*='forum-'], a[href*='forumdisplay.php'], strong a[href*='forum']")
    for a in category_links:
        title = clean_text(a.get_text())
        href = urljoin(base_url, a.get("href", ""))

        if not title or href in seen_urls:
            continue

        # Filter out breadcrumb / header navigation links
        if any(ignored in href for ignored in ["action=", "markread", "usercp", "search"]):
            continue

        seen_urls.add(href)
        items.append({"type": "forum", "title": title, "url": href, "thumb": None})

    # 3. Extract Pagination
    pages = []
    for a in soup.select(".pagination a, .pagination_page, a.pagination_next, a.pagination_last"):
        href = a.get("href")
        if not href:
            continue
        full = urljoin(base_url, href)
        label = clean_text(a.get_text()) or "Next"
        if full not in [p["url"] for p in pages]:
            pages.append({"label": label, "url": full})

    return {"items": items, "pages": pages}

        if not src:
            continue

        full_img_url = urljoin(base_url, src)

        # Skip UI icons, avatars, smilies, and buttons
        if any(ignored in full_img_url.lower() for ignored in ["smilies", "images/", "avatars", "button", "icon"]):
            continue

        if full_img_url not in seen_imgs:
            seen_imgs.add(full_img_url)
            images.append(full_img_url)

    # Check for direct image links wrapping thumbnails
    for a in soup.select("div.post_body a[href], div.post_content a[href]"):
        href = a.get("href", "")
        if href.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
            full_img_url = urljoin(base_url, href)
            if full_img_url not in seen_imgs:
                seen_imgs.add(full_img_url)
                images.append(full_img_url)

    # Thread Pagination
    pages = []
    for a in soup.select(".pagination a, .pagination_page, a.pagination_next, a.pagination_last"):
        href = a.get("href")
        if not href:
            continue
        full = urljoin(base_url, href)
        label = clean_text(a.get_text()) or "Next"
        if full not in [p["url"] for p in pages]:
            pages.append({"label": label, "url": full})

    return {"title": title, "images": images, "pages": pages}


# ---------------------------------------------------------------------------
# UI & Main Loop
# ---------------------------------------------------------------------------
def main():
    # Session state initialization
    if "history" not in st.session_state:
        st.session_state["history"] = []

    # Sidebar
    with st.sidebar:
        st.title("🖼️ DropMMS Viewer")
        st.caption("Clean image gallery browser")

        st.divider()
        st.markdown("**Quick Navigation**")

        def navigate_to(url_target):
            if st.session_state.get("last_loaded"):
                st.session_state["history"].append(st.session_state["last_loaded"])
            st.session_state["url"] = url_target
            st.rerun()

        if st.button("Home Index", use_container_width=True):
            navigate_to(f"{BASE}/index2.php")

    # Main Area UI
    st.title("DropMMS Image Gallery")

    default_url = st.session_state.get("url", f"{BASE}/index2.php")

    col1, col2, col3 = st.columns([4, 1, 1])
    with col1:
        url_input = st.text_input(
            "Paste URL",
            value=default_url,
            placeholder="https://dropmms.net/thread-12345.html",
            label_visibility="collapsed",
        )
    with col2:
        load = st.button("Load", type="primary", use_container_width=True)
    with col3:
        can_go_back = len(st.session_state["history"]) > 0
        if st.button("⬅ Back", disabled=not can_go_back, use_container_width=True):
            previous_url = st.session_state["history"].pop()
            st.session_state["url"] = previous_url
            st.session_state["last_loaded"] = None
            st.rerun()

    current_url = normalize_url(url_input)
    last_loaded = st.session_state.get("last_loaded")

    # Fetch data on button click or URL change
    if (load or (url_input and current_url != last_loaded)) and is_dropmms(current_url):
        if last_loaded and last_loaded != current_url:
            st.session_state["history"].append(last_loaded)

        st.session_state["url"] = current_url
        st.session_state["last_loaded"] = current_url

        with st.spinner("Fetching image content…"):
            html = fetch(current_url)
            if html:
                soup = BeautifulSoup(html, "lxml")
                page_type = get_page_type(current_url)

                if page_type == "thread":
                    data = parse_image_thread(soup, current_url)
                    st.session_state["thread_data"] = data
                    st.session_state["page_type"] = "thread"
                else:
                    data = parse_gallery_or_list(soup, current_url)
                    st.session_state["list_data"] = data
                    st.session_state["page_type"] = "list"
                    st.session_state["list_title"] = (
                        soup.title.get_text() if soup.title else "Galleries"
                    )

    # Render Content
    page_type = st.session_state.get("page_type")

    # Thread / Image View
    if page_type == "thread":
        data = st.session_state.get("thread_data", {})
        st.subheader(data.get("title", "Gallery"))

        images = data.get("images", [])
        pages = data.get("pages", [])

        # Display Thread Pagination
        if pages:
            st.markdown("**Pages:**")
            cols = st.columns(min(len(pages), 10))
            for i, p in enumerate(pages[:10]):
                with cols[i]:
                    if st.button(p["label"], key=f"thread_page_{i}", use_container_width=True):
                        navigate_to(p["url"])

        st.divider()

        if not images:
            st.info("No images detected in this thread.")
        else:
            # Render images in a 3-column responsive grid layout
            cols_per_row = 3
            grid_cols = st.columns(cols_per_row)

            for idx, img_url in enumerate(images):
                with grid_cols[idx % cols_per_row]:
                    st.image(img_url, use_container_width=True)

    # List / Gallery View
    elif page_type == "list":
        list_data = st.session_state.get("list_data", {})
        items = list_data.get("items", [])
        pages = list_data.get("pages", [])

        st.subheader(st.session_state.get("list_title", "Galleries"))

        if not items:
            st.info("No galleries found on this page.")
        else:
            for item in items:
                icon = "📁" if item["type"] == "forum" else "🖼️"
                if st.button(f"{icon}  {item['title']}", key=item["url"], use_container_width=True):
                    navigate_to(item["url"])

        # Display Gallery List Pagination
        if pages:
            st.divider()
            st.markdown("**Pages:**")
            cols = st.columns(min(len(pages), 10))
            for i, p in enumerate(pages[:10]):
                with cols[i]:
                    if st.button(p["label"], key=f"forum_page_{i}", use_container_width=True):
                        navigate_to(p["url"])

    else:
        st.info("Paste a dropmms.net URL above and click **Load** to start browsing images.")


if __name__ == "__main__":
    main()
