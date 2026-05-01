import re
from typing import List, Dict, Set

## --- Constants are now loaded from config object ---


def extract_visible_text(html: str) -> str:
    """Extract visible text from HTML (strip tags/scripts/styles)."""
    from bs4 import BeautifulSoup
    stripped = html.lstrip()
    is_xml = (
        stripped.startswith('<?xml') or
        stripped.startswith('<urlset') or
        stripped.startswith('<sitemapindex')
    )
    soup = BeautifulSoup(html, 'xml' if is_xml else 'html.parser')
    # Remove script and style elements for HTML pages.
    if not is_xml:
        for tag in soup(['script', 'style']):
            tag.decompose()
    return soup.get_text(separator=' ', strip=True)


from typing import Tuple
def extract_quotes_from_text(text: str, url: str, names: Set[str], config=None) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Implements the Plan.md quote extraction logic:
    - For each AllowedMins instance, extract 120 chars left/right (QuoteString)
    - Reject if QuoteString contains a name (>3 chars) from names.txt
    - Reject if QuoteString contains a badSet word
    - Score and move to OpenQuotes if valid
    Returns: CandidateQuotes, RejectedQuotes, OpenQuotes
    """
    CandidateQuotes = []
    RejectedQuotes = []
    OpenQuotes = []
    diagnostics = []
    found_any = False
    for min_amt in sorted(config.AllowedMins, key=lambda x: (-len(x), x)):
        pattern = re.compile(r'(?<!\d)' + re.escape(min_amt) + r'(?!\d)', re.IGNORECASE)
        for m in pattern.finditer(text):
            found_any = True
            # Extract 120 chars left/right, do not split words at boundaries
            start = max(0, m.start() - 120)
            end = min(len(text), m.end() + 120)
            # If left boundary splits a word, move start right to next non-alpha
            while start < m.start() and text[start].isalpha():
                start += 1
            # If right boundary splits a word, move end left to previous non-alpha
            while end > m.end() and text[end-1].isalpha():
                end -= 1
            quote_str = text[start:end]
            # aNum logic: string with 4+ digits, 1-2 commas, optional $ at start
            aNum_pat = re.compile(r'\$?\d{1,3}(?:,\d{3}){1,2}(?!\d)')
            aNums = list(aNum_pat.finditer(quote_str))
            # Only reject if three consecutive aNum with only whitespace/punctuation between
            rejected_table = False
            for i in range(len(aNums)-2):
                between1 = quote_str[aNums[i].end():aNums[i+1].start()]
                between2 = quote_str[aNums[i+1].end():aNums[i+2].start()]
                if not re.search(r'\w', between1) and not re.search(r'\w', between2):
                    rejected_table = True
                    break
            possible_names = set(w.lower() for w in re.findall(r'\b[a-zA-Z]{4,}\b', quote_str))
            diag = {"min_amt": min_amt, "match_start": m.start(), "match_end": m.end(), "quote": quote_str}
            if possible_names & names:
                diag["result"] = "rejected_name"
                # Name-in-URL exception
                name_in_url = False
                for n in possible_names & names:
                    if n in url.lower():
                        name_in_url = True
                        break
                if not name_in_url:
                    RejectedQuotes.append({"quote": quote_str, "url": url, "reason": "name"})
                    diagnostics.append(diag)
                    continue
            # Case-insensitive badSet check
            quote_str_lower = quote_str.lower()
            if any(bad.lower() in quote_str_lower for bad in config.badSet):
                diag["result"] = "rejected_badSet"
                RejectedQuotes.append({"quote": quote_str, "url": url, "reason": "badSet"})
                diagnostics.append(diag)
                continue
            if rejected_table:
                diag["result"] = "rejected_table_aNum"
                RejectedQuotes.append({"quote": quote_str, "url": url, "reason": "table_aNum"})
                diagnostics.append(diag)
                continue
            creationScore = sum(1 for c in config.creationSet if c.lower() in quote_str_lower)
            fundScore = sum(1 for f in config.fundSet if f.lower() in quote_str_lower)
            minScore = sum(1 for mn in config.minSet if mn.lower() in quote_str_lower)
            sumScore = creationScore + fundScore + minScore
            qdict = {
                "quote": quote_str,
                "url": url,
                "creationScore": creationScore,
                "fundScore": fundScore,
                "minScore": minScore,
                "sumScore": sumScore,
                "minAmount": min_amt
            }
            diag["result"] = "accepted"
            diag["creationScore"] = creationScore
            diag["fundScore"] = fundScore
            diag["minScore"] = minScore
            diag["sumScore"] = sumScore
            CandidateQuotes.append(qdict)
            OpenQuotes.append(qdict)
            diagnostics.append(diag)
    if not found_any:
        diagnostics.append({"result": "no_matches_found", "AllowedMins": list(config.AllowedMins)})
    return CandidateQuotes, RejectedQuotes, OpenQuotes
