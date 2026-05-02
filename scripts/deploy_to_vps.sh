#!/bin/bash

# Configuration
VPS_USER="root" # Update if different
VPS_IP="72.61.231.160" # Your Hostinger VPS IP
REMOTE_DIR="/root/yfinance-api"

echo "🚀 Preparing deployment to Hostinger VPS..."

# Create remote directory
ssh $VPS_USER@$VPS_IP "mkdir -p $REMOTE_DIR"

# Copy files
echo "📦 Copying files..."
scp yfinance_server.py Dockerfile docker-compose.yml $VPS_USER@$VPS_IP:$REMOTE_DIR/

# Build and Start
echo "🏗️ Building and starting container..."
ssh $VPS_USER@$VPS_IP "cd $REMOTE_DIR && docker compose up -d --build"

echo "✅ Deployment complete! API available at http://$VPS_IP:8001/research?ticker=AAPL"
