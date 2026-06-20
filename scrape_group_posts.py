"""
Facebook Group Post Scraper
Scrapes all posts from a Facebook group and saves to JSONL (crash-safe, per-post persistence)
"""
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
import time
import json
import signal
import sys
from datetime import datetime
import os
import re
import pickle
import hashlib
import glob as glob_mod
from getpass import getpass
from pathlib import Path


# Configuration
GROUP_URL = "https://www.facebook.com/groups/728006314041815"
# https://www.facebook.com/groups/3992285697768093
# Done 
# "https://www.facebook.com/groups/4085642185096154"

def _dedup_key(post_data):
    """Canonical dedup key: URL when present, else stable md5 of text prefix.
    Used identically in resume, feed, link, and article strategies."""
    url = post_data.get('url', '').strip()
    if url:
        return url
    text = post_data.get('text', '')[:120]
    return hashlib.md5(text.encode('utf-8', errors='replace')).hexdigest()


def _remember_post_id(post_data, seen_post_ids):
    """Record a post's numeric ID (from its URL) so the supplemental article
    scan can cheaply skip it on later rounds."""
    m = re.search(r'/posts/(\d+)', post_data.get('url', '') or '')
    if not m:
        m = re.search(r'story_fbid=(\d+)', post_data.get('url', '') or '')
    if m:
        seen_post_ids.add(m.group(1))


def _append_post_to_jsonl(post_data, jsonl_path):
    """Append a single post as one JSON line to a JSONL file.
    Crash-safe: each write is independent — if the process dies,
    all previously written posts are intact on disk."""
    with open(jsonl_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(post_data, ensure_ascii=False) + '\n')


BASE_DIR = Path(__file__).parent
OUTPUT_DIR = str(BASE_DIR / "output")
COOKIES_FILE = BASE_DIR / "fb_cookies.pkl"
PROFILE_DIR = str(BASE_DIR / "fb_group_scraper_profile")
MAX_SCROLL_ITERATIONS = 1000  # Small batch for testing
DEBUG_MODE = False  # Set to True to dump HTML samples for debugging

# Extract group ID from URL once
_GROUP_ID_MATCH = re.search(r'/groups/(\d+)', GROUP_URL)
GROUP_ID = _GROUP_ID_MATCH.group(1) if _GROUP_ID_MATCH else '1664454230462828'

# Crash-safe output: one JSONL file per group, each post appended immediately
OUTPUT_JSONL = os.path.join(OUTPUT_DIR, f"posts_{GROUP_ID}.jsonl")

# Shared regex patterns for cleaning UI noise from post text
_UI_CLEANUP_PATTERNS = [
    # Arabic UI elements
    r'عرض المزيد(?: من التعليقات| من الإجابات| من)?',
    r'عرض كل الردود',
    r'عرض  واحد',
    r'عرض  \d+',
    r'عرض كل الردود \(\d+\)',
    r'أعجبني', r'ردّ?', r'مشاركة',
    r'عرض الترجمة', r'تقييم هذه الترجمة', r'عرض الأصل',
    r'اكتب تعليقًا عامًا', r'اكتب إجابة',
    r'مهتم', r'متابعة', r'إلغاء المتابعة',
    r'مساهم صاعد', r'مساهم بارز', r'مشرف', r'خبير مجموعة',
    r'خبير مجموعة في[^$]*',
    # English UI elements
    r'See more', r'See More', r'Show more', r'Show more comments',
    r'Show all replies', r'Read more',
    r'Like', r'Reply', r'Share', r'Comment',
    r'Show translation', r'View original',
    r'Write a comment', r'Write an answer',
    r'Follow', r'Following', r'Unfollow',
    r'Group expert', r'Top contributor', r'Rising contributor',
    r'Interested', r'Going', r'Invite',
    # Both languages - contributor badges
    r'Rising contributor[^$]*',
    r'Top contributor[^$]*',
    # Time patterns
    r'·\s*[٠-٩]+\s*[دسسحhmd][\s\n]*',
    r'·\s*\d+\s*[dhmsy][\s\n]*',
    r'·\s*\d+\s*(?:hour|hours|hr|hrs|minute|min|minutes|day|days|week|weeks|month|months|year|years|just now|now|yesterday)[\s\n]*',
    r'·\s*[٠-٩]+\s*(?:ساعة|ساعات|دقيقة|دقائق|يوم|أيام|أسبوع|شهر|سنة|منذ)[\s\n]*',
    # Standalone numbers (reaction counts)
    r'^[\d٠-٩]+\s*[\n\s]+$',
    r'^\s*[\d٠-٩]+\s*\n',
    r'\n[\d٠-٩]+\s*$',
    # "·" separator on its own line
    r'^\s*·\s*$',
]

# Words that disqualify a first-line text from being an author name
_AUTHOR_BAD_WORDS = [
    'عرض', 'see', 'like', 'share', 'comment', 'more', 'http',
    'منذ', 'ago', 'ساعة', 'دقيقة', 'يوم', 'hour', 'min',
]

# Words that disqualify a link text from being an author name
_BAD_AUTHOR_WORDS = [
    'مشرف', 'خبير', 'مساهم', 'صاعد', 'بارز', 'متابعة', 'مهتم',
    'interested', 'follow', 'share', 'like', 'reply', 'comment',
    'more', 'show', 'عرض', 'اكتب', 'اقرأ', 'http', 'www',
    'منذ', 'ago', 'ساعة', 'دقيقة', 'يوم', 'hour', 'min', 'day',
    'group', 'expert', 'contributor', 'rising', 'posts',
]

# Map Arabic-Indic digits to ASCII so counts are stored consistently
_AR2EN_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')

# Bidi/zero-width marks that can prefix a count line (esp. Arabic/RTL)
_BIDI_MARKS = '‎‏‪‫‬‭‮​﻿'

# JS: return an element's innerText with nested comment replies
# (div[role="article"] descendants) removed, so post-level counts aren't
# polluted by numbers from individual comments.
_ENGAGEMENT_TEXT_JS = """
var el = arguments[0];
var clone = el.cloneNode(true);
clone.querySelectorAll('div[role="article"]').forEach(function(a){ a.remove(); });
return clone.innerText || '';
"""

# JS: find the comment/share COUNT elements directly. Facebook renders these as
# small clickable nodes whose ENTIRE text is the count, e.g. "8 comments" /
# "٨ تعليقات". Matching the whole node text (anchored) avoids grabbing body
# numbers or the reaction "…and 9009 others" line that flat innerText parsing
# was mistaking for comment counts. Nested comments are removed first.
_ENGAGEMENT_COUNTS_JS = r"""
var el = arguments[0];
var clone = el.cloneNode(true);
clone.querySelectorAll('div[role="article"]').forEach(function(a){ a.remove(); });
var nodes = clone.querySelectorAll('span, a, div[role="button"], div[role="link"]');
var res = {comments: '', shares: ''};
var strip = /[‎‏‪-‮​﻿]/g;
var reC = /^([0-9٠-٩][0-9٠-٩.,]*\s*[KkMm]?)\s*(?:comments?|تعليق\S*|كومنت\S*)$/i;
var reS = /^([0-9٠-٩][0-9٠-٩.,]*\s*[KkMm]?)\s*(?:shares?|مشارك\S*|مرة مشاركة)$/i;
for (var i = 0; i < nodes.length; i++) {
    var t = (nodes[i].textContent || '').replace(strip, '').trim();
    if (!t || t.length > 25) continue;
    var m;
    if (!res.comments && (m = reC.exec(t))) res.comments = m[1].replace(/\s+/g, '');
    if (!res.shares && (m = reS.exec(t))) res.shares = m[1].replace(/\s+/g, '');
    if (res.comments && res.shares) break;
}
return JSON.stringify(res);
"""


