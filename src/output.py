import os
import math
import re


def write_outputs(entity, outdir, CandidateURLs, RedFlagURLs, VisitedURLs, CandidateQuotes, RejectedQuotes, OpenQuotes, BestQuotes):
    os.makedirs(outdir, exist_ok=True)

    def write_md(name, data):
        if not data:
            return
        keys = data[0].keys()
        with open(os.path.join(outdir, name + '.md'), 'w', encoding='utf-8') as f:
            f.write('| ' + ' | '.join(keys) + ' |\n')
            f.write('| ' + ' | '.join(['---'] * len(keys)) + ' |\n')
            for item in data:
                f.write('| ' + ' | '.join(str(item[k]) for k in keys) + ' |\n')

    write_md('CandidateURLs', CandidateURLs)
    write_md('RedFlagURLs', RedFlagURLs)
    write_md('VisitedURLs', VisitedURLs)
    write_md('CandidateQuotes', CandidateQuotes)
    write_md('RejectedQuotes', RejectedQuotes)
    write_md('OpenQuotes', OpenQuotes)

    # Custom BestQuotes.md output
    best_md_path = os.path.join(outdir, 'BestQuotes.md')
    with open(best_md_path, 'w', encoding='utf-8') as f:
        for idx, q in enumerate(BestQuotes[:5], 1):
            f.write(f"\n## Best Quote #{idx}\n")
            f.write(f"### URL: {q.get('url','')}\n")
            f.write(f"#### Minimal dollar amount: {q.get('minAmount','')}\n")
            f.write(f"- Quote verbatim: {q.get('quote','').strip()}\n")
            f.write(f"- creationScore: {q.get('creationScore','')}\n")
            f.write(f"- fundScore: {q.get('fundScore','')}\n")
            f.write(f"- minScore: {q.get('minScore','')}\n")
            f.write(f"- sumScore: {q.get('sumScore','')}\n")


def write_all_best_quotes(outputs_dir):
    """Aggregate all BestQuotes.md files into outputs_dir/AllBestQuotes.md."""

    def count_best_quotes(md_path):
        count = 0
        with open(md_path, encoding='utf-8') as f:
            for line in f:
                if re.match(r'^## Best Quote #', line):
                    count += 1
        return count

    subdirs = sorted(
        d for d in os.listdir(outputs_dir)
        if os.path.isdir(os.path.join(outputs_dir, d))
    )

    table_rows = []
    content_sections = []
    counts = []

    for subdir in subdirs:
        bestquotes_path = os.path.join(outputs_dir, subdir, 'BestQuotes.md')
        if not os.path.isfile(bestquotes_path):
            continue
        num_quotes = count_best_quotes(bestquotes_path)
        counts.append(num_quotes)
        table_rows.append(f'| {subdir} | {num_quotes} |')
        with open(bestquotes_path, encoding='utf-8') as f:
            quotes_content = f.read().strip()
        content_sections.append(f'# {subdir}\n\n{quotes_content}\n')

    # Summary stats
    num_with_quotes = sum(1 for c in counts if c > 0)
    total_quotes = sum(counts)
    if counts:
        mean = total_quotes / len(counts)
        variance = sum((c - mean) ** 2 for c in counts) / len(counts)
        std_dev = round(math.sqrt(variance), 2)
    else:
        std_dev = 0.0

    stats_table = (
        '| Attribute | Number |\n'
        '|---|---|\n'
        f'| Subdirectories with best quotes > 0 | {num_with_quotes} |\n'
        f'| Total best quotes | {total_quotes} |\n'
        f'| Standard deviation of best quotes | {std_dev} |'
    )

    per_entity_table = '| Subdirectory name | Number of Best Quotes |\n|---|---|\n' + '\n'.join(table_rows)

    all_content = stats_table + '\n\n' + per_entity_table + '\n\n' + '\n'.join(content_sections)

    all_best_quotes_path = os.path.join(outputs_dir, 'AllBestQuotes.md')
    with open(all_best_quotes_path, 'w', encoding='utf-8') as f:
        f.write(all_content)
