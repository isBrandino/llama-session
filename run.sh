#!/bin/bash
alias llama="$PWD/run.sh"
files/.venv/bin/python -m ensurepip --upgrade || files/.venv/bin/python -m pip install --upgrade pip setuptools wheel
$PWD/files/edit.sh
$PWD/files/edit.sh ollama
$PWD/files/edit.sh uuid
$PWD/files/edit.sh ./llama.py