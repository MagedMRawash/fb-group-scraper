# Lean Startup Circle Egypt Group Scraper

Scrapes all posts from the Lean Startup Circle Egypt Facebook group and saves them to JSON files.

## Setup

1. **Install dependencies:**
```bash
pip install seleniumbase
```

2. **First run — Login:**
   - Run the scraper for the first time
   - It will prompt you for your Facebook email/phone and password in the terminal
   - Your password input is hidden (secure, like `sudo`)
   - After successful login, your session cookies are saved to `fb_cookies.pkl`
   - **Your credentials are never stored in the code** — only session cookies are saved locally

3. **Subsequent runs:**
   - The scraper automatically loads saved cookies to restore your session
   - You only need to log in again if the session expires (typically after weeks/months)
   - If cookies expire, it will prompt you again

## Usage

```bash
python scrape_group_posts.py
```

## Configuration

Edit `scrape_group_posts.py` to adjust:

- `MAX_POSTS_PER_FILE` (default: 30) - Posts per JSON file
- `MAX_SCROLL_ITERATIONS` (default: 1000) - Maximum scroll attempts
- `GROUP_URL` - Change to scrape a different group

## Output

Posts are saved to the `output/` folder as JSON files:

- `lean_startup_posts_part1_TIMESTAMP.json`
- `lean_startup_posts_part2_TIMESTAMP.json`
- `scrape_summary_TIMESTAMP.json` - Summary of all scraped data

## Post Data Structure

Each post contains:
- `text` - Full post text
- `author` - Post author name
- `timestamp` - Post timestamp
- `url` - Post URL
- `likes` - Number of likes
- `comments` - Number of comments
- `shares` - Number of shares
- `images` - List of image URLs
- `is_video` - Boolean (if post contains video)
- `is_share` - Boolean (if post is a share)

## Features

- ✅ Undetected Chrome (avoids Facebook bot detection)
- ✅ Persistent login via saved cookies (no need to log in every time)
- ✅ Automatic login flow with credential prompt
- ✅ Handles 2FA (waits for you to complete it in browser)
- ✅ Expands truncated posts ("See More")
- ✅ Clicks "Load More" buttons automatically
- ✅ Human-like scrolling behavior
- ✅ Duplicate detection
- ✅ Saves to multiple JSON files (handles large datasets)
- ✅ Continues from where it left off (via session + seen-post tracking)
- ✅ Detailed progress logging

## Security & Privacy

- Your Facebook **password is never stored** — it's only used during login and not saved to disk
- Session cookies are saved to `fb_cookies.pkl` (added to `.gitignore` so they're never committed)
- The Chrome profile directory is also excluded from version control
- All data stays on your local machine — nothing is sent to any external party

## Troubleshooting

**Browser doesn't start:**
- Close all other Chrome windows
- Delete the `fb_group_scraper_profile` folder and try again

**Login fails:**
- Make sure you're entering the correct email and password
- If you have 2FA enabled, complete it in the browser window when prompted
- Delete `fb_cookies.pkl` and try again

**No posts found:**
- Make sure you're logged into Facebook (the scraper will prompt you)
- Check if the group URL is correct
- Ensure you have access to the group

**Scraper stops early:**
- Increase `MAX_SCROLL_ITERATIONS` in the script
- Facebook may have loaded all available posts

**Cookies expired:**
- Delete `fb_cookies.pkl` to force a fresh login