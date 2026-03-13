#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

# Make start script executable
chmod +x start.sh