def _to_ascii_digits(s):
    """Normalize Arabic-Indic digits to ASCII; leave the rest untouched."""
    return s.translate(_AR2EN_DIGITS)


def _parse_engagement_text(text):
    """Parse comment and share counts from a post's visible text.

    Facebook renders these as short lines that begin with the count, e.g.
    "12 comments 3 shares" or "١٢ تعليقًا". We only consider short,
    number-leading lines to avoid matching prose in the post body or the
    "View N more comments" expander.

    Returns: (comments, shares) as ASCII-digit strings, e.g. ('12', '3').
    """
    comments = ''
    shares = ''
    # Phrases that mark a non-count line (e.g. "View 3 more comments")
    skip_words = ('more', 'view', 'most relevant', 'write', 'be the first',
                  'عرض', 'المزيد', 'أهم', 'اكتب', 'كن أول')

    for raw_line in text.split('\n'):
        line = raw_line.strip().strip(_BIDI_MARKS).strip()
        # Count lines are short and start with the number itself
        if not line or len(line) > 40 or not re.match(r'^[\d٠-٩]', line):
            continue
        low = line.lower()
        if any(w in low for w in skip_words):
            continue

        if not comments:
            m = re.search(r'(\d[\d,\.]*\s*[KkMm]?)\s*(?:comments?\b|تعليق)', line)
            if m:
                comments = _to_ascii_digits(m.group(1).replace(' ', '').rstrip('.,'))
        if not shares:
            m = re.search(r'(\d[\d,\.]*\s*[KkMm]?)\s*(?:shares?\b|مشاركات?|مشاركة)', line)
            if m:
                shares = _to_ascii_digits(m.group(1).replace(' ', '').rstrip('.,'))
        if comments and shares:
            break

    return comments, shares


def _extract_engagement_counts(element, driver):
    """Return (comments, shares) for a post element.

    Primary: anchored DOM-text matching — an element whose ENTIRE text is a
    count like "8 comments" / "٨ تعليقات". This is far more reliable than
    parsing flattened innerText, which was grabbing body numbers and the
    reaction "…and N others" line.

    Fallback: line-based parsing of the innerText (with nested comments
    removed) when the anchored pass finds nothing.
    """
    comments = ''
    shares = ''

    if driver is not None:
        try:
            raw = driver.execute_script(_ENGAGEMENT_COUNTS_JS, element)
            data = json.loads(raw) if raw else {}
            comments = _to_ascii_digits((data.get('comments') or '').strip())
            shares = _to_ascii_digits((data.get('shares') or '').strip())
        except Exception:
            pass

    if comments and shares:
        return comments, shares

    # Fallback for whatever the anchored pass missed
    try:
        if driver is not None:
            text = driver.execute_script(_ENGAGEMENT_TEXT_JS, element) or ''
        else:
            text = element.text or ''
        c, s = _parse_engagement_text(text)
        comments = comments or c
        shares = shares or s
    except Exception:
        pass

    return comments, shares


# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)


def debug_dump_elements(driver, max_elements=3):
    """Save HTML of first few article/feed elements for debugging DOM structure."""
    try:
        print(f"\n🔍 DEBUG: Analyzing page DOM structure...")

        # Check feed container
        try:
            feed = driver.find_element(By.CSS_SELECTOR, 'div[role="feed"]')
            feed_children = feed.find_elements(By.XPATH, './div')
            print(f"   ✅ div[role='feed'] found! {len(feed_children)} direct children")
            for i, child in enumerate(feed_children[:5]):
                try:
                    html = child.get_attribute('innerHTML') or ''
                    has_article = len(child.find_elements(By.CSS_SELECTOR, 'div[role="article"]'))
                    text_preview = (child.text or '')[:60].replace('\n', ' ')
                    # Find post links
                    post_links = child.find_elements(By.CSS_SELECTOR, 'a[href*="/posts/"]')
                    has_post_link = any('comment_id=' not in (l.get_attribute('href') or '') for l in post_links)
                    print(f"   Feed child {i}: html_len={len(html)}, articles_inside={has_article}, has_post_link={has_post_link}")
                    print(f"      text: {text_preview!r}")
                except Exception as e:
                    print(f"   Feed child {i}: error - {e}")
        except Exception:
            print(f"   ❌ div[role='feed'] NOT found")

        # Check article elements
        articles = driver.find_elements(By.CSS_SELECTOR, 'div[role="article"]')
        print(f"\n   div[role='article'] elements: {len(articles)}")

        # Count how many have comment_id vs not
        comment_count = 0
        post_count = 0
        for article in articles:
            try:
                links = article.find_elements(By.TAG_NAME, 'a')
                has_post_link = False
                for link in links[:10]:
                    href = link.get_attribute('href') or ''
                    if '/posts/' in href and 'comment_id=' not in href:
                        has_post_link = True
                        break
                if has_post_link:
                    post_count += 1
                else:
                    comment_count += 1
            except Exception:
                pass
        print(f"   Articles: {post_count} with post links, {comment_count} with only comment links")

        # Also try alternative selectors
        alt_selectors = [
            ('div[data-pagelet]', By.CSS_SELECTOR),
            ("//div[@role='article']//div[@dir='auto']", By.XPATH),
        ]
        for sel_name, sel_by in alt_selectors:
            try:
                elems = driver.find_elements(sel_by, sel_name)
                if elems:
                    print(f"   Selector '{sel_name}': found {len(elems)} elements")
            except Exception:
                pass

        # Dump HTML of first 3 articles
        for i, article in enumerate(articles[:max_elements]):
            try:
                html = article.get_attribute('innerHTML') or ''
                debug_file = os.path.join(OUTPUT_DIR, f'debug_article_{i}.html')
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(html)
                text_preview = article.text[:100] if article.text else "(EMPTY)"
                print(f"   Article {i}: text={text_preview!r}, html_len={len(html)}, saved to {debug_file}")
            except Exception as e:
                print(f"   Article {i}: error - {e}")

        # Also dump first feed child HTML
        try:
            feed = driver.find_element(By.CSS_SELECTOR, 'div[role="feed"]')
            children = feed.find_elements(By.XPATH, './div')
            for i, child in enumerate(children[:2]):
                try:
                    html = child.get_attribute('innerHTML') or ''
                    if len(html) > 1000:
                        debug_file = os.path.join(OUTPUT_DIR, f'debug_feed_unit_{i}.html')
                        with open(debug_file, 'w', encoding='utf-8') as f:
                            f.write(html)
                        print(f"   Feed unit {i}: html_len={len(html)}, saved to {debug_file}")
                except Exception as e:
                    print(f"   Feed unit {i}: error - {e}")
        except Exception:
            pass

    except Exception as e:
        print(f"🔍 DEBUG error: {e}")


def save_cookies(driver):
    """Save browser cookies to file for session reuse"""
    try:
        cookies = driver.get_cookies()
        with open(COOKIES_FILE, 'wb') as f:
            pickle.dump(cookies, f)
        print(f"✓ Cookies saved ({len(cookies)} cookies)")
        return True
    except Exception as e:
        print(f"⚠️ Could not save cookies: {e}")
        return False


def load_cookies(driver):
    """Load saved cookies into browser. Returns True if cookies were loaded."""
    if not COOKIES_FILE.exists():
        print("ℹ️ No saved cookies found")
        return False

    try:
        # Must be on Facebook domain before adding cookies
        driver.get("https://www.facebook.com")
        time.sleep(3)

        with open(COOKIES_FILE, 'rb') as f:
            cookies = pickle.load(f)

        for cookie in cookies:
            try:
                # Remove fields that cause issues
                cookie.pop('sameSite', None)
                cookie.pop('storeId', None)
                cookie.pop('session', None)
                # Ensure domain matches
                if 'domain' in cookie and 'facebook' in cookie['domain']:
                    driver.add_cookie(cookie)
            except Exception:
                continue

        print(f"✓ Loaded {len(cookies)} saved cookies")
        return True
    except Exception as e:
        print(f"⚠️ Could not load cookies: {e}")
        return False


