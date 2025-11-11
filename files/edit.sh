#!/bin/bash
# llama.sh – auto-create .venv and run .py files or install any pip package

set -euo pipefail

VENV_DIR=".venv"
PYTHON_CMD="${PYTHON_CMD:-python3}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$SCRIPT_DIR/$VENV_DIR"
VENV_PYTHON="$VENV_PATH/bin/python"

if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || "$OSTYPE" == "cygwin" ]]; then
    VENV_PYTHON="$VENV_PATH/Scripts/python.exe"
fi

ensure_venv() {
    if [ ! -d "$VENV_PATH" ]; then
        echo "Creating virtual environment at: $VENV_PATH"
        "$PYTHON_CMD" -m venv "$VENV_PATH"
        echo ".venv created."
    else
        echo "Using existing .venv: $VENV_PATH"
    fi
}

run_in_venv() {
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || "$OSTYPE" == "cygwin" ]]; then
        if command -v powershell >/dev/null 2>&1; then
            powershell -Command "& { . \"$VENV_PATH/Scripts/Activate.ps1\"; python \"$@\"; deactivate }" 2>/dev/null || true
        else
            cmd.exe /c "\"$VENV_PATH/Scripts/activate.bat\" && \"$VENV_PYTHON\" \"$@\" && deactivate" 2>/dev/null || true
        fi
    else
        local activate_script="$VENV_PATH/bin/activate"
        if [ -f "$activate_script" ]; then
            source "$activate_script"
            "$@"
            deactivate
        else
            echo "Error: activate script not found: $activate_script" >&2
            exit 1
        fi
    fi
}

main() {
    ensure_venv

    if [ $# -eq 0 ]; then
        echo "Virtual environment is ready: $VENV_PATH"
        return 0
    fi

    local first_arg="$1"
    shift

    if [[ "$first_arg" == *.py ]]; then
        local script_path
        if [[ "$first_arg" = /* ]]; then
            script_path="$first_arg"
        else
            script_path="$SCRIPT_DIR/$first_arg"
        fi

        if [ ! -f "$script_path" ]; then
            echo "Error: File not found: $script_path" >&2
            exit 1
        fi

        echo "Running: $script_path"
        run_in_venv "$VENV_PYTHON" "$script_path" "$@"
        echo "Script finished. venv deactivated."
        return 0
    fi

    if [[ "$first_arg" == "-m" ]]; then
        echo "Running: python -m $*"
        run_in_venv "$VENV_PYTHON" "-m" "$@"
        echo "Command finished. venv deactivated."
        return 0
    fi

    local packages=("$first_arg" "$@")
    echo "Installing packages: ${packages[*]}"
    run_in_venv "$VENV_PYTHON" -m pip install --upgrade "${packages[@]}"
    echo "Packages installed. venv deactivated."
}

[[ ! -x "$0" ]] && chmod +x "$0" 2>/dev/null || true

main "$@"
