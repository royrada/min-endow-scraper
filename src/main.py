import sys
import os
import re
import requests
import time
import random
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, urljoin
from collections import deque
from bs4 import BeautifulSoup
from config import load_parameters_txt
# Load config globally so ALL functions can see it immediately
config = load_parameters_txt('inputs/parameters.txt')

from scraper import (
    normalize_url, load_names, contains_name, get_mobile_user_agent, delay,
    make_candidate_url, make_redflag_url, make_visited_url
)
from quote_extraction import extract_visible_text, extract_quotes_from_text
from output import write_outputs, write_all_best_quotes


def is_xml_response(url, response):
    content_type = response.headers.get('Content-Type', '').lower()
    parsed = urlparse(url)
    path = parsed.path.lower()
    if 'xml' in content_type:
        return True
    if path.endswith('.xml'):
        return True
    text = response.text.lstrip()
    return text.startswith('<xml') or text.startswith('<urlset') or text.startswith('<sitemapindex')

# --- Sitemap and Homepage Extraction ---
def extract_sitemap_urls(entity_url, session, dedup_normalize=True):
    # 1. Identify initial sitemap locations
    parsed = urlparse(entity_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    # Check both the standard sitemap location and the robots.txt file
    initial_search_urls = [urljoin(base, 'sitemap.xml'), urljoin(base, 'robots.txt')]
    
    sitemap_index_urls = set()
    for start_url in initial_search_urls:
        try:
            resp = session.get(start_url, timeout=10)
            if resp.status_code == 200:
                if start_url.endswith('robots.txt'):
                    for line in resp.text.splitlines():
                        if 'sitemap:' in line.lower():
                            sitemap_index_urls.add(line.split(':', 1)[1].strip())
                else:
                    sitemap_index_urls.add(start_url)
        except Exception:
            continue

    # 2. Parse sitemaps (Level 1: The Index)
    all_urls = set()
    norm_urls = set()

    for sm_url in sitemap_index_urls:
        try:
            resp = session.get(sm_url, timeout=10)
            if resp.status_code != 200:
                continue
            
            soup = BeautifulSoup(resp.text, 'xml')
            for loc in soup.find_all('loc'):
                child_url = loc.text.strip()
                
                # Check if this child is another sitemap (Level 2: Child Sitemap)
                if child_url.lower().endswith('.xml'):
                    try:
                        child_resp = session.get(child_url, timeout=10)
                        if child_resp.status_code == 200:
                            child_soup = BeautifulSoup(child_resp.text, 'xml')
                            for sub_loc in child_soup.find_all('loc'):
                                final_url = sub_loc.text.strip()
                                # Add to collection (only if not another XML)
                                if not final_url.lower().endswith('.xml'):
                                    _add_to_collection(final_url, all_urls, norm_urls, dedup_normalize)
                    except Exception:
                        continue
                else:
                    # It's a direct page URL
                    _add_to_collection(child_url, all_urls, norm_urls, dedup_normalize)
                    
        except Exception:
            continue

    return list(all_urls)[:3000]

def _add_to_collection(url, all_urls, norm_urls, dedup_normalize):
    """Helper to handle deduplication logic."""
    if dedup_normalize:
        norm = normalize_url(url)
        if norm not in norm_urls:
            norm_urls.add(norm)
            all_urls.add(url)
    else:
        all_urls.add(url)



def extract_homepage_urls(entity_url, session):
    try:
        resp = session.get(entity_url, timeout=10)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, 'html.parser')
        links = set()
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith(('mailto:', 'tel:', 'javascript:')) or href.startswith('#'):
                continue
            full_url = urljoin(entity_url, href)
            links.add(full_url)
        return list(links)
    except Exception:
        return []

