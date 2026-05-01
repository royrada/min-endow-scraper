# min-endow-scraper

**min-endow-scraper** is a Python tool for extracting, filtering, and summarizing endowment-related quotes and statistics from institutional websites. It automates the process of crawling, parsing, and aggregating relevant financial quotes, producing clean markdown outputs for further analysis.

## Features

- **Automated Web Scraping:** Extracts candidate URLs from sitemaps and homepages.
- **Quote Extraction:** Identifies and scores financial quotes using customizable keyword and pattern matching.
- **Output Aggregation:** Produces per-entity markdown summaries and a combined report with statistics.
- **Configurable Inputs:** Easily specify target institutions and all important parameters of the system.
- **No JSON Output:** All results are in human-readable markdown format.

## Usage

1. **Install Requirements**
   - Python 3+ is required.
   - Install dependencies:  
     ```
     pip install -r requests
     pip install -r beautifulsoup4

     ```

2. **Prepare Inputs**
   - Place target URLs in URLs.txt (one per line).
   - names.txt contains personal names from a public-domain library (one per line).
   - parameters.txt contains sets of string texts and numeric parameters.  The user can use the existing parameters or arbitrarily modify them.

3. **Run the Scraper**
   ```
   python main.py
   ```

4. **View Results**
   - Per-entity results: `outputs/run_datetimestamp/<entity>/` (7 markdown files per entity)
   - Combined summary: AllBestQuotes.md

## Output Structure

- `outputs/<entity>/BestQuotes.md` — Top 5 quotes for each entity
- `outputs/<entity>/CandidateURLs.md`, `RedFlagURLs.md`, `VisitedURLs.md`, `CandidateQuotes.md`, `RejectedQuotes.md`, `OpenQuotes.md` — Supporting data
- AllBestQuotes.md — Combined summary with statistics and all best quotes

## Customization

- Extend or modify output formatting in output.py.

## License

This project is released under the MIT License.

## Disclaimer

This tool is intended for research and educational purposes. 
