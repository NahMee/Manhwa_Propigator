#!/usr/bin/env python3
# scrape.py — Server-friendly main script

import base64
import json
import time
import requests
import threading
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timezone

# Import your scrapers
from scrapers.asuracomic import AsuraComicScraper
from scrapers.mangadex import MangaDexScraper

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

GITHUB_RAW_URL = "https://raw.githubusercontent.com/NahMee/Manhwa_Propigator/refs/heads/main/requests.json"
GITHUB_API_URL = "https://api.github.com/repos/NahMee/Manhwa_Propigator/contents/output/comics.json"
GITHUB_TOKEN = 

OUTPUT_DIR = Path("output")
REQUESTS_FILE = OUTPUT_DIR / "requests.json"
COMICS_FILE = OUTPUT_DIR / "comics.json"

SCRAPERS = [AsuraComicScraper(), MangaDexScraper()]

REQUESTS_POLL_INTERVAL = 30
RESCRAPE_INTERVAL = 60

# ──────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def safe_load_json(path: Path, default):
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf8"))
    except Exception as e:
        print(f"[WARN] Failed to load JSON from {path}: {e}")
        return default

def safe_save_json(path: Path, data):
    try:
        path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf8")
    except Exception as e:
        print(f"[ERROR] Failed to save JSON to {path}: {e}")

def find_scraper(url: str):
    for s in SCRAPERS:
        try:
            if s.can_handle(url):
                return s
        except Exception as e:
            print(f"[WARN] scraper.can_handle() error for {s}: {e}")
    return None

def scrape_url(url: str) -> Dict[str, Any] | None:
    scraper = find_scraper(url)
    if not scraper:
        print(f"[WARN] No scraper found for → {url}")
        return None
    try:
        print(f"[SCRAPE] using {scraper.__class__.__name__} for {url}")
        return scraper.scrape(url)
    except Exception as e:
        print(f"[ERROR] scraping {url}: {e}")
        return None

# ──────────────────────────────────────────────
# GitHub Sync Helpers
# ──────────────────────────────────────────────

def pull_requests_list_from_github():
    try:
        r = requests.get(GITHUB_RAW_URL, timeout=15)
        if r.status_code == 200:
            try:
                parsed = r.json()
            except Exception:
                REQUESTS_FILE.write_text(r.text, encoding="utf8")
                print("[GITHUB] Downloaded requests.json (raw)")
                return

            if isinstance(parsed, dict) and "requests" in parsed and isinstance(parsed["requests"], list):
                requests_list = parsed["requests"]
                REQUESTS_FILE.write_text(json.dumps(requests_list, indent=4, ensure_ascii=False), encoding="utf8")
                print("[GITHUB] Downloaded requests.json (normalized)")
            else:
                REQUESTS_FILE.write_text(json.dumps(parsed, indent=4, ensure_ascii=False), encoding="utf8")
                print("[GITHUB] Downloaded requests.json")
        else:
            print(f"[GITHUB] Failed to download requests.json — {r.status_code}")
    except Exception as e:
        print(f"[GITHUB ERROR] pull requests list: {e}")

def github_get_file_sha():
    try:
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
        r = requests.get(GITHUB_API_URL, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json().get("sha")
        elif r.status_code == 404:
            return None
        else:
            print(f"[GITHUB] GET file error {r.status_code}: {r.text[:150]}")
            return None
    except Exception as e:
        print(f"[GITHUB ERROR] get file sha: {e}")
        return None

def push_comics_to_github():
    try:
        if not COMICS_FILE.exists():
            print("[GITHUB] No comics.json to push.")
            return

        content_bytes = COMICS_FILE.read_bytes()
        b64_content = base64.b64encode(content_bytes).decode("utf8")

        sha = github_get_file_sha()
        payload = {"message": "Auto update comics.json", "content": b64_content}
        if sha:
            payload["sha"] = sha

        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Content-Type": "application/json"
        } if GITHUB_TOKEN else {"Content-Type": "application/json"}

        r = requests.put(GITHUB_API_URL, headers=headers, json=payload, timeout=20)
        if r.status_code in (200, 201):
            print("[GITHUB] Successfully uploaded comics.json")
        else:
            print(f"[GITHUB ERROR] Upload failed {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[GITHUB ERROR] push_comics_to_github: {e}")

