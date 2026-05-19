#!/bin/bash

# --- Configuration ---
PROJECT_ROOT="/opt/trading-journal"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
BACKEND_DIR="$PROJECT_ROOT/backend"
PM2_CONFIG="$PROJECT_ROOT/ecosystem.config.js"

echo "🚀 Starting Deployment..."

# 1. Pull latest changes
echo "📥 Pulling latest code from git..."
cd $PROJECT_ROOT
git pull

# 2. Update Backend (if dependencies changed)
echo "🐍 Updating backend dependencies..."
source $BACKEND_DIR/venv/bin/activate
pip install -r $BACKEND_DIR/requirements.txt
deactivate

# 3. Build Frontend
echo "🏗️  Building frontend..."
cd $FRONTEND_DIR
npm install  # Ensures new packages are installed
npm run build

# 4. Restart Services
echo "🔄 Restarting services with PM2..."
cd $PROJECT_ROOT
pm2 restart $PM2_CONFIG

echo "✅ Deployment Complete!"
