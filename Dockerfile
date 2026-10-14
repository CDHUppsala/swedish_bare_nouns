# ==============================================================================
# Multi-stage Dockerfile for Grew Dependency Corpus Search Engine
# Stage 1: Build the native OCaml grewpy_backend binary via OPAM
# Stage 2: Minimal Python runtime with Streamlit UI and mounted corpus data
# ==============================================================================

# Stage 1: Build OCaml backend
FROM ocaml/opam:debian-12-ocaml-5.2 AS ocaml-builder

# Add Grew OPAM remote repository and install grewpy_backend
RUN opam remote add grew "https://opam.grew.fr" && \
    opam update && \
    opam install -y --cli=2.1 grewpy_backend "conll<1.20"

# Stage 2: Final Python application image
FROM python:3.12-slim-bookworm

# Set container environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    PATH="/usr/local/bin:$PATH"

# Install runtime system dependencies (libgmp required by OCaml binary, curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgmp10 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy compiled grewpy_backend binary from builder stage
COPY --from=ocaml-builder /home/opam/.opam/5.2/bin/grewpy_backend /usr/local/bin/grewpy_backend

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure data directory placeholder exists (overlaid by host volume mount)
RUN mkdir -p /app/data

# Expose Streamlit default port
EXPOSE 8501

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Launch the Streamlit application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
