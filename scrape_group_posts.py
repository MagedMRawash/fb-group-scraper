"""
Facebook Group Post Scraper
Scrapes all posts from a Facebook group and saves to JSON
"""
from seleniumbase import Driver
from selenium.webdriver.common.by import By
import time
import json
import random
from datetime import datetime
import os
import re


# Configuration
GROUP_URL = "https://web.facebook.com/groups/LeanStartupCircleEgypt"
OUTPUT_DIR = "/Users/admin/Desktop/LeanStartup_Group_Scraper/output"
MAX_POSTS_PER_FILE = 30  # Save every 30 posts for quick feedback
MAX_SCROLL_ITERATIONS = 1000  # Small batch for testing
MIN_POSTS_PER_SCROLL = 5  # If we get fewer than this new posts, we might be at the end

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)


def scroll_down(driver, distance=2000):
    """Aggressive scroll down to find more posts quickly"""
    driver.execute_script(f"window.scrollBy(0, {distance});")
    time.sleep(0.5)  # Shorter pause for faster scrolling


def click_show_more(post, driver):
    """Click 'See More' / 'عرض المزيد' buttons to expand truncated posts"""
    try:
        # Look for all clickable elements that might be "See More" buttons
        all_clickable = post.find_elements(By.CSS_SELECTOR, "[role='button'], span[role='button']")

        for button in all_clickable:
            try:
                text = button.text.strip() if button.text else ""
                # Check if this button contains "See More" text
                if text and ('عرض المزيد' in text or 'See more' in text or 'See More' in text or 'عرض المزيد من' in text):
                    if button.is_displayed():
                        # Scroll to button
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", button)
                        time.sleep(0.2)

                        # Try JavaScript click first (most reliable)
                        try:
                            driver.execute_script("arguments[0].click();", button)
                            time.sleep(0.5)  # Wait for content to expand
                            return True
                        except:
                            # Fallback to regular click
                            try:
                                button.click()
                                time.sleep(0.5)
                                return True
                            except:
                                continue
            except:
                continue
    except:
        pass
    return False

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
                        except:
                            try:
                                button.click()
                                time.sleep(0.4)
                                buttons_clicked += 1
                            except:
                                pass
            except:
                continue

        return buttons_clicked > 0
    except:
        pass
    return False


def click_load_more(driver):
    """Click 'Load More' / 'Load more posts' button if present"""
    try:
        # More comprehensive selectors for "Load More" button
        load_more_selectors = [
            # English
            "//div[contains(text(), 'Load more')]",
            "//div[contains(text(), 'See more posts')]",
            "//a[contains(text(), 'Load more')]",
            "//button[contains(text(), 'Load more')]",
            # Arabic
            "//div[contains(text(), 'عرض المزيد من المنشورات')]",
            "//div[contains(text(), 'تحميل المزيد')]",
            "//div[contains(text(), 'المزيد من المنشورات')]",
            "//a[contains(text(), 'عرض المزيد من المنشورات')]",
            # More generic patterns
            "//div[contains(text(), 'more')]",
            "//a[contains(text(), 'more')]",
        ]

        for selector in load_more_selectors:
            try:
                buttons = driver.find_elements(By.XPATH, selector)
                for btn in buttons:
                    try:
                        if btn.is_displayed():
                            # Scroll to button
                            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", btn)
                            time.sleep(0.3)

                            # Try JavaScript click first (most reliable)
                            try:
                                driver.execute_script("arguments[0].click();", btn)
                                time.sleep(1.5)  # Longer wait for content to load
                                return True
                            except:
                                # Fallback to regular click
                                try:
                                    btn.click()
                                    time.sleep(1.5)
                                    return True
                                except:
                                    continue
                    except:
                        continue
            except:
                continue
    except:
        pass
    return False


