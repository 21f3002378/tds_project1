import requests
import json
from urllib.parse import urlencode
import time
import re

def extract_forum_session(set_cookie):
    # Match the _forum_session cookie value from Set-Cookie header
    match = re.search(r'_forum_session=([^;]+);', set_cookie)
    return match.group(1) if match else None

# Load current cookie
with open('cookie.txt', 'r') as file:
    cookie = file.read().strip()

headers = {
    "cookie": cookie,
    "user-agent": "Mozilla/5.0"
}

all_threads = []
page = 1

while True:
    print(f"🔍 Fetching search page {page}...")

    params = {
        "q": "#courses:tds-kb after:2025-01-01 before:2025-04-14 order:latest",
        "page": page
    }

    url = f"https://discourse.onlinedegree.iitm.ac.in/search.json?{urlencode(params)}"
    response = requests.get(url, headers=headers)

    # Check for Set-Cookie to refresh session
    if "set-cookie" in response.headers:
        new_cookie_value = extract_forum_session(response.headers["set-cookie"])
        if new_cookie_value:
            # Replace _forum_session in old cookie
            cookie = re.sub(r'_forum_session=[^;]+', f'_forum_session={new_cookie_value}', cookie)
            headers["cookie"] = cookie
            with open("cookie.txt", "w") as f:
                f.write(cookie)
            print("🔁 Session cookie refreshed.")

    if response.status_code != 200:
        print(f"❌ Request failed with status {response.status_code}")
        break

    data = response.json()
    topics = data.get("topics", [])
    if not topics:
        print("✅ No more topics found.")
        break

    for topic in topics:
        thread_info = {
            "id": topic["id"],
            "title": topic["title"],
            "url": f"https://discourse.onlinedegree.iitm.ac.in/t/{topic['slug']}/{topic['id']}",
        }
        all_threads.append(thread_info)
        print(f"📥 {thread_info['title']}")

    page += 1
    time.sleep(1.5)  # polite crawling delay

# Save all threads
with open("all_threads.json", "w", encoding="utf-8") as f:
    json.dump(all_threads, f, indent=2)

print(f"✅ Done. Saved {len(all_threads)} threads to all_threads.json")
