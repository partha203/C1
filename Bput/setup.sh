#!/usr/bin/env bash
set -e
echo "============================================"
echo "  CampusOne Setup"
echo "  Campus Life, Debugged."
echo "============================================"
echo

# ---- 1. Check Python ----
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 was not found on your system."
    echo "Install it from https://www.python.org/downloads/ (or via your OS package manager)"
    exit 1
fi
echo "[OK] Python found:"
python3 --version
echo

# ---- 2. Create virtual environment ----
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists, skipping creation."
fi
echo

# ---- 3. Install requirements ----
echo "Installing dependencies..."
./venv/bin/pip install --quiet --upgrade pip
./venv/bin/pip install --quiet -r requirements.txt
echo "[OK] Dependencies installed."
echo

# ---- 4. Set up .env if missing ----
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "[OK] Created .env from template. Edit it later if you want email/AI features."
fi
echo

# ---- 5. Initialize + seed database ----
echo "Initializing database with demo data..."
./venv/bin/python init_db.py
echo
echo "============================================"
echo "  Setup complete!"
echo "  Run ./run.sh to start CampusOne."
echo "============================================"