def extract_post_data(post, idx, driver=None):
    """Extract post data from a post element"""
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

    try:
        # Check if post text is truncated (multiple patterns)
        raw_text_before = post.text if post else ""
        # Check for various truncation patterns
        is_truncated = (
            "..." in raw_text_before or
            "عرض المزيد" in raw_text_before or
            "See more" in raw_text_before or
            "عرض المزيد من" in raw_text_before or  # "Show more from [source]"
            "عرض كل" in raw_text_before or  # "Show all [items]"
            "See More" in raw_text_before or
            "Read more" in raw_text_before
        )

        # Try to expand truncated posts - more aggressive clicking
        if is_truncated:
            # Try clicking all "See More" buttons first (most effective)
            click_all_show_more_buttons(post, driver)
            time.sleep(0.8)  # Wait for content to load

            # Additional attempts with different strategies
            max_attempts = 3
            for attempt in range(max_attempts):
                clicked = click_show_more(post, driver)
                if clicked:
                    # Wait longer for content to load
                    time.sleep(1.0)  # Longer wait
                    # Get text again to check if expanded
                    try:
                        new_raw_text = post.text if post else ""
                    except:
                        new_raw_text = ""

                    if len(new_raw_text) > len(raw_text_before):
                        break  # Successfully expanded
                    raw_text_before = new_raw_text
                else:
                    # Even if click failed, move on to next attempt
                    pass
                time.sleep(0.5)  # Pause between attempts

        time.sleep(0.2)

        # Get post text
        raw_text = ""
        try:
            raw_text = post.text
        except:
            pass

        # Clean text - remove UI elements and buttons
        # Remove UI elements that commonly appear in Facebook posts
        ui_patterns = [
            # Arabic UI elements
            r'عرض المزيد',
            r'عرض المزيد من التعليقات',
            r'عرض كل الردود',
            r'عرض المزيد من الإجابات',
            r'عرض  واحد',
            r'عرض  (\d+)',
            r'عرض كل الردود \((\d+)\)',
            r'أعجبني',
            r'رد',
            r'مشاركة',
            r'عرض الترجمة',
            r'تقييم هذه الترجمة',
            r'عرض الأصل',
            r'اكتب تعليقًا عامًا',
            r'اكتب إجابة',
            r'مهتم',
            r'Interested',
            r'متابعة',
            r'مساهم صاعد',
            r'مساهم بارز',
            r'مشرف',
            r'خبير مجموعة',
            # English UI elements
            r'See more',
            r'See More',
            r'Show more',
            r'Show more comments',
            r'Show all replies',
            r'Like',
            r'Reply',
            r'Share',
            r'Show translation',
            r'View original',
            r'Write a comment',
            r'Write an answer',
            # Time patterns (like "٨ س", "2 ي", "٥٧ د")
            r'·\s*[٠-٩]+\s*[دسسح][\s\n]*',  # Arabic time
            r'·\s*\d+\s*[dhm][\s\n]*',  # English time
            # Interaction counts in Arabic
            r'^[\d\u0660-\u0669]+\s*[\n\s]+$',  # Standalone numbers
            r'^\s*[\d\u0660-\u0669]+\s*\n',  # Numbers at start of line
            r'\n[\d\u0660-\u0669]+\s*$',  # Numbers at end of text
            # Contributor badges
            r'خبير مجموعة في[^$]+',
            r'Rising contributor[^$]*',
            r'Top contributor[^$]*',
        ]

        cleaned_text = raw_text
        for pattern in ui_patterns:
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE)

        # Remove extra whitespace and clean up
        cleaned_text = re.sub(r'\n+', '\n', cleaned_text)  # Multiple newlines to single
        cleaned_text = re.sub(r'^\s+|\s+$', '', cleaned_text)  # Trim
        cleaned_text = cleaned_text.strip()

        post_data['text'] = cleaned_text

        # Check if it's a video or share
        text_lower = cleaned_text.lower()
        post_data['is_video'] = 'shared a video' in text_lower or 'شارك فيديو' in text_lower
        post_data['is_share'] = 'shared a post' in text_lower or 'شارك منشور' in text_lower

        # Try to get author
        try:
            author_candidates = []

            # Bad patterns to reject — UI elements, URLs, Arabic buttons
            bad_author_words = [
                'مشرف', 'خبير', 'مساهم', 'صاعد', 'بارز', 'متابعة', 'مهتم',
                'interested', 'follow', 'share', 'like', 'reply', 'comment',
                'more', 'show', 'عرض', 'اكتب', 'اقرأ', 'http', 'www',
                'منذ', 'ago', 'ساعة', 'دقيقة', 'يوم', 'hour', 'min', 'day',
            ]

            # Strategy 1: Find author link (most reliable)
            try:
                all_links = post.find_elements(By.TAG_NAME, 'a')
                for link in all_links[:15]:
                    href = link.get_attribute('href') or ''
                    text = link.text.strip()
                    if (text and 2 < len(text) < 60 and
                        not any(bad in text.lower() for bad in bad_author_words) and
                        not href.startswith('https:') == text and
                        '/posts/' not in href and '/permalink.php' not in href and
                        '?' not in text and ':' not in text):
                        author_candidates.append(text)
            except:
                pass

            if author_candidates:
                author_candidates = list(dict.fromkeys(author_candidates))  # dedupe preserve order
                author_candidates.sort(key=lambda x: len(x))
                post_data['author'] = author_candidates[0]

        except:
            pass

        # Try to get URL and Timestamp
        try:
            links = post.find_elements(By.TAG_NAME, 'a')
            for link in links:
                href = link.get_attribute('href')
                if href and ('/posts/' in href or '/permalink.php' in href):
                    if not post_data['url']:
                        post_data['url'] = href
                    # The timestamp is usually the text of the permalink
                    link_text = link.text.strip()
                    if link_text and not post_data['timestamp'] and len(link_text) < 30:
                        # Ensure it's not simply the domain or share button
                        if not any(stop in link_text.lower() for stop in ['facebook', 'http', 'share', 'مشاركة']):
                            post_data['timestamp'] = link_text
                            break
        except:
            pass

        # Try to get likes/comments/shares counts
        try:
            interaction_elements = post.find_elements(By.CSS_SELECTOR, '[aria-label]')
            for elem in interaction_elements:
                aria_label = elem.get_attribute('aria-label') or ''
                # Match Arabic/English numbers in aria-label
                num_match = re.search(r'([\d,٠-٩]+)', aria_label)
                count = num_match.group(1) if num_match else ''
                label_lower = aria_label.lower()
                if 'like' in label_lower or 'اعجب' in aria_label or 'أعجب' in aria_label or 'react' in label_lower:
                    if count and not post_data['likes']:
                        post_data['likes'] = count
                elif 'comment' in label_lower or 'تعليق' in aria_label:
                    if count and not post_data['comments']:
                        post_data['comments'] = count
                elif 'share' in label_lower or 'مشاركة' in aria_label:
                    if count and not post_data['shares']:
                        post_data['shares'] = count

            # Fallback: look for reaction count spans
            if not post_data['likes']:
                try:
                    spans = post.find_elements(By.CSS_SELECTOR, 'span[aria-hidden="true"]')
                    for span in spans:
                        t = (span.text or '').strip()
                        if t and re.match(r'^[\d,٠-٩\.]+[KkMm]?$', t):
                            post_data['likes'] = t
                            break
                except:
                    pass
        except:
            pass

        # Try to get image URLs (filter out UI icons)
        try:
            images = post.find_elements(By.TAG_NAME, 'img')
            for img in images:
                src = img.get_attribute('src')
                # Skip UI icons, profile pics, and emoji
                if src and 'fbcdn.net' in src and 'profile' not in src and 'emoji' not in src and 'rsrc.php' not in src:
                    # Only include larger images (not small icons)
                    if 'scontent' in src and src not in post_data['images']:
                        post_data['images'].append(src)
        except:
            pass

    except Exception as e:
        print(f"Error extracting post {idx}: {e}")

    return post_data


