#!/bin/bash
# GitHub Sync Script for planfile
# Uses the correct virtual environment with PyGithub installed

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLANFILE_VENV="/home/tom/github/semcod/planfile/venv"

# Use the virtual environment's Python to run planfile
"$PLANFILE_VENV/bin/python" -m planfile.cli.commands "$@"
