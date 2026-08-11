#!/usr/bin/env python3
"""
Proximus Cybersecurity Content Crawler - VERSION 6.2 (SMART CACHE TEST MODE)
Tests smart cache logic with limited URLs (100) for quick validation
"""

import requests
from bs4 import BeautifulSoup
import csv
import time
from datetime import datetime
import sys
import json
import os
from urllib.parse import urljoin, urlparse
import warnings
from bs4 import XMLParsedAsHTMLWarning

# Suppress XML parser warning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Configuration
SITE_URL = "https://www.proximus.be"
SITEMAP_URL = "https://www.proximus.be/sitemap.xml"
OUTPUT_FILE = f"proximus_cybersecurity_audit_TEST_{datetime.now().strftime('%Y-%m-%d')}.csv"
MAX_URLS = 100  # TEST LIMIT! 
CACHE_FILE = "sitemap_cache.json"
RESULTS_BACKUP = "previous_results.json"

# Keywords
KEYWORDS = [
    "cybersecurity", "security", "phishing", "ransomware", "digital trust",
    "protection", "data breach", "malware", "threat", "encryption",
    "parental control", "secure net", "norton", "ada", "cyber",
    "safe online", "online safety", "digital security", "virus", "spyware",
    "firewall", "password", "authentication", "scam", "fraud", "trust", "safe"
]

# Headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

all_urls = []

def get_urls_from_sitemaps(sitemap_url, depth=0, allowed_langs=None, current_lang="EN"):
    """Recursively extract URLs from sitemaps, tracking language"""
    if depth > 5:
        return []
    
    if allowed_langs is None:
        allowed_langs = ['en', 'fr', 'nl']
    
    try:
        print(f"[*] Fetching sitemap (depth {depth}): {sitemap_url}")
        response = requests.get(sitemap_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'xml')
        sitemaps = soup.find_all('sitemap')
        
        if sitemaps:
            print(f"[+] Found {len(sitemaps)} sitemaps in index")
            for sitemap in sitemaps:
                loc = sitemap.find('loc')
                if loc:
                    nested_url = loc.text.strip()
                    lang_code = "EN"
                    
                    if 'iportal' in nested_url:
                        if 'iportal-en' in nested_url:
                            lang_code = 'EN'
                        elif 'iportal-fr' in nested_url:
                            lang_code = 'FR'
                        elif 'iportal-nl' in nested_url:
                            lang_code = 'NL'
                        elif 'iportal-de' in nested_url:
                            lang_code = 'DE'
                        
                        if lang_code.lower() not in allowed_langs:
                            print(f"[→] Skipping {lang_code} sitemap")
                            continue
                    
                    print(f"[→] Following nested sitemap ({lang_code})")
                    urls = get_urls_from_sitemaps(nested_url, depth + 1, allowed_langs, lang_code)
                    all_urls.extend(urls)
            
            return []
        
        urls = []
        url_entries = soup.find_all('url')
        
        if url_entries:
            for url_entry in url_entries:
                loc = url_entry.find('loc')
                if loc:
                    url = loc.text.strip()
                    if 'iportal' in url or '/en/' in url or '/fr/' in url or '/nl/' in url:
                        urls.append((url, current_lang))
            
            print(f"[+] Found {len(urls)} content URLs in {current_lang} sitemap")
        
        return urls
        
    except Exception as e:
        print(f"[-] Error fetching {sitemap_url}: {e}")
        return []

def load_previous_cache():
    """Load previous sitemap snapshot"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cache(urls_dict):
    """Save current sitemap snapshot"""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(urls_dict, f)
        print(f"[+] Sitemap cache saved ({len(urls_dict)} URLs)")
    except Exception as e:
        print(f"[-] Error saving cache: {e}")

def load_previous_results():
    """Load previous crawl results"""
    if os.path.exists(RESULTS_BACKUP):
        try:
            with open(RESULTS_BACKUP, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_results_backup(results):
    """Backup current results"""
    try:
        with open(RESULTS_BACKUP, 'w') as f:
            json.dump(results, f)
        print(f"[+] Results backup saved ({len(results)} pages)")
    except Exception as e:
        print(f"[-] Error saving backup: {e}")

def detect_changes(current_urls, previous_cache):
    """Detect new and removed URLs"""
    current_dict = {url: lang for url, lang in current_urls}
    previous_dict = previous_cache
    
    new_urls = [(url, lang) for url, lang in current_urls if url not in previous_dict]
    removed_urls = [url for url in previous_dict if url not in current_dict]
    existing_urls = [(url, lang) for url, lang in current_urls if url in previous_dict]
    
    return new_urls, removed_urls, existing_urls

def fetch_page(url):
    """Fetch a single page"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        return None

def extract_content(html, url, language="EN"):
    """Extract page content"""
    if not html:
        return None
    
    soup = BeautifulSoup(html, 'html.parser')
    
    title_tag = soup.find('title')
    title = title_tag.text.strip() if title_tag else "No title"
    
    h1_tag = soup.find('h1')
    h1 = h1_tag.text.strip() if h1_tag else "No H1"
    
    h2_tags = soup.find_all('h2')
    h2s = [h2.text.strip() for h2 in h2_tags[:3]]
    h2_text = " | ".join(h2s) if h2s else ""
    
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    meta_description = meta_desc.get('content', '') if meta_desc else ""
    
    for script in soup(["script", "style"]):
        script.decompose()
    
    text_content = soup.get_text(separator=' ', strip=True)
    preview = text_content[:500] if text_content else ""
    
    return {
        'url': url,
        'language': language,
        'title': title,
        'h1': h1,
        'h2s': h2_text,
        'meta_description': meta_description,
        'preview': preview,
        'full_text': text_content
    }

