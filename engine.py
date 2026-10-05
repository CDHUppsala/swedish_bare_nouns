"""
engine.py - Core search engine and utilities for Grew corpus searching.
Provides unified whole-dataset querying, chunk-wise iterative querying,
memory management, and match formatting.
"""

import os
import sys
import glob
from pathlib import Path
from typing import List, Dict, Any, Generator, Optional, Tuple, Callable

# Ensure standard opam binary path is in PATH before importing grewpy
opam_bin = os.path.expanduser("~/.opam/default/bin")
if os.path.isdir(opam_bin) and opam_bin not in os.environ.get("PATH", "").split(os.pathsep):
    os.environ["PATH"] = f"{opam_bin}{os.pathsep}{os.environ.get('PATH', '')}"

import grewpy
from grewpy import Corpus, Request, Graph


def init_backend():
    """Ensure grewpy backend is initialized."""
    try:
        grewpy.init()
    except Exception as e:
        # If already initialized or connecting
        pass


def discover_corpus_files(data_dir: str = "data") -> List[str]:
    """Find all .conllu files in the given directory or project, sorted naturally."""
    candidates = []
    if os.path.isdir(data_dir):
        candidates.extend(glob.glob(f"{data_dir}/*.conllu"))
        candidates.extend(glob.glob(f"{data_dir}/**/*.conllu", recursive=True))
    else:
        candidates.extend(glob.glob("./**/*.conllu", recursive=True))
    
    unique_map = {}
    for f in candidates:
        norm_path = os.path.normpath(f)
        if norm_path not in unique_map and os.path.isfile(norm_path):
            unique_map[norm_path] = norm_path

    sorted_files = sorted(list(unique_map.values()))
    return sorted_files


def get_corpus_chunk_map(data_dir: str = "data") -> Dict[str, str]:
    """Return dictionary mapping chunk display name (stem) to file path."""
    files = discover_corpus_files(data_dir)
    return {Path(f).stem: f for f in files}


