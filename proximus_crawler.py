#!/usr/bin/env python3
"""
Proximus Cybersecurity Content Crawler - VERSION 6 (TEST MODE)
Limited to 100 URLs for quick testing of the entire pipeline
"""

import requests
from bs4 import BeautifulSoup
import csv
import time
from datetime import datetime
import sys
from urllib.parse import urljoin, urlparse
import warnings
from bs4 import XMLParsedAsHTMLWarning

# Suppress XML parser warning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Configuration
SITE_URL = "https://www.proximus.be"
SITEMAP_URL = "https://www.proximus.be/sitemap.xml"
OUTPUT_FILE = f"proximus_cybersecurity_audit_TEST_{datetime.now().strftime('%Y-%m-%d')}.csv"
MAX_URLS = 300  # INCREASED for better testing coverage

# Keywords to search for (case insensitive)
KEYWORDS = [
    "cybersecurity",
    "security",
    "phishing",
    "ransomware",
    "digital trust",
    "protection",
    "data breach",
    "malware",
    "threat",
    "encryption",
    "parental control",
    "secure net",
    "norton",
    "ada",
    "cyber",
    "safe online",
    "online safety",
    "digital security",
    "virus",
    "spyware",
    "firewall",
    "password",
    "authentication",
    "scam",
    "fraud",
    "trust",
    "safe"
]

# Headers to avoid bot detection
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

all_urls = []  # Now stores tuples: (url, language)

