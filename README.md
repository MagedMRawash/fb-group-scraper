# Lean Startup Circle Egypt Group Scraper

Scrapes all posts from the Lean Startup Circle Egypt Facebook group and saves them to JSON files.

## Setup

1. **Install dependencies:**
```bash
pip3 install seleniumbase
```

2. **Login to Facebook:**
   - Run the scraper once
   - Login to Facebook in the browser window that opens
   - The scraper will save your login session

## Usage

### Method 1: Double-click the command file
Simply double-click `Start_LeanStartup_Scraper.command` on your Desktop

### Method 2: Run from Terminal
```bash
cd /Users/admin/Desktop/se3rahakam/car-scraper-automation
source venv/bin/activate
python /Users/admin/Desktop/LeanStartup_Group_Scraper/scrape_group_posts.py
```

## Configuration

Edit `scrape_group_posts.py` to adjust:

- `MAX_POSTS_PER_FILE` (default: 1000) - Posts per JSON file
- `MAX_SCROLL_ITERATIONS` (default: 500) - Maximum scroll attempts
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
- ✅ Expands truncated posts ("See More")
- ✅ Clicks "Load More" buttons automatically
- ✅ Human-like scrolling behavior
- ✅ Duplicate detection
- ✅ Saves to multiple JSON files (handles large datasets)
- ✅ Continues from where it left off (via session)
- ✅ Detailed progress logging

## Notes

- The scraper is aggressive and will try to collect as many posts as possible
- Facebook may rate-limit - if this happens, take a break and try again later
- The scraper uses a persistent Chrome profile to maintain login sessions
- Output files are UTF-8 encoded for Arabic text support

## Troubleshooting

**Browser doesn't start:**
- Close all other Chrome windows
- Delete the `fb_group_scraper_profile` folder
- Try again

**No posts found:**
- Make sure you're logged into Facebook
- Check if the group URL is correct
- Ensure you have access to the group

**Scraper stops early:**
- Increase `MAX_SCROLL_ITERATIONS` in the script
- Facebook may have loaded all available posts

## Example Output

```json
{
  "scrape_info": {
    "timestamp": "2026-04-11T10:30:45",
    "group_url": "https://web.facebook.com/groups/LeanStartupCircleEgypt",
    "total_posts_in_file": 1000,
    "file_number": 1
  },
  "posts": [
    {
      "index": 0,
      "text": "Full post text here...",
      "author": "Author Name",
      "timestamp": "Yesterday at 10:30 AM",
      "url": "https://www.facebook.com/groups/LeanStartupCircleEgypt/posts/123456789",
      "likes": "45",
      "comments": "12",
      "shares": "3",
      "images": ["https://scontent..."],
      "is_video": false,
      "is_share": false
    }
  ]
}
```
