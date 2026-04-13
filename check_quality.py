import json, glob, os

files = sorted(glob.glob("/Users/admin/Desktop/LeanStartup_Group_Scraper/output/lean_startup_posts_*.json"), key=os.path.getmtime)

all_posts = []
for f in files:
    data = json.load(open(f, encoding='utf-8'))
    all_posts.extend(data.get('posts', []))

# Deduplicate
seen = set()
unique = []
for p in all_posts:
    t = p.get('text','').strip()
    if t and t not in seen:
        seen.add(t)
        unique.append(p)

total = len(unique)
if total == 0:
    print("No posts found!")
    exit()

has_author = sum(1 for p in unique if p.get('author','').strip())
has_url = sum(1 for p in unique if p.get('url','').strip())
has_likes = sum(1 for p in unique if p.get('likes','').strip())
has_comments = sum(1 for p in unique if p.get('comments','').strip())
short_posts = sum(1 for p in unique if len(p.get('text','')) < 100)
medium_posts = sum(1 for p in unique if 100 <= len(p.get('text','')) < 300)
long_posts = sum(1 for p in unique if len(p.get('text','')) >= 300)
truncated = sum(1 for p in unique if 'See more' in p.get('text','') or 'عرض المزيد' in p.get('text',''))

print("=== DATA QUALITY REPORT ===")
print(f"Total unique posts: {total}")
print(f"\nField coverage:")
print(f"  Author captured:   {has_author}/{total} ({100*has_author//total}%)")
print(f"  URL captured:      {has_url}/{total} ({100*has_url//total}%)")
print(f"  Likes captured:    {has_likes}/{total} ({100*has_likes//total}%)")
print(f"  Comments captured: {has_comments}/{total} ({100*has_comments//total}%)")
print(f"\nPost length breakdown:")
print(f"  Short (<100 chars):  {short_posts} ({100*short_posts//total}%)")
print(f"  Medium (100-300):    {medium_posts} ({100*medium_posts//total}%)")
print(f"  Long (300+ chars):   {long_posts} ({100*long_posts//total}%)")
print(f"\nStill truncated ('See More' not clicked): {truncated}")
print(f"\n=== TOP 5 LONGEST POSTS (best quality) ===")
unique.sort(key=lambda x: len(x.get('text','')), reverse=True)
for i, p in enumerate(unique[:5]):
    print(f"\n[{i+1}] Author: {p.get('author','?')} | Likes: {p.get('likes','?')} | Comments: {p.get('comments','?')}")
    print(f"Length: {len(p.get('text',''))} chars")
    print(p.get('text','')[:400])
    print("-"*60)