def is_logged_in(driver):
    """Check if the user is currently logged into Facebook.
    Returns True if logged in, False otherwise."""
    try:
        driver.get("https://www.facebook.com")
        time.sleep(5)

        # Check for login form — if we see an email/password field, we're NOT logged in
        login_indicators = [
            # Email/phone input field
            lambda: driver.find_elements(By.CSS_SELECTOR, 'input[name="email"]'),
            # Password input field
            lambda: driver.find_elements(By.CSS_SELECTOR, 'input[name="pass"]'),
            # Login button
            lambda: driver.find_elements(By.CSS_SELECTOR, 'button[name="login"]'),
            # "Log In" text in button
            lambda: driver.find_elements(By.XPATH, '//button[contains(text(), "Log In")]'),
            lambda: driver.find_elements(By.XPATH, '//button[contains(text(), "تسجيل الدخول")]'),
        ]

        for check in login_indicators:
            elements = check()
            if elements:
                return False  # Login form visible = not logged in

        # Check for indicators that we ARE logged in
        logged_in_indicators = [
            lambda: driver.find_elements(By.CSS_SELECTOR, '[aria-label="Account"]'),
            lambda: driver.find_elements(By.CSS_SELECTOR, '[aria-label="الحساب"]'),
            lambda: driver.find_elements(By.CSS_SELECTOR, '[data-pagelet="LeftRail"]'),
            lambda: driver.find_elements(By.CSS_SELECTOR, '[role="navigation"]'),
        ]

        for check in logged_in_indicators:
            elements = check()
            if elements:
                return True

        # If we can't determine, check the URL — redirect away from login means logged in
        current_url = driver.current_url
        if 'login' not in current_url.lower():
            return True

        return False
    except Exception as e:
        print(f"⚠️ Error checking login status: {e}")
        return False


def _is_logged_in_lightweight(driver):
    """Lightweight login check that does NOT navigate away.
    Inspects current page DOM/URL only — safe to call in loops (e.g. 2FA wait).
    """
    try:
        # If URL still has checkpoint/two-factor, user hasn't completed 2FA yet
        current_url = driver.current_url.lower()
        if 'checkpoint' in current_url or 'two-factor' in current_url:
            return False

        # Look for logged-in indicators on the current page
        for selector in ['[aria-label="Account"]', '[aria-label="الحساب"]',
                         '[data-pagelet="LeftRail"]', '[role="navigation"]']:
            if driver.find_elements(By.CSS_SELECTOR, selector):
                return True

        # If we moved away from login/checkpoint pages, likely logged in
        if 'login' not in current_url:
            return True

        return False
    except Exception:
        return False


def login_to_facebook(driver):
    """Log into Facebook using email/password. Handles 2FA if needed."""
    try:
        print("\n🔐 Facebook Login Required")
        print("=" * 40)

        # Navigate to login page
        driver.get("https://www.facebook.com/login")
        time.sleep(3)

        # Get credentials from user (password is hidden)
        email = input("📧 Enter your Facebook email or phone: ").strip()
        password = getpass("🔑 Enter your Facebook password (hidden): ")

        if not email or not password:
            print("❌ Email and password are required.")
            return False

        # Fill in email field
        try:
            email_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="email"]'))
            )
            email_field.clear()
            email_field.send_keys(email)
            time.sleep(0.5)
        except Exception as e:
            print(f"❌ Could not find email field: {e}")
            return False

        # Fill in password field
        try:
            pass_field = driver.find_element(By.CSS_SELECTOR, 'input[name="pass"]')
            pass_field.clear()
            pass_field.send_keys(password)
            time.sleep(0.5)
        except Exception as e:
            print(f"❌ Could not find password field: {e}")
            return False

        # Click login button
        try:
            login_btn = driver.find_element(By.CSS_SELECTOR, 'button[name="login"]')
            login_btn.click()
        except Exception:
            # Try pressing Enter as fallback
            pass_field.send_keys(Keys.RETURN)

        print("⏳ Logging in...")
        time.sleep(8)  # Wait for login to process

        # Check for 2FA / checkpoint
        current_url = driver.current_url.lower()
        page_source = driver.page_source.lower()

        if 'two-factor' in current_url or 'two-factor' in page_source or 'checkpoint' in current_url:
            print("\n🔒 Two-Factor Authentication (2FA) detected!")
            print("Please complete the 2FA process in the browser window.")
            print("Waiting for you to finish...")

            # Wait up to 120 seconds for 2FA completion
            for i in range(120):
                time.sleep(1)
                try:
                    # Use lightweight check — is_logged_in() navigates away!
                    if _is_logged_in_lightweight(driver):
                        print("\n✓ 2FA completed successfully!")
                        break
                except Exception:
                    continue
            else:
                print("⚠️ 2FA timeout — took longer than 120 seconds.")

        # Check for "Save Login Info" prompt and dismiss it
        try:
            not_now_buttons = driver.find_elements(By.XPATH,
                '//button[contains(text(), "Not Now") or contains(text(), "ليس الآن")]')
            if not_now_buttons:
                not_now_buttons[0].click()
                time.sleep(2)
        except Exception:
            pass

        # Verify login
        if is_logged_in(driver):
            print("✅ Login successful!")
            save_cookies(driver)
            return True
        else:
            print("❌ Login failed. Please try again or log in manually.")
            print("💡 You can log in manually in the browser window, then press Enter here...")
            input("   Press Enter once you've logged in manually → ")
            if is_logged_in(driver):
                print("✅ Manual login confirmed!")
                save_cookies(driver)
                return True
            return False

    except Exception as e:
        print(f"❌ Login error: {e}")
        return False


def _clean_post_id(element):
    """Return the numeric post ID from an element's first clean permalink
    (a /posts/ or permalink.php link WITHOUT comment_id=), else ''.

    Used as a cheap pre-dedup so the supplemental article scan doesn't
    re-extract posts we've already saved this run.
    """
    try:
        for link in element.find_elements(By.TAG_NAME, 'a'):
            try:
                href = link.get_attribute('href') or ''
                if 'comment_id=' in href:
                    continue
                m = re.search(r'/posts/(\d+)', href)
                if m:
                    return m.group(1)
                m = re.search(r'story_fbid=(\d+)', href)
                if m:
                    return m.group(1)
            except StaleElementReferenceException:
                break
            except Exception:
                continue
    except Exception:
        pass
    return ''


def find_post_elements_via_links(driver):
    """Find post containers by locating their permalink links.

    This is more reliable than finding div[role='article'] because
    comments are also div[role='article'] but have comment_id= in their links.

    Returns: list of (post_id, container_element) tuples
    """
    posts_found = []
    seen_ids = set()

    try:
        # Find all links that point to posts (not comments)
        all_links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/posts/"]')

        for link in all_links:
            try:
                href = link.get_attribute('href') or ''
                # Skip comment links
                if 'comment_id=' in href:
                    continue

                # Extract post ID
                match = re.search(r'/posts/(\d+)', href)
                if not match:
                    continue
                post_id = match.group(1)

                if post_id in seen_ids:
                    continue
                seen_ids.add(post_id)

                # Find the parent container - try multiple strategies
                container = None

                # Try 1: ancestor div[role="article"] (post might be in an article)
                try:
                    container = link.find_element(By.XPATH, './ancestor::div[@role="article"][1]')
                except Exception:
                    pass

                # Try 2: If not in article, go up to find a meaningful container
                # The timestamp link is typically a few levels deep inside the feed unit
                if not container:
                    try:
                        # Navigate up from the link: link -> span -> div -> div(feed unit)
                        # Try going up 4-6 levels to find a substantial container
                        for depth in [4, 5, 6, 7]:
                            try:
                                candidate = link.find_element(By.XPATH, f'./ancestor::div[{depth}]')
                                html_len = len(candidate.get_attribute('innerHTML') or '')
                                # Feed units are substantial (typically >5000 chars)
                                if html_len > 5000:
                                    container = candidate
                                    break
                            except Exception:
                                continue
                    except Exception:
                        pass

                if container:
                    posts_found.append((post_id, container))

            except StaleElementReferenceException:
                continue
            except Exception:
                continue

    except Exception as e:
        if DEBUG_MODE:
            print(f"   ⚠️ find_post_elements_via_links error: {e}")

    return posts_found


