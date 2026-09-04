# Calibrated triage agent -- reproducible image for the demo and the eval.
#
# Two things drive every decision in this file:
#
# 1. THE CPU TORCH BUILD IS NOT OPTIONAL. `pip install torch` resolves to CUDA
#    wheels and pulls ~2GB of NVIDIA runtime that this image can never use -- the
#    classifier is a 22M-parameter encoder that runs on CPU in well under a second.
#    Installing torch first, from the CPU index, keeps the image at roughly a
#    quarter of the size and makes the build work on a machine with no GPU.
#
# 2. THE WEIGHTS SHIP IN THE IMAGE. `models/` carries the fine-tuned classifier and
#    its base encoder (~88MB each). They are copied in rather than downloaded at
#    build time, so the image builds and runs with NO network access and a grader
#    gets the exact weights every reported number came from.
#
# The pipeline runs end to end with no API key: classification, calibration,
# retrieval and routing are entirely local. A missing GEMINI_API_KEY means every
# auto-reply records a drafting failure and escalates carrying its SOP, which is the
# designed path rather than a crash.

FROM python:3.11-slim

# Fail fast and keep logs unbuffered so `docker logs` shows progress live rather
# than at exit; no .pyc in a layer that is never reused.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Torch first, from the CPU index, in its own layer. Separated from the rest so a
# change to requirements.txt does not re-download 200MB of torch, and so the CPU
# index applies to torch alone rather than to every package.
RUN pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        "torch>=2.2"

# Dependencies before source: this layer is cached across every code change.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Source, config, corpus, weights. `.dockerignore` keeps out .venv, .scratch,
# caches, and the .env file -- secrets are passed at run time, never baked in.
COPY src/ ./src/
COPY app/ ./app/
COPY .streamlit/ ./.streamlit/
COPY eval/ ./eval/
COPY scripts/ ./scripts/
COPY config/ ./config/
COPY data/ ./data/
COPY models/ ./models/
COPY tests/ ./tests/
COPY pyproject.toml README.md ./

# `src` on the path so `import triage` works without an editable install, and the
# repo root so `import eval` resolves for the evaluation entrypoints.
ENV PYTHONPATH=/app/src:/app

# Fail the build if the artefacts and the config disagree -- a stale labels.json
# against a reshaped taxonomy is silent at runtime (every email in the missing
# class escalates as unanswerable) and is exactly the drift worth catching here.
RUN python -m pytest tests/ -q

EXPOSE 8501

# Streamlit needs to bind 0.0.0.0 to be reachable from outside the container;
# headless suppresses the browser-open attempt and the email prompt on first run.
CMD ["streamlit", "run", "app/streamlit_app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
