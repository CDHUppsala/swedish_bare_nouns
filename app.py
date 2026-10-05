# app.py
import streamlit as st
import glob
from pathlib import Path
import grewpy
from grewpy import Corpus, Request

st.set_page_config(page_title="Corpus Search Engine", layout="wide")
st.title("🔍 Dependency Corpus Search Engine")


@st.cache_resource
def init_grew():
    grewpy.init()


init_grew()

# 1. Sidebar: Corpus Selector
st.sidebar.header("Corpus Selection")
conllu_files = glob.glob("./**/*.conllu", recursive=True)
corpus_options = {Path(f).stem: f for f in conllu_files}

selected_corpus_name = st.sidebar.selectbox("Select Corpus Chunk:", list(corpus_options.keys()))

# 2. Query Builder / Input
st.subheader("Query Definition")
preset_queries = {
    "Find all Subjects (nsubj)": "pattern { V -[nsubj]-> N }",
    "Find Direct Objects (obj)": "pattern { V -[obj]-> N }",
    "Custom Request": ""
}

selected_preset = st.selectbox("Preset Queries:", list(preset_queries.keys()))
if selected_preset == "Custom Request":
    query_str = st.text_area("Grew Query Syntax:", "pattern { N [upos=NOUN]; V [upos=VERB]; V -[nsubj]-> N }")
else:
    query_str = st.text_area("Grew Query Syntax:", preset_queries[selected_preset])

# 3. Execution & Results
if st.button("Run Search", type="primary"):
    with st.spinner("Searching corpus..."):
        file_path = corpus_options[selected_corpus_name]

        # Load corpus on demand (RAM friendly)
        corpus = Corpus(file_path)
        req = Request(query_str)
        matches = corpus.search(req)

        st.success(f"Found **{len(matches)}** matching occurrences.")

        # Display match details
        if matches:
            st.subheader("Match Details")
            for idx, match in enumerate(matches[:10]):  # Show first 10
                with st.expander(f"Match #{idx + 1} (Sentence ID: {match.get('sent_id', 'N/A')})"):
                    st.json(match)

            if len(matches) > 10:
                st.info(f"Showing first 10 of {len(matches)} results.")