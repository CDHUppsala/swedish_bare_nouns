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

from auth import (
    authenticate_user,
    load_users,
    add_user,
    update_password,
    delete_user,
    DEFAULT_ADMIN_USER
)

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
    search_unified_dataset,
    matches_to_dataframe
)

# Page configuration
st.set_page_config(
    page_title="Grew Dependency Corpus Search",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Authentication session state initialization
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "username" not in st.session_state:
    st.session_state["username"] = None
if "app_view" not in st.session_state:
    st.session_state["app_view"] = "search"
if "search_results" not in st.session_state:
    st.session_state["search_results"] = None
if "current_match_page" not in st.session_state:
    st.session_state["current_match_page"] = 1


def login_page():
    """Render a basic, clean login page in front of the application."""
    st.markdown("<div style='text-align: center; margin-top: 50px;'>", unsafe_allow_html=True)
    st.title("🔐 Login to Grew Corpus Search")
    st.caption("Please enter your username and password to continue.")
    st.markdown("</div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log In", use_container_width=True)

            if submitted:
                if authenticate_user(username, password):
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = username.strip()
                    st.success("Login successful! Redirecting...")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

        st.info("Default administrator credentials: `admin` / `admin`")


if not st.session_state["authenticated"]:
    login_page()
    st.stop()

# --- SIDEBAR USER SESSION & NAVIGATION ---
current_user = st.session_state["username"]
st.sidebar.markdown(f"👤 Logged in as: **{current_user}**")
st.sidebar.markdown("### 🧭 Navigation")

search_btn_type = "primary" if st.session_state.get("app_view") == "search" else "secondary"
if st.sidebar.button("🔍 Corpus Search", type=search_btn_type, use_container_width=True):
    st.session_state["app_view"] = "search"
    st.rerun()

settings_btn_type = "primary" if st.session_state.get("app_view") == "settings" else "secondary"
if st.sidebar.button("⚙️ User Management Settings", type=settings_btn_type, use_container_width=True):
    st.session_state["app_view"] = "settings"
    st.rerun()

if st.sidebar.button("🚪 Log Out", use_container_width=True):
    st.session_state["authenticated"] = False
    st.session_state["username"] = None
    st.session_state["app_view"] = "search"
    st.rerun()

st.sidebar.markdown("---")

# Render User Management Settings view if selected
if st.session_state.get("app_view") == "settings":
    st.title("⚙️ User Management & Settings")
    st.caption("Manage existing users, change passwords, and create new user accounts.")

    tab_my_account, tab_all_users, tab_create_user = st.tabs([
        "🔑 My Account",
        "👥 All Users",
        "➕ Create New User"
    ])

    with tab_my_account:
        st.subheader("Change My Password")
        with st.form("change_my_password_form"):
            new_pass = st.text_input("New Password", type="password")
            confirm_pass = st.text_input("Confirm New Password", type="password")
            change_submitted = st.form_submit_button("Update Password")

            if change_submitted:
                if not new_pass:
                    st.error("Password cannot be empty.")
                elif new_pass != confirm_pass:
                    st.error("Passwords do not match.")
                else:
                    success, msg = update_password(current_user, new_pass)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)

    with tab_all_users:
        st.subheader("Existing Accounts")
        users = load_users()
        user_list = [{"Username": u, "Role": info.get("role", "user")} for u, info in users.items()]
        st.dataframe(pd.DataFrame(user_list), use_container_width=True, hide_index=True)

        st.markdown("#### Delete User Account")
        delete_candidates = [u for u in users.keys() if u != current_user]
        if not delete_candidates:
            st.info("No other user accounts available to delete.")
        else:
            with st.form("delete_user_form"):
                user_to_delete = st.selectbox("Select user to delete:", delete_candidates)
                delete_submitted = st.form_submit_button("Delete User")

                if delete_submitted:
                    success, msg = delete_user(user_to_delete, current_user=current_user)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    with tab_create_user:
        st.subheader("Create a New User")
        with st.form("create_user_form"):
            new_username = st.text_input("New Username")
            new_password = st.text_input("New Password", type="password")
            role_choice = st.selectbox("Role", ["user", "admin"])
            create_submitted = st.form_submit_button("Create User")

            if create_submitted:
                success, msg = add_user(new_username, new_password, role=role_choice)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    st.stop()

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
st.sidebar.subheader("⚙️ Match Browser Settings")
matches_per_page = st.sidebar.number_input(
    "Matches Per Page in Inspector:",
    min_value=5,
    max_value=500,
    value=25,
    step=5,
    help="Number of match cards to display per page in the Match Inspector."
)


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

col_preset, col_clear_preset = st.columns([3, 1])
with col_preset:
    selected_preset = st.selectbox("Preset Query Templates:", list(preset_queries.keys()), index=1)