# --- RedFlag Filtering ---
def filter_candidate_urls(candidate_urls, entity_url, names):
    redflags = []
    openurls = []
    parsed_entity = urlparse(entity_url)
    entity_domain = parsed_entity.netloc.split('.')[-2]
    for url in candidate_urls:
        parsed = urlparse(url)
        # RedFlag for protocol
        if parsed.scheme not in ('http', 'https'):
            redflags.append(make_redflag_url(url, 'bad_protocol'))
            continue
        # RedFlag for ?, #, or digit in path (strict)
        if '?' in parsed.path:
            print(f"DIAG_BAD_PATH: {url} flagged for '?' in path")

        is_xml = parsed.path.lower().endswith('.xml')
        if any(x in url for x in ['?', '#', '%']) or \
            (re.search(r'\d', parsed.path) and not is_xml) or \
            bool(parsed.query) or \
            bool(parsed.fragment):
                redflags.append(make_redflag_url(url, 'bad_path_or_symbol'))
                continue

        ext = os.path.splitext(parsed.path)[1]
        if ext and ext not in config.AllowedURLfileExtension:
            redflags.append(make_redflag_url(url, 'bad_extension'))
            continue
        url_domain = parsed.netloc.split('.')[-2]
        if url_domain != entity_domain:
            redflags.append(make_redflag_url(url, 'domain_mismatch'))
            continue
        norm = normalize_url(url)
        norm_lower = norm.lower()
        if any(bad.lower() in norm_lower for bad in config.URL_Bad):
            redflags.append(make_redflag_url(url, 'bad_string'))
            continue
        if contains_name(norm_lower, [n.lower() for n in names], use_regex=False):
            redflags.append(make_redflag_url(url, 'name'))
            continue
        score = sum(1 for good in config.URL_Good if good.lower() in norm_lower)
        openurls.append((-score, len(url), url))
    return redflags, openurls

# --- Quote Extraction ---
def extract_quotes(text, url, names):
    quotes = []
    rejected = []
    for min_amt in config.AllowedMins:
        for m in re.finditer(re.escape(min_amt), text):
            start = max(0, m.start() - 120)
            end = min(len(text), m.end() + 120)
            window = text[start:end]
            if contains_name(window, names, use_regex=True):
                rejected.append(make_rejected_quote(window, url, 'name'))
                continue
            if any(bad in window for bad in config.badSet):
                rejected.append(make_rejected_quote(window, url, 'badSet'))
                continue
            creationScore = sum(1 for c in config.creationSet if c in window)
            fundScore = sum(1 for f in config.fundSet if f in window)
            minScore = sum(1 for mn in config.minSet if mn in window)
            sumScore = creationScore + fundScore + minScore
            quotes.append(make_candidate_quote(window, url, creationScore, fundScore, minScore, sumScore))
    return quotes, rejected

# --- Main Scraper Function ---
def fetch_with_retry(session, url, retries=1, backoff=5):
    """Attempts to fetch a URL; retries once after a delay if it fails."""
    for i in range(retries + 1):
        try:
            resp = session.get(url, timeout=10)
            if resp.status_code == 200:
                return resp
        except Exception:
            if i < retries:
                time.sleep(backoff)
    return None

