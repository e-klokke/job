import requests
import feedparser
import json
import os
import re
from datetime import datetime, timedelta

# --- CONFIGURATION ---
TARGET_TITLES = [
    "Solutions Engineer",
    "Implementation Engineer",
    "Customer Success Engineer",
    "Sales Engineer",
    "Technical Account Manager",
    "TAM", "CSE", "Forward Deployed"
]

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

# --- SOURCES ---
def get_wwr_jobs():
    print("Checking We Work Remotely...")
    urls = [
        "https://weworkremotely.com/categories/remote-sales-and-marketing-jobs.rss",
        "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-customer-support-jobs.rss"
    ]
    for url in urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                published = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z")
                if datetime.now(published.tzinfo) - published > timedelta(hours=24):
                    continue
                is_role, is_ai = score_job(entry.title, entry.summary)
                if is_role:
                    add_job("WWR", entry.title, entry.link, published.strftime("%Y-%m-%d"), is_ai)
        except Exception as e:
            print(f"Error WWR: {e}")

def get_remoteok_jobs():
    print("Checking RemoteOK...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get('https://remoteok.com/api', headers=headers)
        data = r.json()
        for job in data[1:]:
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
            "https://www.workingnomads.com/jobs?category=development&rss=1"
        ]
        for url in urls:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                # WN puts date in description often, but we'll assume feed is fresh
                is_role, is_ai = score_job(entry.title, entry.description)
                if is_role:
                    add_job("WorkingNomads", entry.title, entry.link, "Recent", is_ai)
    except Exception as e:
        print(f"Error Working Nomads: {e}")

def get_remotive_jobs():
    print("Checking Remotive...")
    try:
        r = requests.get('https://remotive.com/api/remote-jobs')
        data = r.json()
        for job in data.get('jobs', []):
            pub_date = datetime.strptime(job.get('publication_date'), "%Y-%m-%dT%H:%M:%S")
            if datetime.now() - pub_date > timedelta(hours=24):
                continue
            is_role, is_ai = score_job(job.get('title'), job.get('description'))
            if is_role:
                add_job("Remotive", job.get('title'), job.get('url'), "Recent", is_ai)
    except Exception as e:
        print(f"Error Remotive: {e}")

def send_slack_alert():
    unique_jobs = {job['url']: job for job in found_jobs}.values()
    sorted_jobs = sorted(unique_jobs, key=lambda x: x['is_ai'], reverse=True)
    count = len(sorted_jobs)
    
    print(f"Found {count} jobs.")

    if count == 0:
        payload = {"blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "✅ *Job Scan Complete:* No new roles found (Last 24h)."}}]}
    else:
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": f"🚀 {count} Target Roles Found"}},
            {"type": "divider"}
        ]
        for job in list(sorted_jobs)[:15]:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{job['source']}*: <{job['url']}|{job['title']}>"}
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