default_text = preset_queries[selected_preset] if selected_preset != "Custom Request" else 'pattern {\n  V [xpos="VB"];\n  N [xpos="NN"];\n  V -[SS]-> N;\n}'
query_str = st.text_area("Grew Query Syntax (Grew / GRS pattern):", value=default_text, height=140)

# Search Trigger
col_run, col_clear_results = st.columns([4, 1])
with col_run:
    run_search = st.button("🚀 Run Search", type="primary", use_container_width=True)
with col_clear_results:
    if st.button("🗑️ Clear Results", use_container_width=True):
        st.session_state["search_results"] = None
        st.session_state["current_match_page"] = 1
        st.rerun()


# --- 3. SEARCH EXECUTION ---
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
                max_matches=None
            )
            elapsed = time.time() - start_time
            progress_bar.progress(1.0)
            status_text.text("Search completed.")

            st.session_state["search_results"] = {
                "search_mode": search_mode,
                "all_matches": matches,
                "total_matches_count": len(matches),
                "total_sentences_count": total_sentences,
                "total_targets": 1,
                "elapsed": elapsed,
                "chunk_stats_list": []
            }
            st.session_state["current_match_page"] = 1

        else:
            # Multi-corpus iteration / Unified Dataset search
            total_targets = len(target_files)
            chunk_stats_list = []
            all_matches = []
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

                # Collect all matches across chunks for export and browsing
                all_matches.extend(chunk_data.get("matches", []))

                # Update live progress
                progress_bar.progress(idx / total_targets)
                status_text.text(f"Searching [{idx}/{total_targets}] {chunk_data['chunk']}... Found: {total_matches_count} matches so far")

            elapsed = time.time() - start_time
            status_text.text(f"Completed search across {total_targets} subcorpus files in {elapsed:.2f}s.")

            st.session_state["search_results"] = {
                "search_mode": search_mode,
                "all_matches": all_matches,
                "total_matches_count": total_matches_count,
                "total_sentences_count": total_sentences_count,
                "total_targets": total_targets,
                "elapsed": elapsed,
                "chunk_stats_list": chunk_stats_list
            }
            st.session_state["current_match_page"] = 1

    except Exception as e:
        st.error(f"Error during search execution: {e}")


