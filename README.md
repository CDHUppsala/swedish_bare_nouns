# 🔍 Grew Dependency Corpus Search Engine

A high-performance search engine and interactive web application for querying syntactic dependency treebanks in **CoNLL-U** format using the [Grew](https://grew.fr) graph transformation system.

The application allows linguists and NLP researchers to execute pattern queries across large multi-chunk corpora either as a **single unified dataset** or **iteratively chunk-by-chunk** with real-time progress, distribution charts, token-level match inspectors, and export capabilities. It also includes a standalone command-line interface (CLI) for automated batch queries.

---

## 📑 Table of Contents

- [Architecture & Tech Stack](#-architecture--tech-stack)
- [Prerequisites & System Requirements](#-prerequisites--system-requirements)
- [Installation & Setup](#-installation--setup)
  - [1. System Packages](#1-system-packages)
  - [2. OCaml & Grew Backend Installation](#2-ocaml--grew-backend-installation)
  - [3. Python Environment & Dependencies](#3-python-environment--dependencies)
  - [4. Corpus Data Placement](#4-corpus-data-placement)
- [Corpus Ingestion & XML Extraction (`extract.py`)](#-corpus-ingestion--xml-extraction-extractpy)
- [Running Locally](#-running-locally)
  - [Streamlit Web Application](#streamlit-web-application)
  - [Command-Line Interface (CLI)](#command-line-interface-cli)
  - [Running Tests](#running-tests)
- [Linux Server Deployment Guide](#-linux-server-deployment-guide)
  - [Architecture Overview](#architecture-overview)
  - [Step 1: Dedicated System User & Directory](#step-1-dedicated-system-user--directory)
  - [Step 2: Server-side OPAM & Grew Setup](#step-2-server-side-opam--grew-setup)
  - [Step 3: Application & Python Setup](#step-3-application--python-setup)
  - [Step 4: Systemd Service Configuration](#step-4-systemd-service-configuration)
  - [Step 5: Nginx Reverse Proxy with WebSockets](#step-5-nginx-reverse-proxy-with-websockets)
  - [Step 6: SSL / HTTPS Configuration (Let's Encrypt)](#step-6-ssl--https-configuration-lets-encrypt)
  - [Step 7: Service Management & Maintenance](#step-7-service-management--maintenance)
- [User Guide & Examples](#-user-guide--examples)
  - [Streamlit Web Interface](#streamlit-web-interface)
  - [CLI Tool (`search_cli.py`)](#cli-tool-search_clipy)
  - [Grew Query Syntax & Templates](#grew-query-syntax--templates)
- [Project Structure](#-project-structure)
- [Troubleshooting & FAQ](#-troubleshooting--faq)

---

## 🏗 Architecture & Tech Stack

The application is structured into a modular multi-tier architecture:

```
┌────────────────────────────────────────────────────────┐
│                   Streamlit Web UI                     │
│    (Filters, Preset Queries, Visualizations, Export)   │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                  Python Engine Layer                   │
│         engine.py  /  search_cli.py (CLI)              │
│  - Corpus auto-discovery (recursive folder scanning)   │
│  - Chunk iterator & memory management (corpus.clean()) │
│  - Token extraction & sentence reconstruction          │
└───────────────────────────┬────────────────────────────┘
                            │  IPC Sockets (JSON-RPC)
┌───────────────────────────▼────────────────────────────┐
│                     grewpy (Python)                    │
└───────────────────────────┬────────────────────────────┘
                            │  Subprocess Spawn
┌───────────────────────────▼────────────────────────────┐
│              grewpy_backend (OCaml Binary)             │
│            grewlib  +  conll  +  Caml runtime          │
└────────────────────────────────────────────────────────┘
```

### Components

- **Frontend / Presentation Layer:**
  - **Streamlit** (v1.40+): Web interface providing search configuration, live progress bars, summary KPI metric cards, dataframes, distribution charts (Altair / Streamlit charts), and JSON/CSV export buttons.
- **Engine & Processing Layer:**
  - `engine.py`: Core querying module providing unified whole-dataset querying, chunk-by-chunk iteration with memory cleanup, token attribute extraction, and sentence reconstruction.
  - `search_cli.py`: Production-ready CLI interface with tabular summaries, formatted text outputs, and structured JSON export.
  - `extract.py`: High-throughput, streaming XML-to-CoNLL-U parser and corpus conversion utility.
- **Linguistic Graph Matching Engine:**
  - `grewpy`: Official Python client for Grew.
  - `grewpy_backend`: Native compiled OCaml binary executing graph matching algorithms with high efficiency.
  - `conll`: OCaml parser library for CoNLL-U format.
- **Corpus Format:**
  - Standard Universal Dependencies / CoNLL-U (`.conllu`) files, stored either flat in `data/` or organized in arbitrary nested subdirectories.

---

## ⚙️ Prerequisites & System Requirements

### Hardware Requirements
- **CPU:** 2+ cores recommended.
- **RAM:** 2 GB minimum (4 GB+ recommended for large multi-gigabyte corpora). Memory footprint is kept strictly bounded via chunk-by-chunk memory recycling (`corpus.clean()`).
- **Disk:** Sufficient disk space for your `.conllu` corpora.

### Supported Operating Systems
- **Linux:** Ubuntu 20.04+, Debian 11+, RHEL/Rocky Linux 8+, Fedora, Arch Linux.
- **macOS:** macOS 12+ (Intel & Apple Silicon).

### Software Requirements
- **Python:** 3.10, 3.11, 3.12, 3.13, or 3.14.
- **OCaml / OPAM:** OPAM 2.1+ with an OCaml compiler switch (OCaml 5.2.1, 5.3.0, or 4.14.2 recommended).
- **Git**, **gcc / clang**, **make**, **curl**, **tar**, **bzip2**, **bubblewrap**.

---

## 🚀 Installation & Setup

### 1. System Packages

#### Debian / Ubuntu:
```bash
sudo apt update
sudo apt install -y build-essential curl git unzip bubblewrap m4 pkg-config opam python3 python3-venv python3-pip
```

#### RHEL / Rocky Linux 9:
```bash
sudo dnf groupinstall -y "Development Tools"
sudo dnf install -y epel-release
sudo dnf install -y opam bubblewrap m4 pkgconfig python3 python3-pip git
```

#### macOS (Homebrew):
```bash
brew install opam python
```

---

### 2. OCaml & Grew Backend Installation

The Python binding `grewpy` requires the native binary `grewpy_backend` compiled via OPAM.

1. **Initialize OPAM (if not already done):**
   ```bash
   opam init --bare -a -y
   ```

2. **Create a compatible OCaml switch:**
   ```bash
   opam switch create 5.2.1
   eval $(opam env)
   ```

3. **Add the official Grew OPAM repository:**
   ```bash
   opam remote add grew "https://opam.grew.fr"
   opam update
   ```

4. **Install `grewpy_backend` (with compatible `conll` dependency):**
   ```bash
   opam install -y grewpy_backend "conll<1.20"
   ```
   > 💡 **Version Note:** Constraining `conll<1.20` (or `conll=1.19.8`) ensures full compatibility across OCaml 4.14 through 5.4 compiler environments.

5. **Verify backend installation:**
   ```bash
   eval $(opam env)
   which grewpy_backend
   grewpy_backend --help
   ```

---

### 3. Python Environment & Dependencies

1. **Clone the repository:**
   ```bash
   git clone <repository_url> grew_frontend
   cd grew_frontend
   ```

2. **Create and activate a Python virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install Python dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Verify connection between Python and OCaml backend:**
   ```bash
   python -c "import grewpy; print('grewpy connected successfully!')"
   ```
   *(You should see `connected to port: <port_number>` followed by the success message).*

---

### 4. Corpus Data Placement

Place your `.conllu` treebank files in the `data/` directory.

You can organize your files flat or in arbitrary subfolders:
```text
data/
├── svt-2022_0001.conllu
├── svt-2022_0002.conllu
├── news/
│   ├── news_part1.conllu
│   └── news_part2.conllu
└── historical/
    └── 1800s.conllu
```

The application recursively scans and indexes all `.conllu` files automatically on launch.

---

## 📦 Corpus Ingestion & XML Extraction (`extract.py`)

If your raw corpus source is in XML format (e.g., Korp / Språkbanken XML exports), the repository includes `extract.py` to parse and convert XML treebanks directly into standard CoNLL-U format.

### How It Works

- **Streaming XML Parsing (`iterparse`):** Processes documents incrementally element-by-element, maintaining minimal memory overhead even for large multi-gigabyte XML files.
- **1-to-1 File Mapping (Default):** Converts each source XML file (e.g., `da_000010.xml`) directly into a matching `.conllu` file (e.g., `data/da_000010.conllu`) without unnecessary sub-chunking.
- **Syntactic & Morphological Field Mapping:**
  - Token reference ID $\to$ CoNLL-U `ID`
  - Word text $\to$ `FORM`
  - Base lemma $\to$ `LEMMA`
  - Part of Speech (`pos`) $\to$ `XPOS`
  - Universal / Morphological features (`ufeats`) $\to$ `FEATS`
  - Dependency head (`dephead`) $\to$ `HEAD`
  - Dependency relation (`deprel`) $\to$ `DEPREL`

### Command-Line Arguments

```text
usage: extract.py [-h] [--output_dir OUTPUT_DIR] [--split SPLIT]
                  [--max_files MAX_FILES] [--archive ARCHIVE]
                  xml_files [xml_files ...]

Positional Arguments:
  xml_files              One or more XML file paths (globs supported).

Options:
  --output_dir DIR       Destination folder for .conllu files (default: 'data').
  --split N              Optional: Split each XML into chunks of N sentences (e.g. 1000).
  --max_files M          Optional: Safety limit for maximum number of split chunks per XML.
  --archive TAR_NAME     Optional: Package generated .conllu files into a .tar.gz archive.
```

### Examples

#### 1. Convert a single XML file to `data/`:
```bash
python extract.py xml/da_000010.xml --output_dir data
```
*(Produces `data/da_000010.conllu`)*

#### 2. Batch-convert an entire folder of XML files:
```bash
python extract.py xml/*.xml --output_dir data
```

#### 3. Sub-chunk a massive XML into smaller partitions (e.g., 2,000 sentences per chunk):
```bash
python extract.py xml/large_corpus.xml --output_dir data --split 2000
```
*(Produces `data/large_corpus_0001.conllu`, `data/large_corpus_0002.conllu`, etc.)*

#### 4. Convert and create a compressed `.tar.gz` archive for deployment:
```bash
python extract.py xml/*.xml --output_dir data --archive corpus_data.tar.gz
```

---

## 🗂 Organizing Loose Files (`organize_data.py`)

If you have loose `.conllu` chunks stored directly inside the `data/` directory (e.g. `svt-2022_0001.conllu`, `svt-2022_0002.conllu`), you can use `organize_data.py` to automatically group them into clean subfolders.

### Features
- **Auto Prefix Detection:** Identifies corpus prefixes (e.g. `svt-2022_0001.conllu` $\to$ `data/svt-2022/`).
- **Dry-Run Simulation:** Test and preview proposed file reorganizations without modifying disk state.
- **Copy or Move:** Move files by default or copy them with `--copy`.

### Usage & Examples

#### 1. Preview planned reorganization (Safe Dry-Run):
```bash
python organize_data.py --dry-run
```

#### 2. Organize all loose files in `data/`:
```bash
python organize_data.py
```

#### 3. Organize with verbose file-by-file output:
```bash
python organize_data.py -v
```

---

## 💻 Running Locally

### Streamlit Web Application

To launch the web interface:

```bash
# Ensure OPAM environment is loaded in current shell
eval $(opam env)

# Activate virtual environment
source .venv/bin/activate

# Launch Streamlit
streamlit run app.py
```

The app will start at `http://localhost:8501`.

---

### Command-Line Interface (CLI)

Use `search_cli.py` to query your corpora directly from the terminal or in shell scripts.

#### Basic search on all data:
```bash
python search_cli.py --all
```

#### Search with a custom query pattern:
```bash
python search_cli.py --all -q 'pattern { V [xpos="VB"]; O [xpos="NN"]; V -[OO]-> O; }'
```

#### Search a single specific chunk:
```bash
python search_cli.py -f data/svt-2022_0001.conllu -q 'pattern { V [xpos="VB"]; S [xpos="NN"]; V -[SS]-> S; }'
```

#### Output formats:
- **Summary Table (`--format summary`):**
  ```bash
  python search_cli.py -n 10 --format summary
  ```
- **Machine-readable JSON (`--format json`):**
  ```bash
  python search_cli.py -n 5 --format json -o results.json
  ```
- **Count only (fast frequency scan):**
  ```bash
  python search_cli.py --all --count-only
  ```

---

### Running Tests

Run the test suite to verify corpus discovery, single-file search, iterative querying, and whole-dataset queries:

```bash
python -m unittest test_engine.py
```

---

## 🐧 Linux Server Deployment Guide

This section covers setting up a production-ready deployment on a Linux server (Ubuntu/Debian) running behind an **Nginx** reverse proxy managed by **systemd** with **HTTPS/TLS**.

```
                   Internet (HTTPS:443 / HTTP:80)
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │    Nginx Web Server   │
                     │ (SSL + WebSocket Proxy│
                     └───────────┬───────────┘
                                 │ Reverse Proxy to localhost:8501
                                 ▼
                     ┌───────────────────────┐
                     │   systemd service     │
                     │ (grew-frontend.service│
                     │  streamlit run app.py │
                     └───────────┬───────────┘
                                 │
                     ┌───────────▼───────────┐
                     │     grewpy_backend    │
                     │   (OPAM 5.2.1 switch) │
                     └───────────────────────┘
```

---

### Step 1: Dedicated System User & Directory

Create a dedicated non-privileged user `grew` to run the service:

```bash
sudo useradd -m -s /bin/bash grew
sudo usermod -aG sudo grew   # Optional: if initial setup rights needed
sudo su - grew
```

Clone the repository to `/opt/grew_frontend` or the user's home directory `/home/grew/grew_frontend`:

```bash
git clone <repository_url> /home/grew/grew_frontend
cd /home/grew/grew_frontend
```

---

### Step 2: Server-side OPAM & Grew Setup

As the `grew` user:

```bash
# Initialize OPAM for grew user
opam init --bare -a -y
opam switch create 5.2.1
eval $(opam env)

# Add Grew remote and install backend
opam remote add grew "https://opam.grew.fr"
opam update
opam install -y grewpy_backend "conll<1.20"

# Verify binary path
which grewpy_backend
# Should output: /home/grew/.opam/5.2.1/bin/grewpy_backend (or ~/.opam/default/bin/...)
```

---

### Step 3: Application & Python Setup

As the `grew` user:

```bash
cd /home/grew/grew_frontend

# Setup Python Virtual Environment
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Populate corpus data
mkdir -p data
# Copy your .conllu files into data/
```

Test that the application can start:
```bash
eval $(opam env)
python -c "import grewpy; print('OK')"
```

Exit back to your `sudo` administrative user:
```bash
exit
```

---

### Step 4: Systemd Service Configuration

Create a systemd unit file at `/etc/systemd/system/grew-frontend.service`:

```bash
sudo nano /etc/systemd/system/grew-frontend.service
```

Paste the following configuration:

```ini
[Unit]
Description=Grew Dependency Corpus Search Engine (Streamlit)
After=network.target

[Service]
Type=simple
User=grew
Group=grew
WorkingDirectory=/home/grew/grew_frontend
Environment="PATH=/home/grew/.opam/5.2.1/bin:/home/grew/.opam/default/bin:/home/grew/grew_frontend/.venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"
Environment="STREAMLIT_SERVER_HEADLESS=true"
Environment="STREAMLIT_SERVER_ENABLE_CORS=false"
Environment="STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false"
Environment="STREAMLIT_BROWSER_GATHER_USAGE_STATS=false"
ExecStart=/home/grew/grew_frontend/.venv/bin/streamlit run app.py --server.port 8501 --server.address 127.0.0.1
Restart=on-failure
RestartSec=5s

# Security hardening
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable grew-frontend
sudo systemctl start grew-frontend
sudo systemctl status grew-frontend
```

---

### Step 5: Nginx Reverse Proxy with WebSockets

Streamlit requires WebSocket support (`_stcore/stream`). 

Install Nginx:
```bash
sudo apt install -y nginx
```

Create `/etc/nginx/sites-available/grew-frontend`:

```nginx
server {
    listen 80;
    server_name grew.example.com; # Replace with your domain or server IP

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;

        # WebSocket support (Crucial for Streamlit)
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Standard proxy headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts for long queries
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }
}
```

Enable the configuration and reload Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/grew-frontend /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

### Step 6: SSL / HTTPS Configuration (Let's Encrypt)

Install Certbot for automated TLS certificates:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d grew.example.com
```

Certbot will automatically update the Nginx configuration to enforce HTTPS and set up automatic certificate renewals.

---

### Step 7: Service Management & Maintenance

- **View Live Application Logs:**
  ```bash
  sudo journalctl -u grew-frontend -f
  ```
- **Restart the Application:**
  ```bash
  sudo systemctl restart grew-frontend
  ```
- **Update Corpus Data on the Server:**
  Simply add or update `.conllu` files in `/home/grew/grew_frontend/data/`. Refreshing the browser will automatically discover the updated files.

---

## 📖 User Guide & Examples

### Streamlit Web Interface

1. **Select Subcorpus Folder & Scope in the Sidebar:**
   - **📂 Subcorpus Folder / Group:** Filter by specific corpus directory under `data/` (e.g. `svt-2022`, `news`, `historical`) or select `🌐 All Subcorpora Folders`.
   - **🌐 All Subcorpora (In Selected Scope):** Executes the query across all files in the scope as one cohesive corpus.
   - **🔄 Iterate Subcorpora (Per-Chunk Breakdown):** Iterates chunk by chunk through the selected folder, recording match counts, frequencies per 1,000 sentences, and distribution charts.
   - **🎯 Single Subcorpus Chunk:** Focus on an individual `.conllu` file for fast micro-analysis.
   - **📑 Custom Subset / Range:** Select the first $N$ chunks or pick specific chunks manually from the selected folder.
2. **Choose or Enter a Grew Query:**
   - Select a pre-built template from the dropdown (Swedish Talbanken/MAMBA or Universal Dependencies).
   - Or write a custom GRS pattern directly in the query editor.
3. **Run Search:**
   - Click **🚀 Run Search**.
   - Monitor the live progress bar and status message.
4. **Inspect Results:**
   - View top summary KPI metrics (Total Matches, Sentences Scanned, Frequency).
   - In Iterative mode, switch between the **📋 Table View** and **📊 Chart View** to analyze frequencies across chunks.
   - Expand individual matches in the **🔎 Match Inspector** to read sentence texts, matched node lemmas, POS tags, and morphological features.
   - Click **📥 Download Results** for JSON or CSV exports.

---

### CLI Tool (`search_cli.py`)

#### Basic Usage & Options

```text
usage: search_cli.py [-h] [-q QUERY] [-f FILE] [-d DATA_DIR] [-s SUBFOLDER]
                     [-n CHUNKS_LIMIT] [--all] [--count-only] [-m MAX_MATCHES]
                     [--format {text,json,summary}] [-o OUTPUT]

Options:
  -q, --query TEXT         Grew pattern query.
  -f, --file PATH          Path to a single .conllu file.
  -d, --data-dir DIR       Directory containing .conllu files (default: 'data').
  -s, --subfolder FOLDER   Filter search to a specific subfolder/group in data directory.
  -n, --chunks-limit N     Limit number of subcorpus chunks.
  --all                    Search across all subcorpora.
  --count-only             Output match counts only without building full trees.
  -m, --max-matches N      Maximum sample matches to display (default: 20).
  --format FORMAT          Output format: text, json, summary.
  -o, --output FILE        Save full result payload to a JSON file.
```

#### Examples

1. **Get an instant distribution summary across the first 20 chunks:**
   ```bash
   python search_cli.py -n 20 --format summary
   ```

2. **Run a passive verb query across the entire dataset and export to JSON:**
   ```bash
   python search_cli.py --all \
     -q 'pattern { V [xpos="VB", Voice="Pass"]; }' \
     --format json \
     -o passive_verbs.json
   ```

---

### Grew Query Syntax & Templates

Grew uses graph pattern matching syntax enclosed in `pattern { ... }` blocks, with optional negative constraints in `without { ... }` blocks.

#### 1. Swedish Dependency Treebank (MAMBA / Talbanken / SVT Tagset)

- **Subject–Verb (`V -[SS]-> S`):**
  ```grew
  pattern {
    V [xpos="VB"];
    S [xpos="NN"|"PN"];
    V -[SS]-> S;
  }
  ```

- **Direct Object (`V -[OO]-> O`):**
  ```grew
  pattern {
    V [xpos="VB"];
    O [xpos="NN"];
    V -[OO]-> O;
  }
  ```

- **Inverted Word Order (Verb precedes Subject):**
  ```grew
  pattern {
    V [xpos="VB"];
    S [xpos="NN"|"PN"];
    V -[SS]-> S;
    V < S;
  }
  ```

- **Negative Constraint (Verb with Subject but NO Object):**
  ```grew
  pattern {
    V [xpos="VB"];
    V -[SS]-> S;
  }
  without {
    V -[OO]-> O;
  }
  ```

- **Passive Verb with Agent Prepositional Phrase:**
  ```grew
  pattern {
    V [xpos="VB", Voice="Pass"];
    P [xpos="PP"];
    V -> P;
  }
  ```

---

#### 2. Universal Dependencies (UD Standard Tagset)

- **Nominal Subject (`nsubj`):**
  ```grew
  pattern {
    V [upos=VERB];
    N [upos=NOUN|PRON];
    V -[nsubj]-> N;
  }
  ```

- **Direct Object (`obj`):**
  ```grew
  pattern {
    V [upos=VERB];
    N [upos=NOUN|PRON];
    V -[obj]-> N;
  }
  ```

- **Adjectival Modifier (`amod`):**
  ```grew
  pattern {
    N [upos=NOUN];
    A [upos=ADJ];
    N -[amod]-> A;
  }
  ```

- **Lemma Constraint:**
  ```grew
  pattern {
    V [lemma="ha"|"vara", upos=VERB];
  }
  ```

---

## 📁 Project Structure

```text
grew_frontend/
├── app.py              # Streamlit Web Application (UI, visualization, exports)
├── engine.py           # Core search engine & memory-safe iteration logic
├── search_cli.py       # Standalone Command-Line Interface (CLI)
├── extract.py          # XML to CoNLL-U streaming converter & extraction tool
├── organize_data.py    # Auto-organizer for loose corpus files into subfolders
├── test_engine.py      # Automated unit and integration test suite
├── requirements.txt    # Python package dependencies
├── README.md           # Technical documentation and deployment guide
├── xml/                # Raw source XML corpora directory
└── data/               # CoNLL-U (.conllu) corpus treebank directory (git-ignored)
```

---

## ❓ Troubleshooting & FAQ

### 1. `FileNotFoundError: [Errno 2] No such file or directory: 'grewpy_backend'`
- **Cause:** The OCaml executable `grewpy_backend` is not found in the system's `PATH`.
- **Solution:** 
  1. Make sure `grewpy_backend` was installed via OPAM (`opam install grewpy_backend "conll<1.20"`).
  2. Run `eval $(opam env)` before starting Python.
  3. In systemd, ensure `Environment="PATH=/home/grew/.opam/.../bin:..."` is properly set in the service file.

---

### 2. OPAM compilation error: `Error: Unbound value String.drop_first` in `conll`
- **Cause:** `conll.1.20.0` uses an OCaml 5.5+ standard library function that does not exist in OCaml 5.2/5.3/5.4.
- **Solution:** Install with a constrained version of `conll`:
  ```bash
  opam install grewpy_backend "conll<1.20"
  ```

---

### 3. Streamlit shows "Please wait..." or WebSocket disconnected on the Linux server
- **Cause:** Nginx is not passing WebSocket upgrade headers to Streamlit.
- **Solution:** Ensure the following directives are present in your Nginx `location /` block:
  ```nginx
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";
  proxy_http_version 1.1;
  ```

---

### 4. Can I organize treebank files into subdirectories under `data/`?
- **Yes.** `discover_corpus_files()` uses recursive globbing (`data/**/*.conllu`), so you can categorize corpora by genre, year, language, or partition.

---

## 📄 License

This project is licensed under the MIT License. Grew and grewpy are developed and maintained by [CDHU](https://www.uu.se/en/centre/digital-humanities-and-social-sciences/about-us).
