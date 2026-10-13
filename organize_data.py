#!/usr/bin/env python3
"""
organize_data.py - Utility script to organize loose corpus files in the data directory.

Scans the target data directory for loose files (e.g. svt-2022_0001.conllu, da_000010.conllu)
and organizes them into clean subcorpus folders (e.g. data/svt-2022/, data/da_000010/)
so they can be queried individually or by folder in the web interface and CLI.
"""

import os
import sys
import re
import glob
import shutil
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any


def infer_subfolder_name(filename: str, mode: str = "auto", delimiter: str = "_", parts: int = 1) -> str:
    """
    Infer the subfolder name for a given filename based on naming conventions.

    Modes:
      - 'auto': Intelligently strips numeric chunk/split suffixes (e.g. svt-2022_0001 -> svt-2022,
                da_000010_0001 -> da_000010, corpus-01 -> corpus).
      - 'stem': Uses the entire file stem (e.g. file.conllu -> file).
      - 'delimiter': Splits by delimiter and takes the first N parts.
    """
    stem = Path(filename).stem

    if mode == "stem":
        return stem

    if mode == "delimiter":
        tokens = stem.split(delimiter)
        if len(tokens) >= parts:
            return delimiter.join(tokens[:parts])
        return stem

    # Default 'auto' mode
    # 1. Match standard chunk patterns like: <prefix>_<digits> or <prefix>-<digits> (e.g. svt-2022_0001 -> svt-2022)
    match_chunk = re.match(r"^(.+?)[_-]\d+$", stem)
    if match_chunk:
        return match_chunk.group(1)

    # 2. Match part/split patterns like: <prefix>.part<digits> or <prefix>_part_<digits>
    match_part = re.match(r"^(.+?)[._-](?:part|chunk)[._-]?\d+$", stem, re.IGNORECASE)
    if match_part:
        return match_part.group(1)

    # 3. Default fallback to stem
    return stem


def find_loose_files(data_dir: str = "data", pattern: str = "*.conllu", include_all: bool = False) -> List[str]:
    """Find all loose files situated directly in the root of data_dir."""
    if not os.path.isdir(data_dir):
        return []

    loose = []
    for entry in os.listdir(data_dir):
        full_path = os.path.join(data_dir, entry)
        if os.path.isfile(full_path):
            if include_all or glob.fnmatch.fnmatch(entry, pattern):
                loose.append(full_path)

    return sorted(loose)


def organize_loose_files(
    data_dir: str = "data",
    pattern: str = "*.conllu",
    mode: str = "auto",
    dry_run: bool = False,
    copy_files: bool = False,
    delimiter: str = "_",
    parts: int = 1,
    force: bool = False,
    include_all: bool = False
) -> Dict[str, Any]:
    """
    Scan loose files in data_dir and organize them into subdirectories.
    """
    data_path = Path(data_dir)
    if not data_path.exists():
        raise FileNotFoundError(f"Data directory '{data_dir}' does not exist.")

    loose_files = find_loose_files(data_dir, pattern=pattern, include_all=include_all)
    
    plan: Dict[str, List[Tuple[Path, Path]]] = {}
    total_loose = len(loose_files)

    for f in loose_files:
        src = Path(f)
        subfolder_name = infer_subfolder_name(src.name, mode=mode, delimiter=delimiter, parts=parts)
        dest_dir = data_path / subfolder_name
        dest_file = dest_dir / src.name

        plan.setdefault(subfolder_name, []).append((src, dest_file))

    executed_count = 0
    skipped_count = 0
    created_dirs = set()

    for folder_name, file_pairs in plan.items():
        dest_dir = data_path / folder_name
        if not dry_run and not dest_dir.exists():
            dest_dir.mkdir(parents=True, exist_ok=True)
            created_dirs.add(str(dest_dir))
        elif dry_run:
            created_dirs.add(str(dest_dir))

        for src, dest in file_pairs:
            if dest.exists() and not force and src != dest:
                skipped_count += 1
                continue

            if not dry_run:
                if copy_files:
                    shutil.copy2(src, dest)
                else:
                    shutil.move(src, dest)
            executed_count += 1

    return {
        "total_loose_found": total_loose,
        "total_organized": executed_count,
        "total_skipped": skipped_count,
        "folders_created": len(created_dirs),
        "plan": plan,
        "dry_run": dry_run,
        "copy_mode": copy_files
    }


def main():
    parser = argparse.ArgumentParser(
        description="Organize loose .conllu files in the data directory into subfolders."
    )
    parser.add_argument(
        "-d", "--data-dir",
        type=str,
        default="data",
        help="Target data directory (default: 'data')."
    )
    parser.add_argument(
        "-p", "--pattern",
        type=str,
        default="*.conllu",
        help="Glob pattern to match loose files (default: '*.conllu')."
    )
    parser.add_argument(
        "-m", "--mode",
        choices=["auto", "stem", "delimiter"],
        default="auto",
        help="Subfolder naming strategy: 'auto' (removes chunk numbers), 'stem' (full name), 'delimiter'."
    )
    parser.add_argument(
        "--delimiter",
        type=str,
        default="_",
        help="Delimiter to use when mode is 'delimiter' (default: '_')."
    )
    parser.add_argument(
        "--parts",
        type=int,
        default=1,
        help="Number of delimiter parts to keep for folder name (default: 1)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the reorganization without modifying files or directories on disk."
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy loose files into subfolders instead of moving them."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite destination files if they already exist."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Organize all loose files regardless of extension (not just *.conllu)."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed per-file move operations."
    )

    args = parser.parse_args()

    data_dir = args.data_dir
    if not os.path.isdir(data_dir):
        print(f"Error: Directory '{data_dir}' not found.", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning '{data_dir}' for loose files...")
    if args.dry_run:
        print("[DRY-RUN MODE: No changes will be written to disk]\n")

    summary = organize_loose_files(
        data_dir=data_dir,
        pattern=args.pattern,
        mode=args.mode,
        dry_run=args.dry_run,
        copy_files=args.copy,
        delimiter=args.delimiter,
        parts=args.parts,
        force=args.force,
        include_all=args.all
    )

    total_loose = summary["total_loose_found"]
    if total_loose == 0:
        print(f"No loose files found in '{data_dir}'. All files are already organized or none exist.")
        return

    action_label = "Copied" if args.copy else "Moved"
    if args.dry_run:
        action_label = f"Would be {action_label.lower()}"

    print(f"Found {total_loose} loose file(s) across {len(summary['plan'])} inferred group(s):")
    print("-" * 65)

    for folder_name, pairs in summary["plan"].items():
        print(f"📁 Folder: {os.path.join(data_dir, folder_name)}/ ({len(pairs)} files)")
        if args.verbose or args.dry_run:
            for src, dest in pairs:
                print(f"   -> {src.name}  ==>  {dest.relative_to(data_dir)}")

    print("-" * 65)
    print(f"Summary:")
    print(f" - Loose Files Identified : {total_loose}")
    print(f" - Files {action_label}   : {summary['total_organized']}")
    print(f" - Subfolders Created     : {summary['folders_created']}")
    if summary["total_skipped"] > 0:
        print(f" - Skipped (Already Exist): {summary['total_skipped']}")
    print(f"\nCompleted successfully.")


if __name__ == "__main__":
    main()
