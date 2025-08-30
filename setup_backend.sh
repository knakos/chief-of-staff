#!/bin/bash
# Backend setup script for Chief of Staff

echo "🚀 Setting up Chief of Staff Backend..."

cd backend

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Create .env file from example if it doesn't exist
if [ ! -f ".env" ]; then
    echo "⚙️ Creating .env file..."
    cp .env.example .env
    echo "❗ Please edit .env file and add your ANTHROPIC_API_KEY"
fi

# Initialize database and run tests
echo "🗄️ Testing backend setup..."
python test_setup.py

echo ""
echo "✅ Backend setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit backend/.env and add your ANTHROPIC_API_KEY"
echo "2. Run: ./scripts/start_all.sh to start the backend"
echo "3. Run: ./scripts/start-electron.ps1 to start the frontend"