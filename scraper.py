import requests
import feedparser
import json
import os
import re
from datetime import datetime, timedelta

# --- CONFIGURATION ---

# 1. Target Titles (Using SINGULAR forms to catch plurals too)
# "Solution Engineer" matches "Solutions Engineer" AND "Solution Engineer"
TARGET_TITLES = [
    "Solution Engineer",       # Catches "Solutions" too
    "Implementation Engineer",
    "Customer Success",        # Broader: matches "Customer Success Engineer" or "Manager"
    "Sales Engineer",
    "Account Manager",         # Broader: matches "Technical Account Manager"
    "TAM",
    "VoIP",
    "Unified Communication",
    "Voice Engineer",
    "Cybersecurity",
    "Network Security",
    "Forward Deployed",
    "Pre-Sales",               # Common synonym
    "Post-Sales"               # Common synonym
]

# 2. AI Keywords
AI_KEYWORDS = [
    "AI", "Artificial Intelligence", "LLM", "RAG", "Machine Learning", 
    "Generative", "Claude", "OpenAI", "NLP", "Model"
]

SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL')
found_jobs = []

# --- HELPER FUNCTIONS ---

def normalize_title(title):
    return title.lower().replace("-", " ").replace("/", " ")

def score_job(title, description):
    title_clean = normalize_title(title)
    desc_clean = description.lower() if description else ""
    
    # Check if ANY of your target titles exist in the job title
    is_target_role = any(role.lower() in title_clean for role in TARGET_TITLES)
    is_ai = any(k.lower() in title_clean or k.lower() in desc_clean for k in AI_KEYWORDS)
    
    return is_target_role, is_ai

def add_job(source, title, url, date_str, is_ai):
    icon = "🤖" if is_ai else "💼"
    found_jobs.append({
        "source": source,
        "title": f"{icon} {title}",
        "url": url,
        "date": date_str,
        "is_ai": is_ai
    })

def is_recent(pub_date_obj):
    """
    Checks if job is within the last 7 DAYS (to ensure you see results).
    """
    if not pub_date_obj: return True # If no date, assume fresh
    # Calculate difference
    if pub_date_obj.tzinfo:
        # If timezone aware, compare with timezone aware now
        return datetime.now(pub_date_obj.tzinfo) - pub_date_obj < timedelta(days=7)
    else:
        # If naive, compare with naive now
        return datetime.now() - pub_date_obj < timedelta(days=7)

# --- SOURCES ---

def get_wwr_jobs():
    print("Checking We Work Remotely...")
    urls = [
        "https://weworkremotely.com/categories/remote-sales-and-marketing-jobs.rss",
        "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-customer-support-jobs.rss",
        "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss"
    ]
    count = 0
    for url in urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                count += 1
                # Parse date properly
                try:
                    published = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z")
                except:
                    published = None
                
                if is_recent(published):
                    is_role, is_ai = score_job(entry.title, entry.summary)
                    if is_role:
                        add_job("WWR", entry.title, entry.link, "Recent", is_ai)
        except Exception as e:
            print(f"Error WWR: {e}")
    print(f"  > Scanned {count} items from WWR")

def get_remoteok_jobs():
    print("Checking RemoteOK...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get('https://remoteok.com/api', headers=headers)
        data = r.json()
        print(f"  > Scanned {len(data)} items from RemoteOK")
        
        for job in data[1:]: 
            # RemoteOK dates are tricky, we'll accept the top 50 recent ones
            is_role, is_ai = score_job(job.get('position', ''), job.get('description', ''))
            if is_role:
                add_job("RemoteOK", job.get('position'), job.get('url'), "Recent", is_ai)
    except Exception as e:
        print(f"Error RemoteOK: {e}")

def get_working_nomads():
    print("Checking Working Nomads...")
    try:
        urls = [
            "https://www.workingnomads.com/jobs?category=sales&rss=1",
            "https://www.workingnomads.com/jobs?category=management&rss=1",
            "https://www.workingnomads.com/jobs?category=development&rss=1",
            "https://www.workingnomads.com/jobs?category=system-administration&rss=1"
        ]
        count = 0
        for url in urls:
            feed = feedparser.parse(url)
            count += len(feed.entries)
            for entry in feed.entries:
                is_role, is_ai = score_job(entry.title, entry.description)
                if is_role:
                    add_job("WorkingNomads", entry.title, entry.link, "Recent", is_ai)
        print(f"  > Scanned {count} items from Working Nomads")
    except Exception as e:
        print(f"Error Working Nomads: {e}")

def get_remotive_jobs():
    print("Checking Remotive...")
    try:
        r = requests.get('https://remotive.com/api/remote-jobs')
        data = r.json()
        jobs = data.get('jobs', [])
        print(f"  > Scanned {len(jobs)} items from Remotive")
        
        for job in jobs:
            # Parse date
            try:
                pub_date = datetime.strptime(job.get('publication_date'), "%Y-%m-%dT%H:%M:%S")
                if not is_recent(pub_date):
                    continue
            except:
                pass 

            is_role, is_ai = score_job(job.get('title'), job.get('description'))
            if is_role:
                add_job("Remotive", job.get('title'), job.get('url'), "Recent", is_ai)
    except Exception as e:
        print(f"Error Remotive: {e}")

def send_slack_alert():
    if not found_jobs:
        print("No matching jobs found today.")
        # Send a debug message so you know it actually scanned something
        payload = {"blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "⚠️ *Debug:* Scanned feeds but found 0 matches. (Try broadening keywords)"}}]}
        if SLACK_WEBHOOK_URL:
            requests.post(SLACK_WEBHOOK_URL, json=payload)
        return

    # Deduplicate
    unique_jobs = {job['url']: job for job in found_jobs}.values()
    sorted_jobs = sorted(unique_jobs, key=lambda x: x['is_ai'], reverse=True)
    count = len(sorted_jobs)
    
    print(f"Found {count} matching jobs. Sending to Slack...")
    
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🚀 {count} Roles Found (Last 7 Days)"
            }
        },
        {"type": "divider"}
    ]

    for job in list(sorted_jobs)[:20]: # Show top 20
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{job['source']}*: <{job['url']}|{job['title']}>"
            }
        })
    
    payload = {"blocks": blocks}
    
    if SLACK_WEBHOOK_URL:
        requests.post(SLACK_WEBHOOK_URL, json=payload)

if __name__ == "__main__":
    get_wwr_jobs()
    get_remoteok_jobs()
    get_working_nomads()
    get_remotive_jobs()
    send_slack_alert()
