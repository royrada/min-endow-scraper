
import os
import re
import json
import requests
from bs4 import BeautifulSoup
from main import process_entity, extract_homepage_urls, filter_candidate_urls, extract_quotes
from scraper import load_names

print('test_suite.py script started')
try:
    os.makedirs('test_outputs', exist_ok=True)
    with open('test_outputs/top_level_testfile.txt', 'w', encoding='utf-8') as f:
        f.write('top level test file written')
except Exception as e:
    print('Top level file write failed:', e)

def test_sitemap_overlap():
    # Compare CandidateURLs to testing/sitemapURLs/*.txt
    test_dir = 'testing/sitemapURLs'
    names = load_names('inputs/names.txt')
    with open('inputs/URLs.txt', encoding='utf-8') as f:
        entity_urls = [line.strip() for line in f if line.strip()]
    for entity_url in entity_urls:
        entity = re.search(r'//([^/]+)/?', entity_url).group(1).split('.')[-2]
        CandidateURLs, *_ = process_entity(entity_url, names)
        candidate_set = set(c['url'] for c in CandidateURLs)
        test_file = os.path.join(test_dir, f'{entity}_sitemap_index_URLs.txt')
        if os.path.exists(test_file):
            with open(test_file, encoding='utf-8') as tf:
                gold_urls = set(line.strip() for line in tf if line.strip())
            overlap = candidate_set & gold_urls
            print(f'{entity}: {len(overlap)} / {len(gold_urls)} overlap')

def test_homepage_urls():
    # Compare homepage scraper output to testing/homepageURLs/YaleURLs.txt
    from main import extract_homepage_urls
    names = load_names('inputs/names.txt')
    yale_url = 'https://www.yale.edu/'
    homepage_urls = set(extract_homepage_urls(yale_url, None))
    with open('testing/homepageURLs/YaleURLs.txt', encoding='utf-8') as f:
        gold_urls = set(line.strip() for line in f if line.strip())
    overlap = homepage_urls & gold_urls
    print(f'Yale homepage: {len(overlap)} / {len(gold_urls)} overlap')

def test_quote_extraction():
    # Compare extracted quotes to testing/QuoteExtraction/*.csv
    test_dir = 'testing/QuoteExtraction'
    names = load_names('inputs/names.txt')
    for fname in os.listdir(test_dir):
        if fname.endswith('_Candidates.csv'):
            entity = fname.split('_')[0]
            with open(os.path.join(test_dir, fname), encoding='utf-8') as f:
                gold_quotes = set(line.strip() for line in f if line.strip())
            # Simulate extraction (not running full scraper here)
            # This is a placeholder for actual quote extraction test
            print(f'{entity}: {len(gold_quotes)} gold quotes (manual check required)')


def test_bestquotes_top_level():
    """Check that for each EntityURL in testing/testURLs.txt, the BestQuotes output for that entity contains a quote for the required URL and minimal dollar amount."""
    testfile = 'testing/testURLs.txt'
    if not os.path.exists(testfile):
        print('test_bestquotes_top_level: testURLs.txt not found')
        return
    summary_lines = []
    with open(testfile, encoding='utf-8') as f:
        for line in f:
            if not line.strip() or line.startswith('#'):
                continue
            parts = line.strip().split('\t')
            if len(parts) < 4:
                continue
            entity_url, quote_url, min_amt, gold_quote = parts[:4]
            entity = re.search(r'//([^/]+)/?', entity_url)
            if not entity:
                continue
            entity = entity.group(1).split('.')[-2]
            bestquotes_path = os.path.join('outputs', entity, 'BestQuotes.json')
            if not os.path.exists(bestquotes_path):
                summary_lines.append(f'BestQuotes file not found for {entity}\n')
                continue
            # Find all BestQuotes for this URL
            matches = []
            with open(bestquotes_path, encoding='utf-8') as bqf:
                for line in bqf:
                    try:
                        q = json.loads(line)
                    except Exception:
                        continue
                    if q.get('url') == quote_url:
                        matches.append(q)
            # Compute overlap score for each match
            def overlap_score(a, b):
                import re
                a_tokens = set(re.findall(r'\w+', a.lower()))
                b_tokens = set(re.findall(r'\w+', b.lower()))
                if not b_tokens:
                    return 0.0
                return len(a_tokens & b_tokens) / len(b_tokens)
            best_score = 0.0
            best_quote = None
            for q in matches:
                score = overlap_score(q.get('quote',''), gold_quote)
                if score > best_score:
                    best_score = score
                    best_quote = q.get('quote','')
            # Write summary
            if matches:
                summary_lines.append(f'Entity: {entity} | URL: {quote_url}\n')
                summary_lines.append(f'  Gold: {gold_quote}\n')
                summary_lines.append(f'  BestQuotes found: {len(matches)} | Best overlap: {best_score:.2f}\n')
                if best_score > 0.5:
                    summary_lines.append(f'  HIT (overlap > 0.5): {best_quote[:120]}...\n')
                else:
                    summary_lines.append(f'  MISS (overlap <= 0.5): {best_quote[:120]}...\n')
            else:
                summary_lines.append(f'Entity: {entity} | URL: {quote_url}\n')
                summary_lines.append(f'  Gold: {gold_quote}\n')
                summary_lines.append(f'  No BestQuotes found for this URL.\n')
    # Write summary to file
    os.makedirs('test_outputs', exist_ok=True)
    with open('test_outputs/bestquotes_overlap_summary.txt', 'w', encoding='utf-8') as outf:
        outf.writelines(summary_lines)