def find_posts_via_feed(driver):
    """Find posts by looking at the Facebook feed structure.

    In Facebook groups, div[role="feed"] contains direct children,
    each of which is a feed unit (one post + its comments).
    The post content is directly in the feed unit, while comments
    are in nested div[role="article"] elements.

    Returns: list of (post_id, feed_unit_element) tuples
    """
    posts_found = []
    seen_ids = set()

    try:
        feed = driver.find_element(By.CSS_SELECTOR, 'div[role="feed"]')
        # Get direct children (feed units)
        feed_units = feed.find_elements(By.XPATH, './div')

        if DEBUG_MODE:
            print(f"   📋 Feed found: {len(feed_units)} feed units")

        for unit in feed_units:
            try:
                html = unit.get_attribute('innerHTML') or ''
                # Skip only genuine skeleton/placeholder units: tiny AND
                # link-less. Real posts — even short or image-only ones — always
                # carry author/timestamp anchor links, so the old flat
                # len(html) < 3000 cutoff was dropping short posts.
                if len(html) < 1500 and not unit.find_elements(By.TAG_NAME, 'a'):
                    continue

                # Find the post URL from this feed unit
                # Facebook groups don't always have a direct /posts/ link for the post.
                # The post's timestamp link uses obfuscated __cft__ URLs.
                # Comment links DO have /posts/POST_ID/?comment_id=... format.
                # We extract the post ID from those comment links.
                post_url = ''
                post_timestamp = ''

                links = unit.find_elements(By.TAG_NAME, 'a')
                for link in links:
                    try:
                        href = link.get_attribute('href') or ''
                        # Look for post permalink (NOT comment link)
                        if '/posts/' in href and 'comment_id=' not in href:
                            post_url = href
                            link_text = (link.text or '').strip()
                            if link_text and len(link_text) < 30 and not any(
                                s in link_text.lower() for s in ['facebook', 'http', 'share', 'مشاركة']
                            ):
                                post_timestamp = link_text
                            break  # Found the post link
                    except Exception:
                        continue

                # If no direct post link found, extract from comment links
                if not post_url:
                    for link in links:
                        try:
                            href = link.get_attribute('href') or ''
                            if '/posts/' in href and 'comment_id=' in href:
                                # Extract base URL from comment link
                                match = re.match(r'(https?://[^/]+/groups/[^/]+/posts/\d+/)', href)
                                if match:
                                    post_url = match.group(1)
                                else:
                                    # Extract post ID and construct URL
                                    post_id_match = re.search(r'/posts/(\d+)', href)
                                    if post_id_match:
                                        post_url = f'https://www.facebook.com/groups/{GROUP_ID}/posts/{post_id_match.group(1)}/'
                                break
                        except Exception:
                            continue

                # Extract post ID from URL
                post_id = ''
                if post_url:
                    match = re.search(r'/posts/(\d+)', post_url)
                    if match:
                        post_id = match.group(1)

                # If no post URL found, try to get from permalink.php links
                if not post_id:
                    for link in links:
                        try:
                            href = link.get_attribute('href') or ''
                            if '/permalink.php' in href and 'comment_id=' not in href:
                                match = re.search(r'story_fbid=(\d+)', href)
                                if match:
                                    post_id = match.group(1)
                                    post_url = href
                                    break
                        except Exception:
                            continue

                # Skip if already seen
                if post_id and post_id in seen_ids:
                    continue

                # If no post ID from URL, use content hash for dedup
                if not post_id:
                    # Use first 200 chars of non-comment text as hash input
                    post_id = hashlib.md5(html[:200].encode('utf-8', errors='replace')).hexdigest()

                if post_id in seen_ids:
                    continue

                seen_ids.add(post_id)
                posts_found.append((post_id, unit))

            except StaleElementReferenceException:
                continue
            except Exception:
                continue

    except Exception as e:
        if DEBUG_MODE:
            print(f"   ⚠️ find_posts_via_feed error: {e}")

    return posts_found


def extract_post_text_js(feed_unit, driver):
    """Extract post body text from a feed unit using JavaScript.

    Removes all div[role="article"] elements (comments) from a clone,
    then extracts the remaining text, which should be the post content.

    Returns: str - the post body text
    """
    try:
        script = """
        var unit = arguments[0];
        var clone = unit.cloneNode(true);
        // Remove all div[role="article"] from the clone (these are comments)
        var articles = clone.querySelectorAll('div[role="article"]');
        articles.forEach(function(a) { a.remove(); });

        // IMPORTANT: the clone is detached from the document, so innerText is
        // unreliable — on a non-rendered node it collapses to textContent and
        // drops the line breaks between block elements, merging words across
        // lines (e.g. "عليكم" + "ممكن" -> "عليكمممكن"). So insert explicit
        // newlines for <br> and block elements, then read textContent.
        function blockText(el) {
            var c = el.cloneNode(true);
            c.querySelectorAll('br').forEach(function(br) {
                br.replaceWith(document.createTextNode('\\n'));
            });
            c.querySelectorAll('div,p,li,h1,h2,h3,h4,h5,h6').forEach(function(b) {
                b.appendChild(document.createTextNode('\\n'));
            });
            return (c.textContent || '').replace(/\\n{3,}/g, '\\n\\n');
        }

        // Find div[dir="auto"] elements in the cleaned clone
        var dirAutos = clone.querySelectorAll('div[dir="auto"]');
        var bestText = '';
        for (var i = 0; i < dirAutos.length; i++) {
            var t = blockText(dirAutos[i]).trim();
            if (t.length > bestText.length && t.length > 5) {
                bestText = t;
            }
        }
        if (bestText) return bestText;
        // Fallback: try span[dir="auto"]
        var spans = clone.querySelectorAll('span[dir="auto"]');
        for (var i = 0; i < spans.length; i++) {
            var t = blockText(spans[i]).trim();
            if (t.length > bestText.length && t.length > 5) {
                bestText = t;
            }
        }
        if (bestText) return bestText;
        // Last resort: all remaining text
        return blockText(clone).trim().substring(0, 2000);
        """
        return driver.execute_script(script, feed_unit) or ''
    except Exception:
        return ''


