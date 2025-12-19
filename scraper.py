import requests
import feedparser
import json
import os
import re
from datetime import datetime, timedelta

# --- CONFIGURATION ---

# 1. Target Titles (Singular matches plurals)
TARGET_TITLES = [
    "Solution Engineer",       # Matches "Solutions Engineer"
    "Implementation Engineer",
    "Customer Success",        # Matches "Customer Success Engineer/Manager"
    "Sales Engineer",
    "Account Manager",         # Matches "Technical Account Manager"
    "TAM",
    "VoIP",
    "Unified Communication",
    "Voice Engineer",
    "Cybersecurity",
    "Network Security",
    "Forward Deployed",
    "Pre-Sales",
    "Post-Sales"
]

# 2. AI Keywords (Pivot)
AI_KEYWORDS = [
    "AI", "Artificial Intelligence", "LLM", "RAG", "Machine Learning", 
    "Generative", "Claude", "OpenAI", "NLP", "Model"
]

# 3. Sports Tech Keywords (Purple Squirrel)
SPORTS_KEYWORDS = [
    "Sports", "Athlete", "Fitness", "Wearable", "NBA", "NFL", "NCAA", 
    "Hudl", "Strava", "DraftKings", "FanDuel", "ESPN", "Stadium", 
    "Fan Experience", "Player Tracking", "Catapult", "Peloton", "Gaming"
]

SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL')
found_jobs = []

# --- HELPER FUNCTIONS ---

def normalize_title(title):
    return title.lower().replace("-", " ").replace("/", " ")

def score_job(title, description):
    title_clean = normalize_title(title)
    desc_clean = description.lower() if description else ""
    
    # 1. Check Title (Required)
    is_target_role = any(role.lower() in title_clean for role in TARGET_TITLES)
    
    # 2. Check Context (Bonus)
    is_ai = any(k.lower() in title_clean or k.lower() in desc_clean for k in AI_KEYWORDS)
    is_sports = any(k.lower() in title_clean or k.lower() in desc_clean for k in SPORTS_KEYWORDS)
    
    return is_target_role, is_ai, is_sports

def add_job(source, title, url, date_str, is_ai, is_sports):
    # Icons: Sports (🏅) > AI (🤖) > Standard (💼)
    if is_sports: icon = "🏅"
    elif is_ai: icon = "🤖"
    else: icon = "💼"
    
    found_jobs.append({
        "source": source,
        "title": f"{icon} {title}",
        "url": url,
        "date": date_str,
        "is_ai": is_ai,
        "is_sports": is_sports
    })

def is_recent(pub_date_obj):
    """Checks if job is within last 7 days"""
    if not pub_date_obj: return True
    now = datetime.now(pub_date_obj.tzinfo) if pub_date_obj.tzinfo else datetime.now()
    return now - pub_date_obj < timedelta(days=7)

# --- SOURCES ---

def get_himalayas_jobs():
    """Himalayas.app (High quality tech/sales roles)"""
    print("Checking Himalayas...")
    # They have a clean RSS feed for all jobs
    url = "https://himalayas.app/feed"
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            try:
                published = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z")
            except:
                published = None
                
            if is_recent(published):
                is_role, is_ai, is_sports = score_job(entry.title, entry.summary)
                if is_role:
                    add_job("Himalayas", entry.title, entry.link, "Recent", is_ai, is_sports)
    except Exception as e:
        print(f"Error Himalayas: {e}")

def get_jobspresso_jobs():
    """Jobspresso (Curated remote jobs)"""
    print("Checking Jobspresso...")
    url = "https://jobspresso.co/feed/"
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            try:
                published = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z")
            except:
                published = None
            
            if is_recent(published):
                is_role, is_ai, is_sports = score_job(entry.title, entry.description)
                if is_role:
                    add_job("Jobspresso", entry.title, entry.link, "Recent", is_ai, is_sports)
    except Exception as e:
        print(f"Error Jobspresso: {e}")

def get_wwr_jobs():
    print("Checking We Work Remotely...")
    urls = [
        "https://weworkremotely.com/categories/remote-sales-and-marketing-jobs.rss",
        "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-customer-support-jobs.rss",
        "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss"
    ]
    for url in urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                try:
                    published = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z")
                except:
                    published = None
                
                if is_recent(published):
                    is_role, is_ai, is_sports = score_job(entry.title, entry.summary)
                    if is_role:
                        add_job("WWR", entry.title, entry.link, "Recent", is_ai, is_sports)
        except Exception as e:
            print(f"Error WWR: {e}")

def get_remoteok_jobs():
    print("Checking RemoteOK...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get('https://remoteok.com/api', headers=headers)
        data = r.json()
        for job in data[1:]: 
            is_role, is_ai, is_sports = score_job(job.get('position', ''), job.get('description', ''))
            if is_role:
                add_job("RemoteOK", job.get('position'), job.get('url'), "Recent", is_ai, is_sports)
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
        for url in urls:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                is_role, is_ai, is_sports = score_job(entry.title, entry.description)
                if is_role:
                    add_job("WorkingNomads", entry.title, entry.link, "Recent", is_ai, is_sports)
    except Exception as e:
        print(f"Error Working Nomads: {e}")

def get_remotive_jobs():
    print("Checking Remotive...")
    try:
        r = requests.get('https://remotive.com/api/remote-jobs')
        data = r.json()
        for job in data.get('jobs', []):
            try:
                pub_date = datetime.strptime(job.get('publication_date'), "%Y-%m-%dT%H:%M:%S")
                if not is_recent(pub_date): continue
            except: pass 

            is_role, is_ai, is_sports = score_job(job.get('title'), job.get('description'))
            if is_role:
                add_job("Remotive", job.get('title'), job.get('url'), "Recent", is_ai, is_sports)
    except Exception as e:
        print(f"Error Remotive: {e}")

def send_slack_alert():
    if not found_jobs:
        # Debug message to ensure it ran
        print("No matches found.")
        payload = {"blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "✅ *Job Monitor Ran:* No new matches found (Last 7 Days)."}}]}
        if SLACK_WEBHOOK_URL:
            requests.post(SLACK_WEBHOOK_URL, json=payload)
        return

    # Deduplicate by URL
    unique_jobs = {job['url']: job for job in found_jobs}.values()
    
    # Sort Priority: Sports > AI > Core
    sorted_jobs = sorted(unique_jobs, key=lambda x: (x['is_sports'], x['is_ai']), reverse=True)
    count = len(sorted_jobs)
    
    print(f"Found {count} matching jobs. Sending to Slack...")
    
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🚀 {count} Roles Found (6 Sources)"
            }
        },
        {"type": "divider"}
    ]

    # Show top 25 results
    for job in list(sorted_jobs)[:25]:
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
    else:
        print(json.dumps(payload, indent=2))

if __name__ == "__main__":
    get_himalayas_jobs()   # NEW
    get_jobspresso_jobs()  # NEW
    get_wwr_jobs()
    get_remoteok_jobs()
    get_working_nomads()
    get_remotive_jobs()
    send_slack_alert()
