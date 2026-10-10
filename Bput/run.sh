#!/usr/bin/env bash
echo "============================================"
echo "  Starting CampusOne..."
echo "============================================"

if [ ! -d "venv" ]; then
    echo "[ERROR] Virtual environment not found."
    echo "Please run ./setup.sh first."
    exit 1
fi

if [ ! -f "database/campusone.db" ]; then
    echo "[WARNING] Database not found. Running initial setup..."
    ./venv/bin/python init_db.py
fi

echo
echo "CampusOne will be available at:"
echo "  http://127.0.0.1:5000"
echo
echo "Press CTRL+C to stop the server."
echo "============================================"
echo

./venv/bin/python app.py