def extract_post_data_from_feed_unit(unit, idx, driver):
    """Extract post data from a feed unit element (post + comments container).

    Uses JavaScript-based text extraction to get only the post text,
    not comment text.
    """
    post_data = {
        'index': idx,
        'text': '',
        'author': '',
        'timestamp': '',
        'url': '',
        'likes': '',
        'comments': '',
        'shares': '',
        'images': [],
        'is_video': False,
        'is_share': False
    }

    # --- Extract post body text (excluding comments) ---
    raw_text = extract_post_text_js(unit, driver)

    # Fallback: if JS extraction failed, try data-ad-preview/message selector
    if not raw_text or len(raw_text) < 10:
        try:
            msg_blocks = unit.find_elements(By.CSS_SELECTOR,
                '[data-ad-rendering-role="story_message"], [data-ad-preview="message"], [data-ad-comet-preview="message"]')
            if msg_blocks:
                best = ""
                for block in msg_blocks:
                    try:
                        t = block.text or ""
                        if len(t) > len(best):
                            best = t
                    except StaleElementReferenceException:
                        raise
                    except Exception:
                        continue
                if len(best) > len(raw_text):
                    raw_text = best
        except StaleElementReferenceException:
            pass
        except Exception:
            pass

    # Clean UI patterns from text
    cleaned_text = raw_text
    for pattern in _UI_CLEANUP_PATTERNS:
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE | re.MULTILINE)

    cleaned_text = re.sub(r'\n{2,}', '\n', cleaned_text)
    cleaned_text = re.sub(r'^\s+|\s+$', '', cleaned_text, flags=re.MULTILINE)
    cleaned_text = cleaned_text.strip()

    # Try to extract author from first line (tentative — don't strip from text yet)
    _heuristic_author = ''
    if cleaned_text:
        lines = cleaned_text.split('\n')
        if lines:
            first_line = lines[0].strip()
            if (2 < len(first_line) < 60 and
                not any(bad in first_line.lower() for bad in _AUTHOR_BAD_WORDS) and
                not re.match(r'^[\d٠-٩]+$', first_line)):
                _heuristic_author = first_line

    post_data['text'] = cleaned_text

    # Check video/share
    text_lower = cleaned_text.lower()
    post_data['is_video'] = 'shared a video' in text_lower or 'شارك فيديو' in text_lower
    post_data['is_share'] = 'shared a post' in text_lower or 'شارك منشور' in text_lower

    # --- Extract metadata from the feed unit ---

    # Get post URL — prefer non-comment links, but if none found,
    # extract post ID from comment links and construct the URL
    try:
        links = unit.find_elements(By.TAG_NAME, 'a')  # cached for reuse below
        post_link_found = False
        for link in links:
            try:
                href = link.get_attribute('href') or ''
                # Phase 1: Look for post permalink WITHOUT comment_id=
                if ('/posts/' in href or '/permalink.php' in href) and 'comment_id=' not in href:
                    post_data['url'] = href
                    link_text = (link.text or '').strip()
                    if link_text and len(link_text) < 30 and not post_data['timestamp']:
                        if not any(s in link_text.lower() for s in ['facebook', 'http', 'share', 'مشاركة']):
                            post_data['timestamp'] = link_text
                    post_link_found = True
                    break
            except StaleElementReferenceException:
                continue
            except Exception:
                continue

        # Phase 2: If no post link, extract post ID from a comment link
        if not post_link_found:
            for link in links:
                try:
                    href = link.get_attribute('href') or ''
                    if '/posts/' in href and 'comment_id=' in href:
                        # Extract the base post URL from the comment link
                        match = re.match(r'(https?://[^/]+/groups/[^/]+/posts/\d+/)', href)
                        if match:
                            post_data['url'] = match.group(1)
                            break
                        # Fallback: extract post ID and construct URL
                        post_id_match = re.search(r'/posts/(\d+)', href)
                        if post_id_match:
                            post_data['url'] = f'https://www.facebook.com/groups/{GROUP_ID}/posts/{post_id_match.group(1)}/'
                            break
                except StaleElementReferenceException:
                    continue
                except Exception:
                    continue
    except Exception:
        pass

    # Get author — try data-ad-rendering-role="profile_name" first (most reliable)
    try:
        profile_elements = unit.find_elements(By.CSS_SELECTOR,
            '[data-ad-rendering-role="profile_name"] a, h2 a, h3 a')
        for elem in profile_elements:
            try:
                text = (elem.text or '').strip()
                href = elem.get_attribute('href') or ''
                if text and 2 < len(text) < 60 and '/posts/' not in href:
                    post_data['author'] = text
                    break
            except StaleElementReferenceException:
                continue
            except Exception:
                continue
    except Exception:
        pass

    # Fallback: get author from link elements (reuse cached links)
    if not post_data['author']:
        try:
            # Re-fetch links in case previous list went stale
            author_links = unit.find_elements(By.TAG_NAME, 'a')
            for link in author_links[:30]:
                try:
                    href = link.get_attribute('href') or ''
                    text = (link.text or '').strip()
                    if (text and 2 < len(text) < 60 and
                        not any(bad in text.lower() for bad in _BAD_AUTHOR_WORDS) and
                        '/posts/' not in href and '/permalink.php' not in href and
                        '?' not in text and ':' not in text and
                        ('facebook.com' in href or '/profile.php' in href or '/user/' in href or '/groups/' in href)):
                        post_data['author'] = text
                        break
                except StaleElementReferenceException:
                    continue
                except Exception:
                    continue
        except Exception:
            pass

    # Get reaction (likes) count from aria-labels (e.g. "25 reactions")
    try:
        interaction_elements = unit.find_elements(By.CSS_SELECTOR, '[aria-label]')
        for elem in interaction_elements:
            try:
                aria_label = elem.get_attribute('aria-label') or ''
                label_lower = aria_label.lower()
                if 'like' in label_lower or 'react' in label_lower or 'اعجب' in aria_label or 'أعجب' in aria_label:
                    num_match = re.search(r'([\d,٠-٩\.]+\s*[KkMm]?)', aria_label)
                    if num_match and not post_data['likes']:
                        post_data['likes'] = _to_ascii_digits(num_match.group(1).replace(' ', ''))
            except Exception:
                continue
    except Exception:
        pass

    # Get comment & share counts via anchored count-element matching
    # (far more reliable than action-button aria-labels or innerText lines).
    try:
        c, s = _extract_engagement_counts(unit, driver)
        if c:
            post_data['comments'] = c
        if s:
            post_data['shares'] = s
    except Exception:
        pass

    # Get images
    try:
        images = unit.find_elements(By.TAG_NAME, 'img')
        for img in images:
            try:
                src = img.get_attribute('src') or ''
                if src and 'fbcdn.net' in src and 'profile' not in src and 'emoji' not in src and 'rsrc.php' not in src:
                    if 'scontent' in src and src not in post_data['images']:
                        post_data['images'].append(src)
            except Exception:
                continue
    except Exception:
        pass

    # Fallback: use heuristic author from first line (only if no DOM-based author found)
    if not post_data['author'] and _heuristic_author:
        post_data['author'] = _heuristic_author

    # Only strip confirmed author from the start of text
    if post_data['author'] and post_data['text'].startswith(post_data['author'] + '\n'):
        post_data['text'] = post_data['text'][len(post_data['author']):].strip()

    return post_data


def scroll_down(driver, distance=2000):
    """Aggressive scroll down to find more posts quickly"""
    driver.execute_script(f"window.scrollBy(0, {distance});")
    time.sleep(0.5)  # Shorter pause for faster scrolling


def click_all_show_more_buttons(post, driver):
    """Click ALL 'See More' buttons in a post for complete expansion"""
    try:
        # Find all clickable elements
        all_clickable = post.find_elements(By.CSS_SELECTOR, "[role='button'], span[role='button']")
        buttons_clicked = 0

        for button in all_clickable:
            try:
                text = button.text.strip() if button.text else ""
                # Check if this button contains "See More" patterns
                if text and (
                    'عرض المزيد' in text or
                    'See more' in text or
                    'See More' in text or
                    'عرض المزيد من' in text or
                    'عرض كل' in text or
                    'Read more' in text
                ):
                    if button.is_displayed():
                        # Scroll to button
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", button)
                        time.sleep(0.2)

                        # Click the button
                        try:
                            driver.execute_script("arguments[0].click();", button)
                            time.sleep(0.4)
                            buttons_clicked += 1
                        except Exception:
                            try:
                                button.click()
                                time.sleep(0.4)
                                buttons_clicked += 1
                            except Exception:
                                pass
            except Exception:
                continue

        return buttons_clicked > 0
    except Exception:
        pass
    return False


