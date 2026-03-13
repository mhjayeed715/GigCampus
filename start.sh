#!/usr/bin/env bash
set -o errexit

# If running on Render with a disk mounted at /var/data
if [ -d "/var/data" ]; then
    echo "Detected persistent disk at /var/data"
    
    # Ensure uploads directory exists on persistent disk
    mkdir -p /var/data/uploads
    
    # Remove the ephemeral static/uploads directory from the container image
    rm -rf static/uploads
    
    # Create a symlink from static/uploads to /var/data/uploads
    # This allows Flask to serve files from /static/uploads while storing them on the disk
    ln -s /var/data/uploads static/uploads
    
    echo "Symlinked static/uploads -> /var/data/uploads"
fi

# Run the seeding script (it should be idempotent)
python seed_admin.py

# Start Gunicorn
exec gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 --bind 0.0.0.0:$PORT run:app