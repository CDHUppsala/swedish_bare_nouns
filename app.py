# app.py
"""
Streamlit application for searching Dependency Treebank Corpora using Grew.
Supports single-chunk search, iterative multi-corpus search with live stats,
and whole-dataset unified query execution.
"""

import os
import sys
import time
import json
import pandas as pd
import streamlit as st
from pathlib import Path

# Ensure opam bin is in PATH
opam_bin = os.path.expanduser("~/.opam/default/bin")
if os.path.isdir(opam_bin) and opam_bin not in os.environ.get("PATH", "").split(os.pathsep):
    os.environ["PATH"] = f"{opam_bin}{os.pathsep}{os.environ.get('PATH', '')}"

from engine import (
    init_backend,
    discover_corpus_files,
    group_corpus_files_by_folder,
    get_corpus_chunk_map,
    search_single_corpus,
    iterate_corpora_search,
    search_unified_dataset
)

# Page configuration
st.set_page_config(
    page_title="Grew Dependency Corpus Search",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Grew backend
@st.cache_resource
def setup_grew():
    init_backend()

setup_grew()

# Application Title
st.title("🔍 Grew Dependency Corpus Search Engine")
st.caption("Query dependency treebanks individually, iterate chunk-by-chunk with statistics, or search across the entire unified dataset.")

# Discover available corpus files & folders
folder_map = group_corpus_files_by_folder("data")
all_corpus_files = discover_corpus_files("data")
total_corpus_files = len(all_corpus_files)

# --- 1. SIDEBAR: Corpus Scope Configuration ---
st.sidebar.header("📁 Corpus Scope & Selection")

if not all_corpus_files:
    st.sidebar.error("No .conllu files found in data/ directory!")
    st.stop()

# Subfolder / Group filter
folder_keys = list(folder_map.keys())
folder_options = ["🌐 All Subcorpora Folders"] + folder_keys
selected_folder = st.sidebar.selectbox("📂 Subcorpus Folder / Group:", folder_options, index=0)

if selected_folder == "🌐 All Subcorpora Folders":
    scoped_corpus_files = all_corpus_files
    folder_desc = "all folders"
else:
    scoped_corpus_files = folder_map.get(selected_folder, [])
    folder_desc = f"group '{selected_folder}'"

scoped_total = len(scoped_corpus_files)
scoped_corpus_map = {Path(f).stem: f for f in scoped_corpus_files}
scoped_corpus_names = list(scoped_corpus_map.keys())

st.sidebar.info(f"Available in {folder_desc}: **{scoped_total} subcorpus chunks**")

search_mode = st.sidebar.radio(
    "Search Mode:",
    [
        "🌐 All Subcorpora (In Selected Scope)",
        "🔄 Iterate Subcorpora (Per-Chunk Breakdown)",
        "🎯 Single Subcorpus Chunk",
        "📑 Custom Subset / Range"
    ],
    index=0
)

target_files = []

if search_mode == "🎯 Single Subcorpus Chunk":
    selected_chunk = st.sidebar.selectbox("Select Subcorpus Chunk:", scoped_corpus_names)
    target_files = [scoped_corpus_map[selected_chunk]] if selected_chunk else []

elif search_mode == "📑 Custom Subset / Range":
    subset_type = st.sidebar.radio("Selection Method:", ["First N Chunks", "Manual Multi-Select"])
    if subset_type == "First N Chunks":
        n_chunks = st.sidebar.slider("Number of Chunks:", min_value=1, max_value=scoped_total, value=min(10, scoped_total))
        target_files = scoped_corpus_files[:n_chunks]
    else:
        default_sel = scoped_corpus_names[:3] if len(scoped_corpus_names) >= 3 else scoped_corpus_names
        selected_multi = st.sidebar.multiselect("Choose Chunks:", scoped_corpus_names, default=default_sel)
        target_files = [scoped_corpus_map[name] for name in selected_multi]

elif search_mode == "🔄 Iterate Subcorpora (Per-Chunk Breakdown)":
    limit_chunks = st.sidebar.checkbox("Limit number of chunks to iterate", value=False)
    if limit_chunks:
        n_chunks = st.sidebar.slider("Chunks to iterate:", min_value=1, max_value=scoped_total, value=min(20, scoped_total))
        target_files = scoped_corpus_files[:n_chunks]
    else:
        target_files = scoped_corpus_files

elif search_mode.startswith("🌐 All Subcorpora"):
    target_files = scoped_corpus_files

st.sidebar.markdown(f"**Target Files Selected:** {len(target_files)}")

# Settings
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Display Settings")
max_sample_matches = st.sidebar.slider("Max Sample Matches to Display:", min_value=5, max_value=200, value=25, step=5)


# --- 2. QUERY DEFINITION ---
st.subheader("📝 Query Definition")

preset_queries = {
    "Custom Request": "",
    "Swedish: Subject-Verb (V -[SS]-> S)": 'pattern {\n  V [xpos="VB"];\n  S [xpos="NN"|"PN"];\n  V -[SS]-> S;\n}',
    "Swedish: Direct Object (V -[OO]-> O)": 'pattern {\n  V [xpos="VB"];\n  O [xpos="NN"];\n  V -[OO]-> O;\n}',
    "Swedish: Inverted Word Order (V precedes S)": 'pattern {\n  V [xpos="VB"];\n  S [xpos="NN"|"PN"];\n  V -[SS]-> S;\n  V < S;\n}',
    "Swedish: Passive Verb with Agent": 'pattern {\n  V [xpos="VB", Voice="Pass"];\n  P [xpos="PP"];\n  V -> P;\n}',
    "UD: Subject (V -[nsubj]-> N)": 'pattern {\n  V [upos=VERB];\n  N [upos=NOUN|PRON];\n  V -[nsubj]-> N;\n}',
    "UD: Direct Object (V -[obj]-> N)": 'pattern {\n  V [upos=VERB];\n  N [upos=NOUN|PRON];\n  V -[obj]-> N;\n}',
    "UD: Adjective modifying Noun": 'pattern {\n  N [upos=NOUN];\n  A [upos=ADJ];\n  N -[amod]-> A;\n}'
}

col_preset, col_clear = st.columns([3, 1])
with col_preset:
    selected_preset = st.selectbox("Preset Query Templates:", list(preset_queries.keys()), index=1)

default_text = preset_queries[selected_preset] if selected_preset != "Custom Request" else 'pattern {\n  V [xpos="VB"];\n  N [xpos="NN"];\n  V -[SS]-> N;\n}'
query_str = st.text_area("Grew Query Syntax (Grew / GRS pattern):", value=default_text, height=140)

# Search Trigger
run_search = st.button("🚀 Run Search", type="primary", use_container_width=True)


# --- 3. SEARCH EXECUTION & RESULTS ---
if run_search:
    if not query_str.strip():
        st.warning("Please enter a valid Grew query pattern before running.")
        st.stop()

    if not target_files:
        st.warning("No subcorpus files selected.")
        st.stop()

    start_time = time.time()
    
    # Progress UI placeholders
    progress_bar = st.progress(0.0)
    status_text = st.empty()

    try:
        if search_mode == "🎯 Single Subcorpus Chunk":
            file_path = target_files[0]
            status_text.text(f"Searching {Path(file_path).stem}...")
            matches, total_sentences = search_single_corpus(
                file_path=file_path,
                query_str=query_str,
                extract_sentence_text=True,
                max_matches=max_sample_matches
            )
            elapsed = time.time() - start_time
            progress_bar.progress(1.0)
            status_text.text("Search completed.")

            # Metrics
            st.markdown("### 📊 Search Results Summary")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Matches", len(matches))
            m2.metric("Sentences Scanned", total_sentences)
            m3.metric("Match Frequency", f"{(len(matches) / total_sentences * 1000):.1f} / 1k sents" if total_sentences else "0")
            m4.metric("Elapsed Time", f"{elapsed:.2f}s")

            # Sample matches
            sample_matches = matches

        else:
            # Multi-corpus iteration / Unified Dataset search
            total_targets = len(target_files)
            chunk_stats_list = []
            collected_sample_matches = []
            total_matches_count = 0
            total_sentences_count = 0

            for chunk_data in iterate_corpora_search(
                file_paths=target_files,
                query_str=query_str,
                extract_sentence_text=True
            ):
                idx = len(chunk_stats_list) + 1
                cnt = chunk_data["matches_count"]
                sents = chunk_data["sentences_count"]
                
                total_matches_count += cnt
                total_sentences_count += sents

                ratio = round((cnt / sents * 1000) if sents > 0 else 0, 1)
                chunk_stats_list.append({
                    "Subcorpus Chunk": chunk_data["chunk"],
                    "Sentences": sents,
                    "Matches": cnt,
                    "Matches / 1k": ratio
                })

                # Collect sample matches across chunks
                for m in chunk_data.get("matches", []):
                    if len(collected_sample_matches) < max_sample_matches:
                        collected_sample_matches.append(m)

                # Update live progress
                progress_bar.progress(idx / total_targets)
                status_text.text(f"Searching [{idx}/{total_targets}] {chunk_data['chunk']}... Found: {total_matches_count} matches so far")

            elapsed = time.time() - start_time
            status_text.text(f"Completed search across {total_targets} subcorpus files in {elapsed:.2f}s.")

            # Metrics
            st.markdown("### 📊 Search Results Summary")
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Total Matches", f"{total_matches_count:,}")
            m2.metric("Total Sentences", f"{total_sentences_count:,}")
            m3.metric("Subcorpora Scanned", total_targets)
            m4.metric("Average Frequency", f"{(total_matches_count / total_sentences_count * 1000):.1f} / 1k" if total_sentences_count else "0")
            m5.metric("Elapsed Time", f"{elapsed:.2f}s")

            sample_matches = collected_sample_matches

            # Per-Chunk Breakdown View
            if chunk_stats_list:
                df_stats = pd.DataFrame(chunk_stats_list)
                
                st.markdown("### 📈 Subcorpus Distribution Breakdown")
                tab_table, tab_chart = st.tabs(["📋 Table View", "📊 Chart View"])
                
                with tab_table:
                    st.dataframe(df_stats, use_container_width=True, hide_index=True)
                
                with tab_chart:
                    st.bar_chart(df_stats.set_index("Subcorpus Chunk")["Matches"])

        # --- 4. MATCH DETAILS DISPLAY ---
        st.markdown("---")
        st.subheader(f"🔎 Match Inspector (Displaying {min(len(sample_matches), max_sample_matches)} of {len(sample_matches) if search_mode == '🎯 Single Subcorpus Chunk' else total_matches_count} matches)")

        if not sample_matches:
            st.info("No matching occurrences found for the given pattern.")
        else:
            for idx, item in enumerate(sample_matches[:max_sample_matches]):
                chunk_lbl = f"[{item.get('chunk', '')}] " if item.get('chunk') else ""
                sent_id = item.get("sent_id", "N/A")
                expander_title = f"{chunk_lbl}Match #{idx + 1} — Sentence ID: {sent_id}"

                with st.expander(expander_title, expanded=(idx < 3)):
                    # Sentence text
                    if item.get("sentence_text"):
                        st.markdown(f"**Sentence Text:**")
                        st.info(item["sentence_text"])

                    # Matched tokens breakdown
                    matched_tokens = item.get("matched_tokens", {})
                    if matched_tokens:
                        st.markdown("**Matched Variables & Tokens:**")
                        token_cols = st.columns(min(len(matched_tokens), 4))
                        for col, (var, t_info) in zip(token_cols, matched_tokens.items()):
                            with col:
                                st.markdown(f"**`{var}` (Node #{t_info.get('node_id')}):**")
                                st.markdown(f"- **Form:** `{t_info.get('form', '')}`")
                                st.markdown(f"- **Lemma:** `{t_info.get('lemma', '')}`")
                                st.markdown(f"- **POS (XPOS/UPOS):** `{t_info.get('xpos', '') or t_info.get('upos', '')}`")

                    # JSON data
                    with st.expander("Show Raw Match JSON", expanded=False):
                        st.json(item)

        # --- 5. EXPORT OPTIONS ---
        st.markdown("---")
        st.subheader("💾 Export Results")
        exp_col1, exp_col2 = st.columns(2)
        
        with exp_col1:
            json_str = json.dumps(sample_matches, indent=2, ensure_ascii=False)
            st.download_button(
                label="📥 Download Sample Matches (JSON)",
                data=json_str,
                file_name="grew_search_matches.json",
                mime="application/json",
                use_container_width=True
            )

        with exp_col2:
            if 'df_stats' in locals():
                csv_data = df_stats.to_csv(index=False)
                st.download_button(
                    label="📥 Download Subcorpus Stats (CSV)",
                    data=csv_data,
                    file_name="subcorpus_match_stats.csv",
                    mime="text/csv",
                    use_container_width=True
                )

    except Exception as e:
        st.error(f"Error during search execution: {e}")
