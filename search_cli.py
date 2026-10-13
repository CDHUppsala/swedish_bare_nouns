#!/usr/bin/env python3
"""
search_cli.py - Command-line interface for searching CONLL-U corpora with Grew.
Supports single-file search, iterative subcorpus search, and whole-dataset queries.
"""

import argparse
import sys
import json
import time
from pathlib import Path
from engine import (
    discover_corpus_files,
    search_single_corpus,
    iterate_corpora_search,
    search_unified_dataset
)

DEFAULT_PRESET_QUERY = 'pattern { V [xpos="VB"]; N [xpos="NN"]; V -[SS]-> N; }'


def main():
    parser = argparse.ArgumentParser(
        description="Search dependency treebank subcorpora using Grew query syntax."
    )
    parser.add_argument(
        "-q", "--query",
        type=str,
        default=DEFAULT_PRESET_QUERY,
        help=f"Grew pattern query. Default: '{DEFAULT_PRESET_QUERY}'"
    )
    parser.add_argument(
        "-f", "--file",
        type=str,
        default=None,
        help="Path to a single .conllu file to search."
    )
    parser.add_argument(
        "-d", "--data-dir",
        type=str,
        default="data",
        help="Directory containing .conllu files (default: 'data')."
    )
    parser.add_argument(
        "-s", "--subfolder",
        type=str,
        default=None,
        help="Filter search to a specific subfolder/group within data directory."
    )
    parser.add_argument(
        "-n", "--chunks-limit",
        type=int,
        default=None,
        help="Limit number of subcorpus chunks to search (e.g. 10)."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Search across all subcorpora in the dataset."
    )
    parser.add_argument(
        "--count-only",
        action="store_true",
        help="Output only match counts and statistics without full match trees."
    )
    parser.add_argument(
        "-m", "--max-matches",
        type=int,
        default=20,
        help="Maximum number of sample matches to display in detailed output (default: 20)."
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "summary"],
        default="text",
        help="Output format: text, json, or summary table (default: text)."
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Optional file path to save JSON results."
    )

    args = parser.parse_args()

    # Determine files to search
    if args.file:
        files = [args.file]
    else:
        files = discover_corpus_files(args.data_dir, subfolder=args.subfolder)
        if not files:
            target_desc = f"subfolder '{args.subfolder}' in directory '{args.data_dir}'" if args.subfolder else f"directory '{args.data_dir}'"
            print(f"Error: No .conllu files found in {target_desc}.", file=sys.stderr)
            sys.exit(1)
        if args.chunks_limit:
            files = files[:args.chunks_limit]

    print(f"Executing Grew search on {len(files)} subcorpus file(s)...", file=sys.stderr)
    print(f"Query: {args.query}\n", file=sys.stderr)

    start_time = time.time()

    if len(files) == 1 and not args.all:
        # Single file search
        matches, total_sents = search_single_corpus(
            files[0],
            args.query,
            extract_sentence_text=not args.count_only,
            max_matches=None if args.output else args.max_matches
        )
        elapsed = time.time() - start_time
        results_data = {
            "total_files": 1,
            "total_sentences": total_sents,
            "total_matches": len(matches),
            "elapsed_seconds": round(elapsed, 3),
            "matches": matches[:args.max_matches]
        }
    else:
        # Iterative / Multi-corpus search
        def progress(curr, total, name, m_cnt, total_m):
            sys.stderr.write(f"\r[{curr}/{total}] {name}: +{m_cnt} matches (Total: {total_m})")
            sys.stderr.flush()

        results_data = search_unified_dataset(
            file_paths=files,
            query_str=args.query,
            max_display_matches=args.max_matches,
            progress_callback=progress
        )
        elapsed = time.time() - start_time
        results_data["elapsed_seconds"] = round(elapsed, 3)
        sys.stderr.write("\n")

    # Output formatting
    if args.format == "json":
        print(json.dumps(results_data, indent=2, ensure_ascii=False))
    elif args.format == "summary":
        print("=" * 60)
        print("SEARCH SUMMARY")
        print("=" * 60)
        print(f"Files Searched : {results_data['total_files']}")
        print(f"Total Sentences: {results_data['total_sentences']}")
        print(f"Total Matches  : {results_data['total_matches']}")
        print(f"Elapsed Time   : {results_data['elapsed_seconds']}s")
        if results_data.get("chunk_stats"):
            print("\nPer-Chunk Match Stats (Top 15):")
            print(f"{'Chunk Name':<25} | {'Sentences':<10} | {'Matches':<10} | {'Ratio/1k':<10}")
            print("-" * 62)
            for cs in results_data["chunk_stats"][:15]:
                print(f"{cs['chunk']:<25} | {cs['sentences']:<10} | {cs['matches']:<10} | {cs['match_ratio']:<10}")
            if len(results_data["chunk_stats"]) > 15:
                print(f"... and {len(results_data['chunk_stats']) - 15} more chunks.")
    else:
        # Text output
        print(f"\nSearch complete: Found {results_data['total_matches']} matches in {results_data['total_sentences']} sentences across {results_data['total_files']} files ({results_data['elapsed_seconds']}s).")
        sample_list = results_data.get("sample_matches", results_data.get("matches", []))
        if sample_list and not args.count_only:
            print("\nSample Results:")
            for idx, item in enumerate(sample_list[:args.max_matches]):
                print(f"\n--- Match #{idx + 1} | Chunk: {item['chunk']} | Sent ID: {item['sent_id']} ---")
                if item.get("sentence_text"):
                    print(f"Sentence: \"{item['sentence_text']}\"")
                if item.get("matched_tokens"):
                    tokens_str = ", ".join([f"{v}={info.get('form')} ({info.get('xpos', '')})" for v, info in item["matched_tokens"].items()])
                    print(f"Matched Nodes: {tokens_str}")
                print(f"Node Mapping: {item.get('matching', {}).get('nodes', {})}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
