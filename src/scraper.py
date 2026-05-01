# WebScraper System Main Module

"""
Implements the web scraper system as specified in plan/Plan.md.
- Modular, parameterized functions for each major task
- No virtual environment required; assumes all libraries are installed globally
- All output in Markdown or JSON as specified
- Test and production logic separated
- Mimics human browsing (user-agent, delay)
"""

import os
import re
import time
import json
import random
import requests
from urllib.parse import urlparse, urljoin
from collections import deque
from fake_useragent import UserAgent

## --- User-Defined Constants are now loaded from config object ---

# --- Utility Functions ---
def normalize_url(url):
    url = url.lower()
    # Remove protocol
    if '://' in url:
        url = url.split('://', 1)[1]
    # Split domain and path
    if '/' in url:
        domain, path = url.split('/', 1)
        path = '/' + path
    else:
        domain = url
        path = ''
    # Remove y part of x.y.z domain (second label)
    domain_parts = domain.split('.')
    if len(domain_parts) >= 3:
        # Remove the second label (y part)
        domain = '.'.join([domain_parts[0]] + domain_parts[2:])
    # Recombine domain and path
    norm = domain + path
    # Replace non-alpha chars with space
    norm = re.sub(r'[^a-z]', ' ', norm)
    norm = re.sub(r' +', ' ', norm).strip()
    return norm

def load_names(names_path):
    with open(names_path, encoding='utf-8') as f:
        # Only include names > 3 characters
        return [line.strip().lower() for line in f if line.strip() and len(line.strip()) > 3]


# Optimized for URL path: tokenize and check set intersection
def contains_name(text, names, use_regex=False):
    if use_regex:
        # For quote extraction, use regex for context
        for name in names:
            if re.search(r'(^|[^a-z])' + re.escape(name) + r'([^a-z]|$)', text, re.I):
                return True
        return False
    # For URL path, tokenize and check
    tokens = set(text.split())
    names_set = set(names)
    return not tokens.isdisjoint(names_set)

def get_mobile_user_agent():
    ua = UserAgent()
    return ua.random

def delay(s_min, s_max):
    time.sleep(random.uniform(s_min, s_max))

# --- Data Structure Creators ---
def make_candidate_url(url, source):
    return {"url": url, "source": source}

def make_redflag_url(url, criterion):
    return {"url": url, "criterion": criterion}

def make_visited_url(url, score, http_status):
    return {"url": url, "score": score, "http_status": http_status}

def make_candidate_quote(quote, url, creationScore, fundScore, minScore, sumScore):
    return {"quote": quote, "url": url, "creationScore": creationScore, "fundScore": fundScore, "minScore": minScore, "sumScore": sumScore}

def make_rejected_quote(quote, url, reason):
    return {"quote": quote, "url": url, "reason": reason}

# --- Main Scraper Logic ---
# (To be continued in next file due to size)