def search_single_corpus(
    file_path: str,
    query_str: str,
    extract_sentence_text: bool = True,
    max_matches: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Search a single CONLL-U corpus chunk.
    Returns: (matches_list, total_sentence_count)
    """
    init_backend()
    req = Request(query_str)
    corpus = Corpus(file_path)
    total_sentences = len(corpus)
    raw_matches = corpus.search(req)

    results = []
    chunk_name = Path(file_path).stem
    
    limit = max_matches if max_matches is not None else len(raw_matches)
    for idx, m in enumerate(raw_matches[:limit]):
        sent_id = m.get("sent_id", "")
        item = {
            "chunk": chunk_name,
            "file_path": file_path,
            "sent_id": sent_id,
            "matching": m.get("matching", {}),
            "sentence_text": "",
            "matched_tokens": {}
        }
        
        if extract_sentence_text and sent_id:
            try:
                graph = corpus[sent_id]
                item["sentence_text"] = graph.to_sentence()
                # Extract matched node token details
                nodes_info = graph.json_data().get("nodes", {})
                matched_nodes = m.get("matching", {}).get("nodes", {})
                matched_tokens = {}
                for var_name, node_id in matched_nodes.items():
                    if node_id in nodes_info:
                        matched_tokens[var_name] = {
                            "node_id": node_id,
                            "form": nodes_info[node_id].get("form", ""),
                            "lemma": nodes_info[node_id].get("lemma", ""),
                            "upos": nodes_info[node_id].get("upos", ""),
                            "xpos": nodes_info[node_id].get("xpos", ""),
                            "feats": {k: v for k, v in nodes_info[node_id].items() if k not in ["form", "lemma", "upos", "xpos", "wordform", "textform"]}
                        }
                item["matched_tokens"] = matched_tokens
            except Exception:
                pass
        
        results.append(item)
    
    corpus.clean()
    return results, total_sentences


def iterate_corpora_search(
    file_paths: List[str],
    query_str: str,
    extract_sentence_text: bool = False,
    progress_callback: Optional[Callable[[int, int, str, int, int], None]] = None,
    stop_check: Optional[Callable[[], bool]] = None
) -> Generator[Dict[str, Any], None, None]:
    """
    Iterate over multiple corpus files one by one.
    Yields per-chunk summary dictionary:
    {
        "chunk": str,
        "file_path": str,
        "sentences_count": int,
        "matches_count": int,
        "matches": list
    }
    """
    init_backend()
    req = Request(query_str)
    total_files = len(file_paths)
    accumulated_matches = 0
    accumulated_sentences = 0

    for idx, fpath in enumerate(file_paths):
        if stop_check and stop_check():
            break
            
        chunk_name = Path(fpath).stem
        try:
            corpus = Corpus(fpath)
            sent_count = len(corpus)
            raw_matches = corpus.search(req)
            matches_count = len(raw_matches)
            
            chunk_matches = []
            for m in raw_matches:
                sent_id = m.get("sent_id", "")
                item = {
                    "chunk": chunk_name,
                    "file_path": fpath,
                    "sent_id": sent_id,
                    "matching": m.get("matching", {}),
                    "sentence_text": "",
                    "matched_tokens": {}
                }
                if extract_sentence_text and sent_id:
                    try:
                        graph = corpus[sent_id]
                        item["sentence_text"] = graph.to_sentence()
                        nodes_info = graph.json_data().get("nodes", {})
                        matched_nodes = m.get("matching", {}).get("nodes", {})
                        matched_tokens = {}
                        for var_name, node_id in matched_nodes.items():
                            if node_id in nodes_info:
                                matched_tokens[var_name] = {
                                    "node_id": node_id,
                                    "form": nodes_info[node_id].get("form", ""),
                                    "lemma": nodes_info[node_id].get("lemma", ""),
                                    "upos": nodes_info[node_id].get("upos", ""),
                                    "xpos": nodes_info[node_id].get("xpos", ""),
                                }
                        item["matched_tokens"] = matched_tokens
                    except Exception:
                        pass
                chunk_matches.append(item)

            corpus.clean()
            
            accumulated_matches += matches_count
            accumulated_sentences += sent_count
            
            if progress_callback:
                progress_callback(idx + 1, total_files, chunk_name, matches_count, accumulated_matches)
                
            yield {
                "chunk": chunk_name,
                "file_path": fpath,
                "sentences_count": sent_count,
                "matches_count": matches_count,
                "matches": chunk_matches
            }
        except Exception as e:
            if progress_callback:
                progress_callback(idx + 1, total_files, chunk_name, 0, accumulated_matches)
            yield {
                "chunk": chunk_name,
                "file_path": fpath,
                "sentences_count": 0,
                "matches_count": 0,
                "matches": [],
                "error": str(e)
            }


def search_unified_dataset(
    file_paths: List[str],
    query_str: str,
    max_display_matches: int = 100,
    progress_callback: Optional[Callable[[int, int, str, int, int], None]] = None
) -> Dict[str, Any]:
    """
    Search across multiple files and return unified results as if it's one large dataset.
    Uses memory-safe chunked processing to avoid overflowing backend memory.
    """
    init_backend()
    all_matches = []
    chunk_stats = []
    total_sentences = 0
    total_matches = 0

    for chunk_res in iterate_corpora_search(
        file_paths=file_paths,
        query_str=query_str,
        extract_sentence_text=True,
        progress_callback=progress_callback
    ):
        cnt = chunk_res["matches_count"]
        sents = chunk_res["sentences_count"]
        total_matches += cnt
        total_sentences += sents
        
        chunk_stats.append({
            "chunk": chunk_res["chunk"],
            "sentences": sents,
            "matches": cnt,
            "match_ratio": round((cnt / sents * 1000) if sents > 0 else 0, 2)
        })
        
        # Keep detailed matches up to max_display_matches (or collect all if small)
        for m in chunk_res["matches"]:
            if len(all_matches) < max_display_matches:
                all_matches.append(m)

    return {
        "total_files": len(file_paths),
        "total_sentences": total_sentences,
        "total_matches": total_matches,
        "sample_matches": all_matches,
        "chunk_stats": chunk_stats
    }