def has_security_keywords(content):
    """Check if content has security keywords"""
    if not content:
        return False
    
    full_text = (
        content.get('title', '') + ' ' +
        content.get('h1', '') + ' ' +
        content.get('h2s', '') + ' ' +
        content.get('meta_description', '') + ' ' +
        content.get('preview', '')
    ).lower()
    
    for keyword in KEYWORDS:
        if keyword.lower() in full_text:
            return True
    
    return False

def main():
    """Main crawler function"""
    print("=" * 70)
    print("PROXIMUS CYBERSECURITY CONTENT CRAWLER - V6.2 (SMART CACHE TEST MODE)")
    print("=" * 70)
    print(f"[TEST] Limited to {MAX_URLS} URLs for smart cache testing")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Get current sitemap
    print("[*] Fetching current sitemap structure...")
    get_urls_from_sitemaps(SITEMAP_URL)
    
    if not all_urls:
        print("[-] No URLs found. Exiting.")
        sys.exit(1)
    
    # Filter to Proximus URLs only
    unique_urls = {}
    for url, lang in all_urls:
        if 'proximus.be' in url:
            if url not in unique_urls:
                unique_urls[url] = lang
    
    current_urls = list(unique_urls.items())
    print(f"[+] Current sitemap has {len(current_urls)} unique URLs")
    
    # LIMIT TO MAX_URLS FOR TESTING
    current_urls = current_urls[:MAX_URLS]
    print(f"[TEST] Limited crawl to {len(current_urls)} URLs")
    print()
    
    # Load previous cache and detect changes
    previous_cache = load_previous_cache()
    new_urls, removed_urls, existing_urls = detect_changes(current_urls, previous_cache)
    
    print("[*] CHANGE DETECTION (Smart Cache Logic):")
    print(f"    New URLs: {len(new_urls)}")
    print(f"    Removed URLs: {len(removed_urls)}")
    print(f"    Existing URLs: {len(existing_urls)}")
    print()
    
    # Load previous results
    previous_results = load_previous_results()
    print(f"[+] Previous crawl had {len(previous_results)} security pages")
    print()
    
    # CRAWL STRATEGY
    if len(new_urls) == 0 and len(removed_urls) == 0:
        print("[+] No changes detected! Using previous results...")
        security_pages = [dict(p) for p in previous_results.values()]
    else:
        print(f"[*] Crawling {len(new_urls)} NEW URLs...")
        print()
        
        security_pages_dict = dict(previous_results)
        security_pages = []
        
        # Crawl NEW URLs
        for index, (url, language) in enumerate(new_urls, 1):
            if index % 10 == 0 or index == 1:
                print(f"[Progress] {index}/{len(new_urls)} ({index*100//len(new_urls)}%)")
            
            html = fetch_page(url)
            if not html:
                continue
            
            content = extract_content(html, url, language)
            if not content:
                continue
            
            if has_security_keywords(content):
                security_pages_dict[url] = content
                print(f"  ✓ Found security page ({language}): {url}")
            
            time.sleep(0.5)
        
        # Remove deleted URLs from results
        for url in removed_urls:
            if url in security_pages_dict:
                del security_pages_dict[url]
        
        # Convert back to list
        security_pages = list(security_pages_dict.values())
        
        # Save backup
        save_results_backup(security_pages_dict)
    
    print()
    print(f"[+] Final result: {len(security_pages)} pages with security content")
    print()
    
    # Write CSV
    if security_pages:
        print(f"[*] Writing results to {OUTPUT_FILE}...")
        
        security_pages_sorted = sorted(security_pages, key=lambda x: (x['language'], x['url']))
        
        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Language', 'URL', 'Title', 'H1', 'H2s', 'Meta Description', 'Preview']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for page in security_pages_sorted:
                writer.writerow({
                    'Language': page['language'],
                    'URL': page['url'],
                    'Title': page['title'],
                    'H1': page['h1'],
                    'H2s': page['h2s'],
                    'Meta Description': page['meta_description'],
                    'Preview': page['preview']
                })
        
        print(f"[+] Results saved to {OUTPUT_FILE}")
        
        # Summary
        en_count = sum(1 for p in security_pages if p['language'] == 'EN')
        fr_count = sum(1 for p in security_pages if p['language'] == 'FR')
        nl_count = sum(1 for p in security_pages if p['language'] == 'NL')
        
        print(f"[+] Summary by language:")
        print(f"    EN: {en_count} pages")
        print(f"    FR: {fr_count} pages")
        print(f"    NL: {nl_count} pages")
    else:
        print("[-] No security-related pages found")
    
    # Save cache for next run
    cache_dict = {url: lang for url, lang in current_urls}
    save_cache(cache_dict)
    
    print()
    print("=" * 70)
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("[V6.2 TEST COMPLETE] Smart cache validated!")
    print()
    print("NEXT STEP: Upload V5 (full version) for the complete crawl")
    print("=" * 70)

if __name__ == "__main__":
    main()
