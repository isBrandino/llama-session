#!/bin/bash
alias llama="$(pwd)/run.sh"
files/.venv/bin/python -m ensurepip --upgrade || files/.venv/bin/python -m pip install --upgrade pip setuptools wheel
$(pwd)/files/edit.sh
$(pwd)/files/edit.sh ollama
$(pwd)/files/edit.sh uuid
$(pwd)/files/edit.sh ./llama.py