# --- 4. RENDER RESULTS & MATCH BROWSER ---
search_results = st.session_state.get("search_results")
if search_results is not None:
    all_matches = search_results["all_matches"]
    total_matches_count = search_results["total_matches_count"]
    total_sentences_count = search_results["total_sentences_count"]
    total_targets = search_results["total_targets"]
    elapsed = search_results["elapsed"]
    chunk_stats_list = search_results["chunk_stats_list"]
    current_search_mode = search_results["search_mode"]

    st.markdown("### 📊 Search Results Summary")
    if current_search_mode == "🎯 Single Subcorpus Chunk":
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Matches", len(all_matches))
        m2.metric("Sentences Scanned", total_sentences_count)
        m3.metric("Match Frequency", f"{(len(all_matches) / total_sentences_count * 1000):.1f} / 1k sents" if total_sentences_count else "0")
        m4.metric("Elapsed Time", f"{elapsed:.2f}s")
    else:
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total Matches", f"{total_matches_count:,}")
        m2.metric("Total Sentences", f"{total_sentences_count:,}")
        m3.metric("Subcorpora Scanned", total_targets)
        m4.metric("Average Frequency", f"{(total_matches_count / total_sentences_count * 1000):.1f} / 1k" if total_sentences_count else "0")
        m5.metric("Elapsed Time", f"{elapsed:.2f}s")

    # Per-Chunk Breakdown View
    if chunk_stats_list:
        df_stats = pd.DataFrame(chunk_stats_list)
        st.markdown("### 📈 Subcorpus Distribution Breakdown")
        tab_stat_table, tab_stat_chart = st.tabs(["📋 Table View", "📊 Chart View"])
        
        with tab_stat_table:
            st.dataframe(df_stats, use_container_width=True, hide_index=True)
        
        with tab_stat_chart:
            st.bar_chart(df_stats.set_index("Subcorpus Chunk")["Matches"])
    else:
        df_stats = None

    # --- MATCH BROWSER (Inspector Cards + Full Table) ---
    st.markdown("---")
    st.subheader(f"🔎 Match Browser ({len(all_matches):,} Total Matches)")

    if not all_matches:
        st.info("No matching occurrences found for the given pattern.")
    else:
        tab_cards, tab_table = st.tabs(["🔎 Paginated Match Inspector", "📋 All Matches Table"])

        with tab_cards:
            total_matches = len(all_matches)
            page_size = max(1, int(matches_per_page))
            total_pages = max(1, (total_matches + page_size - 1) // page_size)

            # Ensure current page in bounds
            cur_page = max(1, min(int(st.session_state.get("current_match_page", 1)), total_pages))
            st.session_state["current_match_page"] = cur_page

            # Pagination Controls
            nav_col1, nav_col2, nav_col3, nav_col4, nav_col5 = st.columns([1, 1, 2, 1, 1])
            with nav_col1:
                if st.button("⏮ First", disabled=(cur_page <= 1), use_container_width=True, key="btn_first"):
                    st.session_state["current_match_page"] = 1
                    st.rerun()
            with nav_col2:
                if st.button("◀ Prev", disabled=(cur_page <= 1), use_container_width=True, key="btn_prev"):
                    st.session_state["current_match_page"] = max(1, cur_page - 1)
                    st.rerun()
            with nav_col3:
                chosen_page = st.number_input(
                    f"Page (of {total_pages:,})",
                    min_value=1,
                    max_value=total_pages,
                    value=cur_page,
                    step=1,
                    key="match_page_selector"
                )
                if chosen_page != cur_page:
                    st.session_state["current_match_page"] = chosen_page
                    st.rerun()
            with nav_col4:
                if st.button("Next ▶", disabled=(cur_page >= total_pages), use_container_width=True, key="btn_next"):
                    st.session_state["current_match_page"] = min(total_pages, cur_page + 1)
                    st.rerun()
            with nav_col5:
                if st.button("Last ⏭", disabled=(cur_page >= total_pages), use_container_width=True, key="btn_last"):
                    st.session_state["current_match_page"] = total_pages
                    st.rerun()

            start_idx = (cur_page - 1) * page_size
            end_idx = min(start_idx + page_size, total_matches)
            st.caption(f"Showing matches **{start_idx + 1:,}** to **{end_idx:,}** of **{total_matches:,}** (Page **{cur_page:,}** of **{total_pages:,}**)")

            for idx, item in enumerate(all_matches[start_idx:end_idx]):
                match_num = start_idx + idx + 1
                chunk_lbl = f"[{item.get('chunk', '')}] " if item.get('chunk') else ""
                sent_id = item.get("sent_id", "N/A")
                expander_title = f"{chunk_lbl}Match #{match_num:,} — Sentence ID: {sent_id}"

                with st.expander(expander_title, expanded=(idx < 3)):
                    # Sentence text
                    if item.get("sentence_text"):
                        st.markdown("**Sentence Text:**")
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

        with tab_table:
            df_matches = matches_to_dataframe(all_matches)
            st.dataframe(df_matches, use_container_width=True, hide_index=True)

    # --- 5. EXPORT OPTIONS ---
    st.markdown("---")
    st.subheader("💾 Export Results")

    if all_matches:
        st.markdown(f"##### 📄 Matches Export ({len(all_matches):,} matches)")
        df_matches = matches_to_dataframe(all_matches)
        
        exp_col1, exp_col2, exp_col3 = st.columns(3)
        with exp_col1:
            json_str = json.dumps(all_matches, indent=2, ensure_ascii=False)
            st.download_button(
                label="📥 Download Matches (JSON)",
                data=json_str,
                file_name="grew_search_matches.json",
                mime="application/json",
                use_container_width=True
            )
        with exp_col2:
            csv_matches = df_matches.to_csv(index=False)
            st.download_button(
                label="📥 Download Matches (CSV)",
                data=csv_matches,
                file_name="grew_search_matches.csv",
                mime="text/csv",
                use_container_width=True
            )
        with exp_col3:
            tsv_matches = df_matches.to_csv(index=False, sep="\t")
            st.download_button(
                label="📥 Download Matches (TSV)",
                data=tsv_matches,
                file_name="grew_search_matches.tsv",
                mime="text/tab-separated-values",
                use_container_width=True
            )

    if df_stats is not None and not df_stats.empty:
        st.markdown("##### 📊 Subcorpus Statistics Export")
        stat_col1, stat_col2, stat_col3 = st.columns(3)
        with stat_col1:
            json_stats = df_stats.to_json(orient="records", indent=2)
            st.download_button(
                label="📥 Download Stats (JSON)",
                data=json_stats,
                file_name="subcorpus_match_stats.json",
                mime="application/json",
                use_container_width=True
            )
        with stat_col2:
            csv_data = df_stats.to_csv(index=False)
            st.download_button(
                label="📥 Download Stats (CSV)",
                data=csv_data,
                file_name="subcorpus_match_stats.csv",
                mime="text/csv",
                use_container_width=True
            )
        with stat_col3:
            tsv_data = df_stats.to_csv(index=False, sep="\t")
            st.download_button(
                label="📥 Download Stats (TSV)",
                data=tsv_data,
                file_name="subcorpus_match_stats.tsv",
                mime="text/tab-separated-values",
                use_container_width=True
            )