def _is_comment_article(article):
    """Determine if a div[role='article'] is a comment (not a top-level post).

    Post articles have at least one /posts/ link WITHOUT comment_id=.
    Comment articles only have /posts/ links WITH comment_id=.
    Falls back to heuristics if no /posts/ links are found.
    """
    try:
        links = article.find_elements(By.TAG_NAME, 'a')
        has_post_link = False    # /posts/ WITHOUT comment_id=
        has_comment_link = False # /posts/ WITH comment_id=

        for link in links:
            try:
                href = link.get_attribute('href') or ''
                if '/posts/' in href or '/permalink.php' in href:
                    if 'comment_id=' in href:
                        has_comment_link = True
                    else:
                        has_post_link = True
                        break  # Found a clean post link → it's a post
            except StaleElementReferenceException:
                raise
            except Exception:
                continue

        # Clear cases
        if has_post_link:
            return False  # Has a clean post permalink → it's a top-level post
        if has_comment_link:
            return True   # Only has comment links → it's a comment

        # No /posts/ links at all — use heuristics
        try:
            html = article.get_attribute('innerHTML') or ''
            text = article.text or ''

            # Posts are large; comments are small
            if len(html) < 3000:
                return True  # Too small to be a post

            # Comments have "Reply" action; posts have "Comment" action
            has_reply = bool(re.search(r'\bReply\b', text))
            has_reply_ar = bool(re.search(r'ردّ?\b', text))
            has_comment_action = bool(re.search(r'\bComment\b', text))
            has_comment_action_ar = bool(re.search(r'تعليق', text))

            if (has_reply or has_reply_ar) and not (has_comment_action or has_comment_action_ar):
                return True  # Reply without Comment → comment
            if (has_comment_action or has_comment_action_ar) and len(html) > 5000:
                return False  # Comment action + large → post
        except Exception:
            pass

        return False  # Default: treat as post (avoid missing real posts)

    except StaleElementReferenceException:
        raise
    except Exception:
        return False


def extract_post_data(post, idx, driver=None, retries=2):
    """Extract post data from a post element, with retry on stale element"""
    for attempt in range(retries + 1):
        try:
            return _extract_post_data_inner(post, idx, driver)
        except StaleElementReferenceException:
            if attempt < retries:
                print(f"   ⚡ Stale element on post {idx}, retrying ({attempt + 1}/{retries})...")
                time.sleep(0.5)
            else:
                print(f"   ⚠️ Post {idx} went stale after {retries} retries, skipping")
                return {
                    'index': idx, 'text': '', 'author': '', 'timestamp': '',
                    'url': '', 'likes': '', 'comments': '', 'shares': '',
                    'images': [], 'is_video': False, 'is_share': False
                }


def _extract_post_data_inner(post, idx, driver=None):
    """Inner extraction logic — lets StaleElementReferenceException bubble up
    so the retry wrapper in extract_post_data() can re-attempt."""
    post_data = {
        'index': idx,
        'text': '',
        'author': '',
        'timestamp': '',
        'url': '',
        'likes': '',
        'comments': '',
        'shares': '',
        'images': [],
        'is_video': False,
        'is_share': False
    }

    # --- Get text FIRST (most important field) ---
    # Try multiple strategies to find the actual post body text
    raw_text = ""

    # Strategy 1: Look for dir="auto" divs (Facebook wraps post text in these)
    try:
        text_containers = post.find_elements(By.CSS_SELECTOR, 'div[dir="auto"]')
        if text_containers:
            best_text = ""
            for container in text_containers:
                try:
                    t = container.text or ""
                    # The longest dir="auto" div is usually the post body (not just a name)
                    if len(t) > len(best_text) and len(t) > 5:
                        best_text = t
                except StaleElementReferenceException:
                    raise
                except Exception:
                    continue
            if best_text:
                raw_text = best_text
    except StaleElementReferenceException:
        raise
    except Exception:
        pass

    # Strategy 2: Look for the specific post text block using aria attributes
    if not raw_text or len(raw_text) < 10:
        try:
            # Facebook often marks the post body with data-ad-preview or specific span/div
            text_blocks = post.find_elements(By.CSS_SELECTOR, '[data-ad-preview], [data-ad-comet-preview]')
            if text_blocks:
                best_text = ""
                for block in text_blocks:
                    try:
                        t = block.text or ""
                        if len(t) > len(best_text):
                            best_text = t
                    except StaleElementReferenceException:
                        raise
                    except Exception:
                        continue
                if len(best_text) > len(raw_text):
                    raw_text = best_text
        except StaleElementReferenceException:
            raise
        except Exception:
            pass

    # Strategy 3: Look for the content div that contains the actual post text
    # This targets the common pattern where post text is in a specific nested div
    if not raw_text or len(raw_text) < 10:
        try:
            # Try span with dir="auto" (Facebook often uses spans for post text)
            spans = post.find_elements(By.CSS_SELECTOR, 'span[dir="auto"]')
            if spans:
                best_text = ""
                for span in spans:
                    try:
                        t = span.text or ""
                        if len(t) > len(best_text) and len(t) > 5:
                            best_text = t
                    except StaleElementReferenceException:
                        raise
                    except Exception:
                        continue
                if len(best_text) > len(raw_text):
                    raw_text = best_text
        except StaleElementReferenceException:
            raise
        except Exception:
            pass

    # Strategy 4: Fallback to the whole article text
    if not raw_text:
        try:
            raw_text = post.text or ""
        except StaleElementReferenceException:
            raise
        except Exception:
            raw_text = ""

    # Debug: Log if text extraction is failing
    if DEBUG_MODE and not raw_text.strip():
        try:
            # Log what's actually in this element so we can fix the selector
            inner_html = post.get_attribute('innerHTML') or ''
            tag = post.tag_name
            classes = post.get_attribute('class') or ''
            print(f"   🔍 DEBUG: Empty element - tag={tag}, class={classes[:80]}, html_len={len(inner_html)}")
        except Exception:
            pass

    # --- Try to extract author from the raw text (before cleaning) ---
    # Heuristic only — don't use for destructive text removal
    _heuristic_author = ''
    if raw_text:
        lines = raw_text.split('\n')
        if lines:
            first_line = lines[0].strip()
            if (2 < len(first_line) < 60 and
                not any(bad in first_line.lower() for bad in _AUTHOR_BAD_WORDS) and
                not re.match(r'^[\d٠-٩]+$', first_line)):
                _heuristic_author = first_line

    # --- Clean the text: remove UI elements ---
    cleaned_text = raw_text
    for pattern in _UI_CLEANUP_PATTERNS:
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE | re.MULTILINE)

    # Remove extra whitespace and clean up
    cleaned_text = re.sub(r'\n{2,}', '\n', cleaned_text)  # Multiple newlines to single
    cleaned_text = re.sub(r'^\s+|\s+$', '', cleaned_text, flags=re.MULTILINE)  # Trim each line
    cleaned_text = cleaned_text.strip()

    post_data['text'] = cleaned_text

    # Check if it's a video or share
    text_lower = cleaned_text.lower()
    post_data['is_video'] = 'shared a video' in text_lower or 'شارك فيديو' in text_lower
    post_data['is_share'] = 'shared a post' in text_lower or 'شارك منشور' in text_lower

    # --- Extract metadata (author, url, likes, etc.) ---
    # These are non-critical. StaleElement here means we still have the text.

    # Try to get author from link elements (more reliable than text extraction)
    try:
        all_links = post.find_elements(By.TAG_NAME, 'a')
        for link in all_links[:20]:
            try:
                href = link.get_attribute('href') or ''
                text = link.text.strip()
                # Author links typically go to facebook.com/profile.php or facebook.com/username
                if (text and 2 < len(text) < 60 and
                    not any(bad in text.lower() for bad in _BAD_AUTHOR_WORDS) and
                    '/posts/' not in href and '/permalink.php' not in href and
                    '?' not in text and ':' not in text and
                    ('facebook.com' in href or '/profile.php' in href)):
                    post_data['author'] = text
                    break
            except StaleElementReferenceException:
                continue
            except Exception:
                continue
    except StaleElementReferenceException:
        pass
    except Exception:
        pass

    # Try to get URL and Timestamp
    # Phase 1: Look for POST permalink (without comment_id=)
    try:
        links = post.find_elements(By.TAG_NAME, 'a')
        for link in links:
            try:
                href = link.get_attribute('href')
                if href and ('/posts/' in href or '/permalink.php' in href) and 'comment_id=' not in href:
                    post_data['url'] = href
                    link_text = link.text.strip()
                    if link_text and not post_data['timestamp'] and len(link_text) < 30:
                        if not any(stop in link_text.lower() for stop in ['facebook', 'http', 'share', 'مشاركة']):
                            post_data['timestamp'] = link_text
                    break  # Found the post URL, stop looking
            except StaleElementReferenceException:
                continue
            except Exception:
                continue
    except StaleElementReferenceException:
        pass
    except Exception:
        pass

    # Phase 2: Extract post URL from comment links (construct from post ID)
    if not post_data['url']:
        try:
            links = post.find_elements(By.TAG_NAME, 'a')
            for link in links:
                try:
                    href = link.get_attribute('href') or ''
                    if '/posts/' in href and 'comment_id=' in href:
                        match = re.match(r'(https?://[^/]+/groups/[^/]+/posts/\d+/)', href)
                        if match:
                            post_data['url'] = match.group(1)
                            break
                        post_id_match = re.search(r'/posts/(\d+)', href)
                        if post_id_match:
                            post_data['url'] = f'https://www.facebook.com/groups/{GROUP_ID}/posts/{post_id_match.group(1)}/'
                            break
                except StaleElementReferenceException:
                    continue
                except Exception:
                    continue
        except StaleElementReferenceException:
            pass
        except Exception:
            pass

    # Get reaction (likes) count from aria-labels (e.g. "25 reactions")
    try:
        interaction_elements = post.find_elements(By.CSS_SELECTOR, '[aria-label]')
        for elem in interaction_elements:
            try:
                aria_label = elem.get_attribute('aria-label') or ''
                label_lower = aria_label.lower()
                if 'like' in label_lower or 'react' in label_lower or 'اعجب' in aria_label or 'أعجب' in aria_label:
                    num_match = re.search(r'([\d,٠-٩\.]+\s*[KkMm]?)', aria_label)
                    if num_match and not post_data['likes']:
                        post_data['likes'] = _to_ascii_digits(num_match.group(1).replace(' ', ''))
            except StaleElementReferenceException:
                break
            except Exception:
                continue
        # Fallback: look for reaction count spans
        if not post_data['likes']:
            try:
                spans = post.find_elements(By.CSS_SELECTOR, 'span[aria-hidden="true"]')
                for span in spans:
                    try:
                        t = (span.text or '').strip()
                        if t and re.match(r'^[\d,٠-٩\.]+[KkMm]?$', t):
                            post_data['likes'] = _to_ascii_digits(t)
                            break
                    except Exception:
                        continue
            except Exception:
                pass
    except StaleElementReferenceException:
        pass
    except Exception:
        pass

    # Get comment & share counts via anchored count-element matching
    # (far more reliable than action-button aria-labels or innerText lines).
    try:
        c, s = _extract_engagement_counts(post, driver)
        if c:
            post_data['comments'] = c
        if s:
            post_data['shares'] = s
    except StaleElementReferenceException:
        pass
    except Exception:
        pass

    # Try to get image URLs
    try:
        images = post.find_elements(By.TAG_NAME, 'img')
        for img in images:
            try:
                src = img.get_attribute('src')
                if src and 'fbcdn.net' in src and 'profile' not in src and 'emoji' not in src and 'rsrc.php' not in src:
                    if 'scontent' in src and src not in post_data['images']:
                        post_data['images'].append(src)
            except Exception:
                continue
    except Exception:
        pass

    # Fallback: use heuristic author from first line (only if no DOM-based author found)
    if not post_data['author'] and _heuristic_author:
        post_data['author'] = _heuristic_author

    # Only strip confirmed author from the start of text
    if post_data['author'] and post_data['text'].startswith(post_data['author'] + '\n'):
        post_data['text'] = post_data['text'][len(post_data['author']):].strip()

    return post_data

