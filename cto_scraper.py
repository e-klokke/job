import requests
import feedparser
import json
import os
import re
from datetime import datetime, timedelta

# --- CONFIGURATION ---

# 1. The "Symptom" Roles (Signs they need a CTO)
# If they are hiring these, they have a tech gap you can exploit.
TARGET_TITLES = [
    "IT Director",
    "Director of Technology",
    "Head of Technology",
    "Systems Administrator",
    "Operations Manager",
    "Director of Operations",
    "Video Coordinator",
    "Data Analyst",
    "Performance Analyst",
    "Product Manager"
]

# 2. The "Dream" Roles (If they actually list it)
EXEC_TITLES = [
    "Chief Technology Officer",
    "CTO",
    "VP of Engineering",
    "VP of Technology",
    "Head of Product",
    "Technical Director" # Common in soccer, often confused with coaching, but worth checking
]

# 3. Sports Context (REQUIRED for this strategy)
# We only care about IT Directors if they are in SPORTS.
SPORTS_KEYWORDS = [
    "Sports", "Academy", "Club", "League", "Athletics", "Football", "Basketball", 
    "Soccer", "Baseball", "Volleyball", "NCAA", "Varsity", "Training Facility",
    "Hudl", "Catapult", "TeamSnap", "PlayMetrics", "SportsEngine"
]

SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL')
found_jobs = []

# --- HELPER FUNCTIONS ---

def normalize_title(title):
    return title.lower().replace("-", " ").replace("/", " ")

def score_job(title, description):
    title_clean = normalize_title(title)
    desc_clean = description.lower() if description else ""
    
    # Check for Executive Roles
    is_exec = any(role.lower() in title_clean for role in EXEC_TITLES)
    
    # Check for Symptom Roles
    is_target = any(role.lower() in title_clean for role in TARGET_TITLES)
    
    # Check for Sports Context
    is_sports = any(k.lower() in title_clean or k.lower() in desc_clean for k in SPORTS_KEYWORDS)
    
    # LOGIC:
    # We want Exec Roles (Context optional, but preferred)
    # OR Target Roles ONLY if they have Sports Context
    
    if is_exec and is_sports:
        return "👑" # Perfect Match (CTO of Sports)
    elif is_exec:
        return "💼" # CTO of General Tech (Still good)
    elif is_target and is_sports:
        return "🎯" # The Pitch Opportunity (They need a CTO)
    else:
        return None # Ignore generic IT jobs

def add_job(source, title, url, date_str, icon):
    found_jobs.append({
        "source": source,
        "title": f"{icon} {title}",
        "url": url,
        "date": date_str,
        "icon": icon # For sorting
    })

def is_recent(pub_date_obj):
    if not pub_date_obj: return True
    now = datetime.now(pub_date_obj.tzinfo) if pub_date_obj.tzinfo else datetime.now()
    return now - pub_date_obj < timedelta(days=7)

# --- SOURCES ---

def get_himalayas_jobs():
    print("Checking Himalayas...")
    url = "https://himalayas.app/feed"
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            try: published = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z")
            except: published = None
            
            if is_recent(published):
                icon = score_job(entry.title, entry.summary)
                if icon: add_job("Himalayas", entry.title, entry.link, "Recent", icon)
    except Exception as e: print(f"Error Himalayas: {e}")

def get_jobspresso_jobs():
    print("Checking Jobspresso...")
    url = "https://jobspresso.co/feed/"
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            try: published = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z")
            except: published = None
            
            if is_recent(published):
                icon = score_job(entry.title, entry.description)
                if icon: add_job("Jobspresso", entry.title, entry.link, "Recent", icon)
    except Exception as e: print(f"Error Jobspresso: {e}")

def get_wwr_jobs():
    print("Checking We Work Remotely...")
    # Checking "Management" and "DevOps" for IT Director roles
    urls = [
        "https://weworkremotely.com/categories/remote-management-and-finance-jobs.rss",
        "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss", 
        "https://weworkremotely.com/categories/remote-programming-jobs.rss"
    ]
    for url in urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                try: published = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z")
                except: published = None
                
                if is_recent(published):
                    icon = score_job(entry.title, entry.summary)
                    if icon: add_job("WWR", entry.title, entry.link, "Recent", icon)
        except Exception as e: print(f"Error WWR: {e}")

def get_remoteok_jobs():
    print("Checking RemoteOK...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get('https://remoteok.com/api', headers=headers)
        data = r.json()
        for job in data[1:]: 
            icon = score_job(job.get('position', ''), job.get('description', ''))
            if icon: add_job("RemoteOK", job.get('position'), job.get('url'), "Recent", icon)
    except Exception as e: print(f"Error RemoteOK: {e}")

def get_working_nomads():
    print("Checking Working Nomads...")
    try:
        urls = [
            "https://www.workingnomads.com/jobs?category=management&rss=1",
            "https://www.workingnomads.com/jobs?category=system-administration&rss=1"
        ]
        for url in urls:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                icon = score_job(entry.title, entry.description)
                if icon: add_job("WorkingNomads", entry.title, entry.link, "Recent", icon)
    except Exception as e: print(f"Error Working Nomads: {e}")

def send_slack_alert():
    if not found_jobs:
        print("No matches found.")
        payload = {"blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "✅ *CTO Hunt Ran:* No new leads found (Last 7 Days)."}}]}
        if SLACK_WEBHOOK_URL: requests.post(SLACK_WEBHOOK_URL, json=payload)
        return

    # Deduplicate
    unique_jobs = {job['url']: job for job in found_jobs}.values()
    
    # Sort Priority: 👑 (CTO Sports) > 🎯 (Symptom/Pitch) > 💼 (Exec General)
    # Mapping icons to sort order
    priority = {"👑": 3, "🎯": 2, "💼": 1}
    sorted_jobs = sorted(unique_jobs, key=lambda x: priority.get(x['icon'], 0), reverse=True)
    count = len(sorted_jobs)
    
    print(f"Found {count} leads. Sending to Slack...")
    
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"🏆 {count} Potential CTO Leads Found"}},
        {"type": "divider"}
    ]

    for job in list(sorted_jobs)[:25]:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{job['source']}*: <{job['url']}|{job['title']}>"}
        })
    
    payload = {"blocks": blocks}
    
    if SLACK_WEBHOOK_URL: requests.post(SLACK_WEBHOOK_URL, json=payload)

if __name__ == "__main__":
    get_himalayas_jobs()
    get_jobspresso_jobs()
    get_wwr_jobs()
    get_remoteok_jobs()
    get_working_nomads()
    send_slack_alert()