def get_urls_from_sitemaps(sitemap_url, depth=0, allowed_langs=None, current_lang="EN"):
    """Recursively extract URLs from sitemaps, tracking language"""
    if depth > 5:  # Prevent infinite recursion
        return []
    
    if allowed_langs is None:
        allowed_langs = ['en', 'fr', 'nl']  # Default languages
    
    try:
        print(f"[*] Fetching sitemap (depth {depth}): {sitemap_url}")
        response = requests.get(sitemap_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        # Parse XML properly
        soup = BeautifulSoup(response.content, 'xml')
        
        # Check if this is a sitemap index (contains other sitemaps)
        sitemaps = soup.find_all('sitemap')
        
        if sitemaps:
            print(f"[+] Found {len(sitemaps)} sitemaps in index")
            for sitemap in sitemaps:
                loc = sitemap.find('loc')
                if loc:
                    nested_url = loc.text.strip()
                    
                    # Detect language from URL
                    lang_code = "EN"
                    if 'iportal' in nested_url:
                        # Extract language from URL (iportal-en-, iportal-fr-, etc.)
                        if 'iportal-en' in nested_url:
                            lang_code = 'EN'
                        elif 'iportal-fr' in nested_url:
                            lang_code = 'FR'
                        elif 'iportal-nl' in nested_url:
                            lang_code = 'NL'
                        elif 'iportal-de' in nested_url:
                            lang_code = 'DE'
                        
                        # Only follow allowed languages
                        if lang_code.lower() not in allowed_langs:
                            print(f"[→] Skipping {lang_code} sitemap (not in allowed languages)")
                            continue
                    
                    print(f"[→] Following nested sitemap ({lang_code}): {nested_url}")
                    urls = get_urls_from_sitemaps(nested_url, depth + 1, allowed_langs, lang_code)
                    all_urls.extend(urls)
            
            return []
        
        # Otherwise extract URLs (this is an actual sitemap with URLs)
        urls = []
        url_entries = soup.find_all('url')
        
        if url_entries:
            for url_entry in url_entries:
                loc = url_entry.find('loc')
                if loc:
                    url = loc.text.strip()
                    # Only add if it's an iportal URL (main content)
                    if 'iportal' in url or '/en/' in url or '/fr/' in url or '/nl/' in url:
                        # Store tuple: (url, language)
                        urls.append((url, current_lang))
            
            print(f"[+] Found {len(urls)} content URLs in {current_lang} sitemap")
        
        return urls
        
    except Exception as e:
        print(f"[-] Error fetching {sitemap_url}: {e}")
        return []

def fetch_page(url):
    """Fetch a single page and return HTML"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"[-] Error fetching {url}: {e}")
        return None

def extract_content(html, url, language="EN"):
    """Extract title, H1, H2, meta description, and preview from HTML"""
    if not html:
        return None
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Extract title
    title_tag = soup.find('title')
    title = title_tag.text.strip() if title_tag else "No title"
    
    # Extract H1
    h1_tag = soup.find('h1')
    h1 = h1_tag.text.strip() if h1_tag else "No H1"
    
    # Extract H2s
    h2_tags = soup.find_all('h2')
    h2s = [h2.text.strip() for h2 in h2_tags[:3]]
    h2_text = " | ".join(h2s) if h2s else ""
    
    # Extract meta description
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    meta_description = meta_desc.get('content', '') if meta_desc else ""
    
    # Extract text preview (remove scripts/styles)
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
    """Check if content contains any security-related keywords"""
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
    print("=" * 60)
    print("PROXIMUS CYBERSECURITY CONTENT CRAWLER - VERSION 6 (TEST MODE)")
    print("=" * 60)
    print(f"[TEST] Limited to {MAX_URLS} URLs for quick testing")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Get URLs from sitemap (including nested)
    print("[*] Fetching sitemap structure...")
    get_urls_from_sitemaps(SITEMAP_URL)
    
    if not all_urls:
        print("[-] No URLs found in sitemaps. Trying direct URL...")
        all_urls.extend([
            ("https://www.proximus.be/en/", "EN"),
            ("https://www.proximus.be/en/family/digital-protection", "EN"),
            ("https://www.proximus.be/en/packs/options/secure-net", "EN"),
            ("https://www.proximus.be/en/business/", "EN"),
        ])
    
    # Filter to only Proximus URLs (remove duplicates but keep language info)
    # Create a dict to keep unique URLs with their languages
    unique_urls = {}
    for url, lang in all_urls:
        if 'proximus.be' in url:
            if url not in unique_urls:
                unique_urls[url] = lang
    
    proximus_urls = list(unique_urls.items())  # Back to list of tuples
    
    # LIMIT TO MAX_URLS FOR TESTING
    proximus_urls = proximus_urls[:MAX_URLS]
    
    print(f"[+] Total unique URLs to crawl: {len(proximus_urls)} (limited to {MAX_URLS} for testing)")
    print(f"    EN: {sum(1 for _, l in proximus_urls if l == 'EN')}")
    print(f"    FR: {sum(1 for _, l in proximus_urls if l == 'FR')}")
    print(f"    NL: {sum(1 for _, l in proximus_urls if l == 'NL')}")
    print()
    
    if len(proximus_urls) == 0:
        print("[-] No Proximus URLs found. Exiting.")
        sys.exit(1)
    
    # Crawl and analyze each page
    security_pages = []
    total_pages = len(proximus_urls)
    
    print(f"[*] Crawling {total_pages} pages...")
    print()
    
    for index, (url, language) in enumerate(proximus_urls, 1):
        # Print progress every 5 pages
        if index % 5 == 0 or index == 1:
            print(f"[Progress] {index}/{total_pages} ({index*100//total_pages}%)")
        
        # DEBUG: Show first few URLs being crawled
        if index <= 5:
            print(f"  [DEBUG] Crawling: {url[:80]}...")
        
        # Fetch page
        html = fetch_page(url)
        if not html:
            if index <= 10:
                print(f"  [DEBUG] Failed to fetch: {url[:80]}")
            continue
        
        # Extract content (pass language)
        content = extract_content(html, url, language)
        if not content:
            if index <= 10:
                print(f"  [DEBUG] Failed to extract: {url[:80]}")
            continue
        
        # Check if page has security keywords
        if has_security_keywords(content):
            security_pages.append(content)
            print(f"  ✓ Found security page ({language}): {url}")
        else:
            # DEBUG: Sample of pages that DON'T match
            if index <= 10:
                print(f"  [no match] {url[:60]}... | Title: {content['title'][:40]}...")
        
        # Be respectful: 0.5 second delay between requests
        time.sleep(0.5)
    
    print()
    print(f"[+] Found {len(security_pages)} pages with security-related content")
    print()
    
    # Write results to CSV
    if security_pages:
        print(f"[*] Writing results to {OUTPUT_FILE}...")
        
        # Sort by language, then by URL for better organization
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
        
        # Print summary by language
        en_count = sum(1 for p in security_pages if p['language'] == 'EN')
        fr_count = sum(1 for p in security_pages if p['language'] == 'FR')
        nl_count = sum(1 for p in security_pages if p['language'] == 'NL')
        
        print(f"[+] Summary:")
        print(f"    EN: {en_count} pages")
        print(f"    FR: {fr_count} pages")
        print(f"    NL: {nl_count} pages")
    else:
        print("[-] No security-related pages found")
    
    print()
    print("=" * 60)
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[TEST MODE COMPLETE] Ready for full crawl!")
    print("=" * 60)

if __name__ == "__main__":
    main()