def scrape_group_posts():
    """Main scraping function"""
    print("\n" + "="*70)
    print("FACEBOOK GROUP POST SCRAPER")
    print("="*70)
    print(f"Target: {GROUP_URL}")
    print(f"Output: {OUTPUT_JSONL}")
    print(f"Max scroll iterations: {MAX_SCROLL_ITERATIONS}")
    print("="*70 + "\n")

    try:
        print("🚀 Starting browser (undetected mode)...")
        driver = Driver(uc=True, headless=False, user_data_dir=PROFILE_DIR)
        print("✓ Browser started\n")
    except Exception as e:
        print(f"❌ Failed to start browser: {e}")
        print("\nTroubleshooting:")
        print("1. Close all other Chrome windows")
        print("2. Try deleting the profile folder and logging in again")
        return

    seen_posts = set()  # Track seen posts by URL/text hash to avoid duplicates
    seen_post_ids = set()  # Numeric post IDs seen — cheap pre-dedup for the article scan
    post_counter = 0   # Running index assigned to each newly scraped post

    # --- LOGIN FLOW ---
    try:
        # Step 1: Try loading saved cookies first
        cookies_loaded = load_cookies(driver)

        # Step 2: Check if we're already logged in
        logged_in = is_logged_in(driver)

        if not logged_in:
            # Step 3: Try logging in with credentials
            print("\n⚠️ Not logged in — starting login flow...")
            if not login_to_facebook(driver):
                print("❌ Could not log in. Exiting.")
                driver.quit()
                return
        else:
            print("✅ Already logged in (session restored)")
            # Refresh cookies to keep them current
            save_cookies(driver)
    except Exception as e:
        print(f"⚠️ Login flow error: {e}")
        print("💡 Attempting to continue anyway...")

    # --- RESUME CAPABILITY: LOAD PREVIOUSLY SEEN POSTS ---
    try:
        # Primary: load from JSONL file (current format)
        if os.path.exists(OUTPUT_JSONL):
            with open(OUTPUT_JSONL, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        p = json.loads(line)
                        seen_posts.add(_dedup_key(p))
                        _remember_post_id(p, seen_post_ids)
                    except json.JSONDecodeError:
                        continue  # skip corrupted line

        # Fallback: load from old batched JSON files (backward compat)
        existing_files = glob_mod.glob(f"{OUTPUT_DIR}/{GROUP_ID}_posts_*.json")
        for f in existing_files:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    for p in data.get('posts', []):
                        seen_posts.add(_dedup_key(p))
                        _remember_post_id(p, seen_post_ids)
            except Exception:
                pass

        if seen_posts:
            print(f"📦 Resuming: Loaded {len(seen_posts)} previously scraped posts. Will skip these.")
    except Exception as e:
        print(f"⚠️ Could not load history: {e}")

    try:
        print(f"📍 Navigating to group...")
        driver.get(GROUP_URL)
        # Wait for feed to appear (up to 10s) instead of fixed 8s sleep
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="feed"]'))
            )
        except Exception:
            time.sleep(5)  # Fallback if feed selector not found

        print("📜 Starting to scroll and collect posts...\n")

        # Debug dump on first run
        if DEBUG_MODE:
            debug_dump_elements(driver)

        total_new_posts = 0
        consecutive_no_new = 0

        # Register graceful Ctrl+C handler — data is already on disk per-post
        def _handle_interrupt(signum, frame):
            print(f"\n⚠️ Interrupted! {total_new_posts} posts already saved to {OUTPUT_JSONL}")
            sys.exit(0)
        signal.signal(signal.SIGINT, _handle_interrupt)

        for scroll_iteration in range(MAX_SCROLL_ITERATIONS):
            # Facebook uses virtual scrolling — only a few posts are in the DOM at a time.
            # PRIMARY STRATEGY: Find feed units (div[role="feed"] children)
            # Each feed unit is one post + its comments.
            # FALLBACK: Find posts via permalink links or article scanning.

            new_this_round = 0

            # === STRATEGY 0 (PRIMARY): Find posts via feed structure ===
            feed_posts = find_posts_via_feed(driver)

            if DEBUG_MODE:
                total_articles = len(driver.find_elements(By.CSS_SELECTOR, 'div[role="article"]'))
                print(f"🔄 Scroll {scroll_iteration + 1}/{MAX_SCROLL_ITERATIONS} - {len(feed_posts)} feed units, {total_articles} articles")

            # Process the feed units found above
            for post_id, unit in feed_posts:
                try:
                    if post_id in seen_posts:
                        continue

                    # Scroll into view
                    try:
                        driver.execute_script(
                            "arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});",
                            unit
                        )
                        time.sleep(0.5)
                    except Exception:
                        pass

                    # Click "See more" to expand truncated posts
                    try:
                        click_all_show_more_buttons(unit, driver)
                    except Exception:
                        pass

                    # Extract post data using JS-based text extraction
                    post_data = extract_post_data_from_feed_unit(unit, post_counter, driver)

                    if DEBUG_MODE:
                        text_preview = post_data.get('text', '')[:80].replace('\n', ' ')
                        url_preview = post_data.get('url', '')[:80]
                        print(f"   🔍 feed: text={text_preview!r} url={url_preview!r}")

                    # Keep image-only / link-only posts too — only drop units
                    # with no text AND no media (text-length alone was dropping
                    # legit image posts and very short posts).
                    text = post_data.get('text', '').strip()
                    has_media = bool(post_data.get('images')) or bool(post_data.get('url'))
                    if (not text or len(text) < 5) and not has_media:
                        if DEBUG_MODE:
                            print(f"      → SKIPPED: no text and no media")
                        continue

                    # Dedup
                    pid = _dedup_key(post_data)
                    if pid in seen_posts:
                        continue

                    seen_posts.add(pid)
                    _remember_post_id(post_data, seen_post_ids)
                    _append_post_to_jsonl(post_data, OUTPUT_JSONL)
                    post_counter += 1
                    new_this_round += 1
                    print(f"   ✅ Post: {(text or '[media-only]')[:60]}...")

                except StaleElementReferenceException:
                    continue
                except Exception as e:
                    if DEBUG_MODE:
                        print(f"   ⚠️ Error on feed post: {e}")
                    continue

            # === STRATEGY 1 (FALLBACK): permalink links — only if feed empty ===
            if not feed_posts:
                post_links_found = find_post_elements_via_links(driver)
                if DEBUG_MODE:
                    print(f"   Fallback: {len(post_links_found)} post links found")

                for post_id_from_link, container in post_links_found:
                    try:
                        if post_id_from_link in seen_post_ids or post_id_from_link in seen_posts:
                            continue

                        try:
                            driver.execute_script(
                                "arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});",
                                container
                            )
                            time.sleep(0.5)
                        except Exception:
                            pass

                        post_data = extract_post_data(container, post_counter, driver)

                        text = post_data.get('text', '').strip()
                        has_media = bool(post_data.get('images')) or bool(post_data.get('url'))
                        if (not text or len(text) < 5) and not has_media:
                            continue

                        pid = _dedup_key(post_data)
                        if pid in seen_posts:
                            continue

                        seen_posts.add(pid)
                        _remember_post_id(post_data, seen_post_ids)
                        _append_post_to_jsonl(post_data, OUTPUT_JSONL)
                        post_counter += 1
                        new_this_round += 1
                        print(f"   ✅ Post (link): {(text or '[media-only]')[:60]}...")

                    except StaleElementReferenceException:
                        continue
                    except Exception as e:
                        if DEBUG_MODE:
                            print(f"   ⚠️ Error on link-based post: {e}")
                        continue

            # === STRATEGY 2 (SUPPLEMENT, every round): scan articles ===
            # Runs even when the feed strategy found posts, to catch any unit it
            # skipped. Cheap pre-dedup by numeric post ID avoids re-extracting
            # posts we've already saved this run.
            articles = driver.find_elements(By.CSS_SELECTOR, 'div[role="article"]')
            if DEBUG_MODE:
                print(f"   Supplement: {len(articles)} article elements")

            for idx, article in enumerate(articles):
                try:
                    # Cheap skip: already-saved post (by numeric ID)
                    article_pid = _clean_post_id(article)
                    if article_pid and article_pid in seen_post_ids:
                        continue

                    try:
                        html_size = len(article.get_attribute('innerHTML') or '')
                    except Exception:
                        html_size = 0
                    # Comments are small; keep the floor low enough for short posts
                    if html_size < 2000:
                        continue

                    if _is_comment_article(article):
                        continue

                    post_data = extract_post_data(article, post_counter, driver)

                    text = post_data.get('text', '').strip()
                    has_media = bool(post_data.get('images')) or bool(post_data.get('url'))
                    if (not text or len(text) < 5) and not has_media:
                        continue

                    pid = _dedup_key(post_data)
                    if pid in seen_posts:
                        continue

                    seen_posts.add(pid)
                    _remember_post_id(post_data, seen_post_ids)
                    _append_post_to_jsonl(post_data, OUTPUT_JSONL)
                    post_counter += 1
                    new_this_round += 1
                    print(f"   ✅ Post (article): {(text or '[media-only]')[:60]}...")

                except StaleElementReferenceException:
                    continue
                except Exception:
                    continue

            total_new_posts += new_this_round

            if new_this_round > 0:
                consecutive_no_new = 0
            else:
                consecutive_no_new += 1

            print(f"   Round: {new_this_round} new | Total: {total_new_posts} unique | Consecutive empty: {consecutive_no_new}")

            # Stop if no new posts found for several rounds
            if consecutive_no_new >= 10:
                print(f"\n✓ No new posts found after {consecutive_no_new} rounds, stopping.")
                break

            # Step 3: Scroll down to load more posts
            scroll_distance = 800
            scroll_down(driver, scroll_distance)
            # Adaptive wait: shorter when actively finding posts, longer when idle
            if consecutive_no_new == 0:
                time.sleep(1.5)   # Posts flowing — short wait
            elif consecutive_no_new <= 3:
                time.sleep(3)     # Mild drought — normal wait
            elif consecutive_no_new <= 7:
                time.sleep(5)     # Longer drought — give Facebook more time
            else:
                time.sleep(6)     # Near stop threshold — last chance

        # All posts already saved per-post to JSONL — nothing to flush
        print("\n" + "="*70)
        print("SCRAPING COMPLETE!")
        print("="*70)
        print(f"Total unique posts collected: {total_new_posts}")
        print(f"Data file: {OUTPUT_JSONL}")
        print("="*70 + "\n")

        # Create a summary file
        summary = {
            'scrape_summary': {
                'timestamp': datetime.now().isoformat(),
                'group_url': GROUP_URL,
                'total_unique_posts': total_new_posts,
                'data_file': OUTPUT_JSONL,
            }
        }

        summary_file = f"{OUTPUT_DIR}/scrape_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"📊 Summary saved to: {summary_file}\n")

    except Exception as e:
        print(f"\n❌ Error during scraping: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("🔄 Closing browser...")
        try:
            driver.quit()
            print("✓ Browser closed\n")
        except Exception:
            pass


if __name__ == "__main__":
    scrape_group_posts()
