#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Void Compass // Linux x86-64 testing build"
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 is not installed in this Linux environment." >&2
    exit 1
fi

needs_packages=0
if ! python3 -c 'import tkinter' >/dev/null 2>&1; then
    needs_packages=1
fi

probe_dir="$(mktemp -d)"
if ! python3 -m venv "$probe_dir/venv" >/dev/null 2>&1; then
    needs_packages=1
fi
rm -rf "$probe_dir"

if (( needs_packages )); then
    if ! command -v apt-get >/dev/null 2>&1; then
        echo "Install Python Tk and venv with your distribution's package manager, then rerun this script." >&2
        exit 1
    fi
    if (( EUID == 0 )); then
        sudo_cmd=()
    elif command -v sudo >/dev/null 2>&1; then
        sudo_cmd=(sudo)
    else
        echo "Installing Python Tk and venv requires root access or sudo." >&2
        exit 1
    fi
    echo "Installing the missing Ubuntu/Debian build prerequisites..."
    "${sudo_cmd[@]}" apt-get update
    "${sudo_cmd[@]}" apt-get install --yes python3-tk python3-venv
fi

python3 -m venv .venv-linux
source .venv-linux/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python build.py

echo
echo "Linux build complete."
echo "Executable: dist/VoidCompass"
echo "Release:    release/VoidCompass-v*-Linux-x64.tar.gz"
echo "Checksum:   release/VoidCompass-v*-Linux-x64.tar.gz.sha256"
echo "Test dist/VoidCompass on Linux before publishing the testing release."