def save_posts_to_file(posts, file_number):
    """Save posts to a JSON file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{OUTPUT_DIR}/lean_startup_posts_part{file_number}_{timestamp}.json"

    data = {
        'scrape_info': {
            'timestamp': datetime.now().isoformat(),
            'group_url': GROUP_URL,
            'total_posts_in_file': len(posts),
            'file_number': file_number
        },
        'posts': posts
    }

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✓ Saved {len(posts)} posts to {filename}")
    return filename


def scrape_group_posts():
    """Main scraping function"""
    print("\n" + "="*70)
    print("FACEBOOK GROUP POST SCRAPER")
    print("="*70)
    print(f"Target: {GROUP_URL}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Max posts per file: {MAX_POSTS_PER_FILE}")
    print(f"Max scroll iterations: {MAX_SCROLL_ITERATIONS}")
    print("="*70 + "\n")

    # Use dedicated local profile (copy of car scraper profile with FB session)
    profile_dir = "/Users/admin/Desktop/LeanStartup_Group_Scraper/fb_group_scraper_profile"

    try:
        print("🚀 Starting browser (undetected mode)...")
        driver = Driver(uc=True, headless=False, user_data_dir=profile_dir)
        print("✓ Browser started\n")
    except Exception as e:
        print(f"❌ Failed to start browser: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure you're logged into Facebook")
        print("2. Close all other Chrome windows")
        print("3. Try deleting the profile folder and logging in again")
        return

    all_posts = []
    seen_posts = set()  # Track seen posts by URL/text hash to avoid duplicates
    
    # --- RESUME CAPABILITY: LOAD PREVIOUSLY SEEN POSTS ---
    try:
        import glob
        existing_files = glob.glob(f"{OUTPUT_DIR}/lean_startup_posts_*.json")
        for f in existing_files:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    for p in data.get('posts', []):
                        pid = p.get('url')
                        if not pid:
                            pid = str(hash(p.get('text', '')[:120]))
                        seen_posts.add(pid)
            except:
                pass
        if seen_posts:
            print(f"📦 Resuming: Loaded {len(seen_posts)} previously scraped posts. Will skip these.")
    except Exception as e:
        print(f"⚠️ Could not load history: {e}")
        
    # Find the highest file_number to resume numbering correctly
    file_number = 1
    try:
        if existing_files:
            numbers = []
            for f in existing_files:
                match = re.search(r'part(\d+)_', f)
                if match:
                    numbers.append(int(match.group(1)))
            if numbers:
                file_number = max(numbers) + 1
    except:
        pass
    saved_files = []
    consecutive_empty_scrolls = 0

    try:
        print(f"📍 Navigating to Facebook home first...")
        driver.get("https://www.facebook.com")
        time.sleep(5)
        
        print(f"📍 Navigating to group...")
        driver.get(GROUP_URL)
        time.sleep(8)  # Wait for page load

        print("📜 Starting to scroll and collect posts...\n")

        for scroll_iteration in range(MAX_SCROLL_ITERATIONS):
            # Find all posts
            posts = driver.find_elements(By.CSS_SELECTOR, 'div[role="article"]')
            current_post_count = len(posts)

            print(f"🔄 Scroll {scroll_iteration + 1}/{MAX_SCROLL_ITERATIONS} - Found {current_post_count} posts total")

            # Process new posts
            new_posts_count = 0
            for idx, post in enumerate(posts):
                try:
                    post_data = extract_post_data(post, idx)

                    # Skip if this is a comment or reply (has comment_id in URL)
                    if post_data['url'] and 'comment_id=' in post_data['url']:
                        continue

                    # Skip if text is too short (likely a comment or button)
                    # Reduced threshold to catch more real posts
                    if len(post_data['text']) < 10:
                        continue

                    # Skip if it's marked as share/video if you only want original posts
                    # Comment out these lines if you want to include shares/videos:
                    # if post_data['is_share']:
                    #     continue
                    # if post_data['is_video']:
                    #     continue

                    # Create a unique identifier - use URL first, then first 120 chars of text
                    post_id = post_data['url']
                    if not post_id:
                        post_id = str(hash(post_data['text'][:120]))

                    if post_id not in seen_posts and post_data['text']:
                        seen_posts.add(post_id)
                        all_posts.append(post_data)
                        new_posts_count += 1

                        # Save to file if we reached the limit
                        if len(all_posts) >= MAX_POSTS_PER_FILE:
                            filename = save_posts_to_file(all_posts, file_number)
                            saved_files.append(filename)
                            file_number += 1
                            all_posts = []  # Reset for next file

                except Exception as e:
                    print(f"⚠️  Error processing post {idx}: {e}")
                    continue

            if new_posts_count > 0:
                print(f"   ✅ Found {new_posts_count} new posts (Total unique: {len(seen_posts)})")
            else:
                print(f"   ℹ️  No new posts")

            # Try to click "Load More" button periodically
            if scroll_iteration % 10 == 0:
                if click_load_more(driver):
                    print(f"   📥 Clicked Load More button")
                    time.sleep(2)

            # Scroll down (more aggressive on later iterations)
            scroll_distance = 1000
            if scroll_iteration > 50:
                scroll_distance = 1500
            if scroll_iteration > 100:
                scroll_distance = 2000

            scroll_down(driver, scroll_distance)

            # Check if we've reached the end (no new posts after scrolling)
            if scroll_iteration > 20 and new_posts_count == 0:
                consecutive_empty_scrolls += 1
                if consecutive_empty_scrolls >= 5:
                    print(f"\n✓ Reached end of posts (no new posts found after {consecutive_empty_scrolls} scrolls)")
                    break
            else:
                consecutive_empty_scrolls = 0

        # Save any remaining posts
        if all_posts:
            filename = save_posts_to_file(all_posts, file_number)
            saved_files.append(filename)

        print("\n" + "="*70)
        print("SCRAPING COMPLETE!")
        print("="*70)
        print(f"Total unique posts collected: {len(seen_posts)}")
        print(f"Total files created: {len(saved_files)}")
        print(f"\nFiles saved:")
        for f in saved_files:
            print(f"  • {f}")
        print("="*70 + "\n")

        # Create a summary file
        summary = {
            'scrape_summary': {
                'timestamp': datetime.now().isoformat(),
                'group_url': GROUP_URL,
                'total_unique_posts': len(seen_posts),
                'total_files': len(saved_files),
                'files': saved_files
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
        except:
            pass


if __name__ == "__main__":
    scrape_group_posts()