# ──────────────────────────────────────────────
# Worker loops
# ──────────────────────────────────────────────

def process_requests_loop():
    while True:
        try:
            pull_requests_list_from_github()
            raw_requests = safe_load_json(REQUESTS_FILE, [])

            if isinstance(raw_requests, dict) and "requests" in raw_requests:
                requests_list = raw_requests["requests"]
            elif isinstance(raw_requests, list):
                requests_list = raw_requests
            else:
                print("[WARN] requests.json invalid format")
                requests_list = []

            comics_list = safe_load_json(COMICS_FILE, [])
            if not isinstance(comics_list, list):
                comics_list = []

            existing_sources = {entry.get("source") for entry in comics_list}

            changed = False

            for url in requests_list:
                if not isinstance(url, str):
                    continue
                if url in existing_sources:
                    continue

                scraped = scrape_url(url)
                if scraped:
                    if "source" not in scraped:
                        scraped["source"] = url

                    # TIMESTAMPS
                    scraped["created_at"] = now_iso()
                    scraped["updated_at"] = scraped["created_at"]

                    # Ensure thumbnail_url exists
                    if "thumbnail_url" not in scraped:
                        scraped["thumbnail_url"] = None

                    comics_list.append(scraped)
                    existing_sources.add(url)
                    changed = True
                    print(f"[ADD] Added {scraped.get('title','?')}")

            if changed:
                safe_save_json(COMICS_FILE, comics_list)
                push_comics_to_github()

        except Exception as e:
            print(f"[ERROR] process_requests_loop: {e}")

        time.sleep(REQUESTS_POLL_INTERVAL)

def rescrape_existing_loop():
    while True:
        try:
            comics_list = safe_load_json(COMICS_FILE, [])
            if not isinstance(comics_list, list):
                comics_list = []

            changed = False

            for idx, entry in enumerate(list(comics_list)):
                if not isinstance(entry, dict):
                    continue

                url = entry.get("source")
                if not url:
                    continue

                # Fix legacy missing timestamps
                if "created_at" not in entry:
                    entry["created_at"] = now_iso()
                if "updated_at" not in entry:
                    entry["updated_at"] = entry["created_at"]

                new_data = scrape_url(url)
                if not new_data:
                    continue

                if "source" not in new_data:
                    new_data["source"] = url

                old_cc = int(entry.get("chapter_count") or 0)
                new_cc = int(new_data.get("chapter_count") or 0)

                # Ensure thumbnail_url exists
                if "thumbnail_url" not in new_data:
                    new_data["thumbnail_url"] = entry.get("thumbnail_url")

                if new_cc != old_cc:
                    # UPDATE TIMESTAMPS
                    new_data["created_at"] = entry.get("created_at") or now_iso()
                    new_data["updated_at"] = now_iso()
                    comics_list[idx] = new_data
                    changed = True
                    print(f"[UPDATE] {new_data.get('title')} {old_cc} → {new_cc}")
                else:
                    # Keep timestamps stable
                    new_data["created_at"] = entry["created_at"]
                    new_data["updated_at"] = entry["updated_at"]
                    comics_list[idx] = new_data

            if changed:
                safe_save_json(COMICS_FILE, comics_list)
                push_comics_to_github()

        except Exception as e:
            print(f"[ERROR] rescrape_existing_loop: {e}")

        time.sleep(RESCRAPE_INTERVAL)

# ──────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────

def main():
    print("Starting Webcomic Scraper Server...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not REQUESTS_FILE.exists():
        safe_save_json(REQUESTS_FILE, [])
    if not COMICS_FILE.exists():
        safe_save_json(COMICS_FILE, [])

    t1 = threading.Thread(target=process_requests_loop, daemon=True)
    t2 = threading.Thread(target=rescrape_existing_loop, daemon=True)
    t1.start()
    t2.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")

if __name__ == "__main__":
    main()