# --- Standalone diagnostic for Wayne FAQ ---
def test_quote_extraction_on_url(url, out_prefix):
    try:
        diagnostics_dir = r'C:\ALL\trusts\WebScraping\EndowmentScraper\diagnostics'
        os.makedirs(diagnostics_dir, exist_ok=True)
        names = load_names('inputs/names.txt')
        # Forced test file write to confirm execution
        with open(os.path.join(diagnostics_dir, 'diagnostic_testfile.txt'), 'w', encoding='utf-8') as f:
            f.write('test file written')
        session = requests.Session()
        resp = session.get(url, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        # Always save the raw extracted text for diagnostics
        with open(os.path.join(diagnostics_dir, f'{out_prefix}_rawtext.txt'), 'w', encoding='utf-8') as f:
            f.write(text)
        quotes, rejected = extract_quotes(text, url, names)
        # Save all candidate and rejected windows for inspection (even if empty)
        with open(os.path.join(diagnostics_dir, f'{out_prefix}_candidates.txt'), 'w', encoding='utf-8') as f:
            for q in quotes:
                f.write(f"{q['quote']}\n---\n")
        with open(os.path.join(diagnostics_dir, f'{out_prefix}_rejected.txt'), 'w', encoding='utf-8') as f:
            for r in rejected:
                f.write(f"{r['quote']}\nREASON: {r['reason']}\n---\n")
        print(f"Extracted {len(quotes)} candidate and {len(rejected)} rejected quotes for {url}")
    except Exception as e:
        os.makedirs(diagnostics_dir, exist_ok=True)
        with open(os.path.join(diagnostics_dir, 'exception.txt'), 'w', encoding='utf-8') as f:
            f.write(str(e))

    from main import extract_homepage_urls, filter_candidate_urls
    names = load_names('inputs/names.txt')
    wayne_url = 'https://giving.wayne.edu'
    session = requests.Session()
    homepage_urls = extract_homepage_urls(wayne_url, session)
    print(f"Wayne homepage URLs found: {len(homepage_urls)}")
    candidate_urls = [url for url in homepage_urls]
    redflags, openurls = filter_candidate_urls(candidate_urls, wayne_url, names)
    print(f"Wayne RedFlag URLs: {len(redflags)}")
    for rf in redflags:
        print(f"  RedFlag: {rf['url']} ({rf['criterion']})")
    print(f"Wayne openurls: {len(openurls)}")
    for score, length, url in openurls:
        print(f"  Open: {url} (score: {-score}, length: {length})")


def main():
    test_sitemap_overlap()
    test_homepage_urls()
    test_quote_extraction()
    test_bestquotes_top_level()
    # test_functional()  # Disabled: not defined
    # test_wayne_diagnostics()  # Disabled: not defined
    # Targeted quote extraction test for Wayne FAQ
    test_quote_extraction_on_url('https://giving.wayne.edu/about/faq', 'wayne_faq')

    # --- Test: PathSentence scoring for Wayne FAQ URL ---
    from scraper import normalize_url, URL_Good, load_names
    url = 'https://giving.wayne.edu/about/faq'
    norm = normalize_url(url)
    score = sum(1 for good in URL_Good if good in norm)
    print(f"Test: PathSentence for {url} is '{norm}'")
    print(f"Test: PathSentence score is {score}")
    assert score == 3, f"Expected score 3, got {score} for PathSentence: {norm}"

if __name__ == '__main__':
    import sys
    log_path = 'test_outputs/test_suite_terminal.log'
    os.makedirs('test_outputs', exist_ok=True)
    with open(log_path, 'w', encoding='utf-8') as logf:
        sys.stdout = logf
        sys.stderr = logf
        main()