def process_entity(entity_url, names, run_dir):
    print(f"--- Starting: {entity_url} ---")
    session = requests.Session()
    session.headers['User-Agent'] = get_mobile_user_agent()
    
    CandidateURLs, CandidateURLs_set, RedFlagURLs = [], set(), []
    VisitedURLs, VisitedURLs_set = [], set()
    CandidateQuotes, RejectedQuotes, OpenQuotes, BestQuotes = [], [], [], []
    
    # Use the retry helper for the initial connection
    resp = fetch_with_retry(session, entity_url)
    if not resp:
        print(f"FAILED: Could not reach {entity_url} after retries.")
        return

    # Collect Initial URLs from the successful response
    sitemap_urls = extract_sitemap_urls(entity_url, session, dedup_normalize=True)
    homepage_urls = extract_homepage_urls(entity_url, session)
    urls_to_process = [(u, 'sitemap') for u in sitemap_urls] + [(u, 'homepage') for u in homepage_urls]
    scored_open_list = [] 
    for url, source in urls_to_process:
        norm_url = normalize_url(url)
        if norm_url not in CandidateURLs_set:
            CandidateURLs.append(make_candidate_url(url, source))
            CandidateURLs_set.add(norm_url)
            reds, items = filter_candidate_urls([url], entity_url, names)
            if reds: RedFlagURLs.extend(reds)
            elif items: scored_open_list.extend(items)

    openurls_queue = deque(sorted(scored_open_list))
    openurls_tracking_set = {item[2] for item in scored_open_list if isinstance(item, tuple)}
    visited_count, cand_q_keys, open_q_keys = 0, set(), set()

    while openurls_queue and visited_count < config.ThrottleMax:
        score_tuple = openurls_queue.popleft()
        neg_score, length, url = score_tuple
        openurls_tracking_set.discard(url)
        norm_url = normalize_url(url)
        if norm_url in VisitedURLs_set: continue
        try:
            delay(config.sleep_min, config.sleep_max)
            r = session.get(url, timeout=10)
            if r.status_code == 200:
                xml_page = is_xml_response(url, r)
                soup = BeautifulSoup(r.text, 'xml' if xml_page else 'html.parser')
                tags = soup.find_all('a', href=True) if not xml_page else soup.find_all('loc')
                new_raw = [urljoin(url, t.get('href')) if not xml_page else t.text.strip() for t in tags]
                for n_url in new_raw:
                    n_norm = normalize_url(n_url)
                    if n_norm not in CandidateURLs_set:
                        CandidateURLs.append(make_candidate_url(n_url, 'crawl'))
                        CandidateURLs_set.add(n_norm)
                        reds, items = filter_candidate_urls([n_url], entity_url, names)
                        if reds: RedFlagURLs.extend(reds)
                        elif items and items[0][2] not in openurls_tracking_set:
                            openurls_queue.append(items[0])
                            openurls_tracking_set.add(items[0][2])
                if not xml_page:
                    text = extract_visible_text(r.text)
                    q_l, r_l, o_l = extract_quotes_from_text(text, url, set(names), config)
                    for q in q_l:
                        if (normalize_url(q['url']), q['quote'].strip()) not in cand_q_keys:
                            CandidateQuotes.append(q)
                            cand_q_keys.add((normalize_url(q['url']), q['quote'].strip()))
                    RejectedQuotes.extend(r_l)
                    for oq in o_l:
                        if (normalize_url(oq['url']), oq['quote'].strip()) not in open_q_keys:
                            OpenQuotes.append(oq)
                            open_q_keys.add((normalize_url(oq['url']), oq['quote'].strip()))
                VisitedURLs.append({"url": url, "score": -neg_score, "http_status": 200, "error": None})
            else:
                VisitedURLs.append({"url": url, "score": -neg_score, "http_status": r.status_code, "error": "HTTP Error"})
        except Exception as e:
            VisitedURLs.append({"url": url, "score": -neg_score, "http_status": None, "error": str(e)})
        VisitedURLs_set.add(norm_url)
        visited_count += 1
    # Select best quotes
    filtered = [q for q in OpenQuotes if q.get('minScore', 0) > 0] or OpenQuotes.copy()
    filtered.sort(key=lambda q: q.get('sumScore', 0), reverse=True)
    for q in filtered:
        if (normalize_url(q['url']), q['quote'].strip()) not in [ (normalize_url(b['url']), b['quote'].strip()) for b in BestQuotes]:
            BestQuotes.append(q)
        if len(BestQuotes) >= 5: break
    
    # Save into the specific timestamped run directory
    entity_name = urlparse(entity_url).netloc.split('.')[-2]
    entity_outdir = os.path.join(run_dir, entity_name)
    write_outputs(entity_name, entity_outdir, CandidateURLs, RedFlagURLs, VisitedURLs, 
                  CandidateQuotes, RejectedQuotes, OpenQuotes, BestQuotes)
    print(f"--- Finished and Saved: {entity_url} ---")

def main():
    # 1. Create Timestamped Folder
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    run_dir = os.path.join('outputs', f"run_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)
    
    # 2. Load Inputs
    with open('inputs/URLs.txt', 'r', encoding='utf-8') as f:
        entity_urls = [line.strip() for line in f if line.strip()]
    names = load_names('inputs/names.txt')
    
    print(f"Starting parallel crawl in {run_dir}...")

    # 3. High-speed parallel execution
    with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
    # with ThreadPoolExecutor(max_workers) as executor:
        for url in entity_urls:
            # We pass the run_dir so workers know where to save
            executor.submit(process_entity, url, names, run_dir)
        executor.shutdown(wait=True)

    # 4. Summarize only this run
    write_all_best_quotes(run_dir)
    print(f"Batch complete. Results in: {run_dir}")

if __name__ == '__main__':
    main()
    