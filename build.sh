#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

# seed admin account on first deploy
python seed_admin.py
