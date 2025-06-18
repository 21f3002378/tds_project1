import json
import requests
import time
import os

BASE_URL = "https://discourse.onlinedegree.iitm.ac.in"
COOKIE_FILE = "cookie.txt"
THREADS_FILE = "all_threads.json"
OUTPUT_FILE = "all_posts.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

def read_cookie():
    if not os.path.exists(COOKIE_FILE):
        raise Exception("cookie.txt not found. Please create it with _forum_session=...")
    with open(COOKIE_FILE, "r") as f:
        line = f.read().strip()
        key, value = line.split("=", 1)
        return {key: value}

def write_cookie(value):
    with open(COOKIE_FILE, "w") as f:
        f.write(f"_forum_session={value}")

def extract_new_cookie(set_cookie_header):
    if not set_cookie_header:
        return None
    for part in set_cookie_header.split(";"):
        if "_forum_session=" in part:
            return part.split("=", 1)[1]
    return None

# Load threads
with open(THREADS_FILE, "r", encoding="utf-8") as f:
    threads = json.load(f)

print(f"📄 Scraping posts from {len(threads)} threads...\n")

session = requests.Session()
current_cookie = read_cookie()
all_posts_data = [] # Renamed to avoid conflict with `posts` inside loop

for i, thread in enumerate(threads):
    topic_id = thread["id"]
    title = thread["title"]
    slug = thread.get("slug", "")
    initial_url = f"{BASE_URL}/t/{topic_id}.json" # Initial URL to get topic metadata and some posts

    try:
        print(f"⏳ [{i + 1}/{len(threads)}] Fetching topic metadata for '{title[:60]}'...")
        res = session.get(initial_url, headers=HEADERS, cookies=current_cookie)

        # Try refreshing cookie if present
        new_cookie_header = res.headers.get("Set-Cookie")
        new_cookie_val = extract_new_cookie(new_cookie_header)
        if new_cookie_val:
            current_cookie["_forum_session"] = new_cookie_val
            write_cookie(new_cookie_val)
            print("🔁 Session cookie refreshed and saved.")

        if res.status_code == 403:
            print("❌ 403 Forbidden. Probably logged out or cookie expired. Stopping.")
            break
        elif res.status_code != 200:
            print(f"⚠️ Error fetching topic {topic_id} metadata: HTTP {res.status_code}")
            continue

        topic_data = res.json()
        
        # This will contain the post numbers in order
        post_ids_in_stream = topic_data.get("post_stream", {}).get("stream", [])
        
        # Get existing posts from the initial response
        initial_posts = topic_data.get("post_stream", {}).get("posts", [])
        
        # We'll store all posts for this thread here
        full_thread_posts = {}
        for p in initial_posts:
            full_thread_posts[p["id"]] = p # Use post ID as key for easy lookup

        # Check if there are more posts than initially fetched
        if len(post_ids_in_stream) > len(initial_posts):
            # Calculate which post IDs we still need to fetch
            # Filter out post IDs we already have from initial_posts
            remaining_post_ids_to_fetch = [
                pid for pid in post_ids_in_stream if pid not in full_thread_posts
            ]

            print(f"   ℹ️ Found {len(post_ids_in_stream)} total posts, fetching {len(remaining_post_ids_to_fetch)} more...")

            # Discourse API allows fetching multiple posts by ID in one request
            # You might need to chunk these if there are thousands of posts,
            # but for 40-ish, it should be fine in one go.
            # The endpoint is usually /t/TOPIC_ID/posts.json
            
            # Construct the URL for fetching remaining posts
            # Max 100 post IDs can be requested at once typically
            # You might need to loop and chunk remaining_post_ids_to_fetch if it's very large
            
            # This handles up to 100 IDs per request. Adjust if needed.
            chunk_size = 100
            for k in range(0, len(remaining_post_ids_to_fetch), chunk_size):
                chunk = remaining_post_ids_to_fetch[k:k + chunk_size]
                post_ids_param = '&'.join([f"post_ids[]={pid}" for pid in chunk])
                posts_fetch_url = f"{BASE_URL}/t/{topic_id}/posts.json?{post_ids_param}"

                try:
                    posts_res = session.get(posts_fetch_url, headers=HEADERS, cookies=current_cookie)
                    if posts_res.status_code != 200:
                        print(f"   ⚠️ Error fetching additional posts for topic {topic_id}: HTTP {posts_res.status_code}")
                        continue
                    
                    additional_posts_data = posts_res.json()
                    for p in additional_posts_data.get("post_stream", {}).get("posts", []):
                        full_thread_posts[p["id"]] = p # Add new posts to our collection
                    
                    # Be polite to the server
                    time.sleep(1) # Small delay between chunks if multiple requests are made

                except Exception as fetch_e:
                    print(f"   ❌ Error fetching chunk of posts for topic {topic_id}: {fetch_e}")
                    continue
        
        # Convert the dictionary of posts back into a sorted list by post_number
        # Use post_ids_in_stream to maintain the original order
        sorted_posts = []
        for post_id in post_ids_in_stream:
            if post_id in full_thread_posts:
                sorted_posts.append(full_thread_posts[post_id])
                
        # Now, process all collected posts
        thread_posts_formatted = [{
            "post_number": post["post_number"],
            "username": post["username"],
            "created_at": post["created_at"],
            "cooked": post["cooked"]
        } for post in sorted_posts]

        all_posts_data.append({
            "id": topic_id,
            "title": title,
            "slug": slug,
            "posts": thread_posts_formatted
        })

        print(f"✅ [{i + 1}/{len(threads)}] {title[:60]} - Collected {len(thread_posts_formatted)} posts.")
        time.sleep(1.2) # General delay between threads

    except Exception as e:
        print(f"❌ Error with topic {topic_id}: {e}")
        continue

# Save all posts
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(all_posts_data, f, indent=2)

print(f"\n🎉 Done! Saved all posts to '{OUTPUT_FILE}'")