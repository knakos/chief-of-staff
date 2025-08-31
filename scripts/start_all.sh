#!/usr/bin/env bash
cd "$(dirname "$0")/../backend"; if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi
uvicorn app:app --host 127.0.0.1 --port 8787 --reload
