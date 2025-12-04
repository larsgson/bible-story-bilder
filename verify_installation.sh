#!/bin/bash

echo "======================================================================"
echo "Bible Content Organizer - Installation Verification"
echo "======================================================================"
echo ""

# Check Python
echo "1. Checking Python..."
if command -v python3 &> /dev/null; then
    echo "   ✓ Python 3 found: $(python3 --version)"
else
    echo "   ✗ Python 3 not found"
    exit 1
fi

# Check dependencies
echo ""
echo "2. Checking dependencies..."
python3 -c "import requests" 2>/dev/null && echo "   ✓ requests installed" || echo "   ✗ requests not installed"
python3 -c "import dotenv" 2>/dev/null && echo "   ✓ python-dotenv installed" || echo "   ✗ python-dotenv not installed"

# Check directories
echo ""
echo "3. Checking directory structure..."
[ -d "api-cache" ] && echo "   ✓ api-cache/ found" || echo "   ✗ api-cache/ missing"
[ -d "sorted" ] && echo "   ✓ sorted/ found" || echo "   ℹ sorted/ not yet generated (run: python3 sort_cache_data.py)"
[ -d "previous-version" ] && echo "   ✓ previous-version/ found" || echo "   ✗ previous-version/ missing"

# Check scripts
echo ""
echo "4. Checking scripts..."
[ -f "sort_cache_data.py" ] && echo "   ✓ sort_cache_data.py found" || echo "   ✗ sort_cache_data.py missing"
[ -f "download_language_content.py" ] && echo "   ✓ download_language_content.py found" || echo "   ✗ download_language_content.py missing"

# Check API key
echo ""
echo "5. Checking API configuration..."
if [ -f ".env" ]; then
    if grep -q "BIBLE_API_KEY=" .env; then
        echo "   ✓ .env file found with BIBLE_API_KEY"
    else
        echo "   ⚠ .env file found but BIBLE_API_KEY not set"
    fi
else
    echo "   ℹ .env file not found (needed for downloads)"
fi

# Check documentation
echo ""
echo "6. Checking documentation..."
[ -f "README.md" ] && echo "   ✓ README.md found" || echo "   ✗ README.md missing"
[ -f "QUICKSTART.md" ] && echo "   ✓ QUICKSTART.md found" || echo "   ✗ QUICKSTART.md missing"

echo ""
echo "======================================================================"
echo "Verification Complete"
echo "======================================================================"
echo ""
echo "Next steps:"
echo "  1. If sorted/ not found: run 'python3 sort_cache_data.py'"
echo "  2. If .env missing: create with 'echo BIBLE_API_KEY=your_key > .env'"
echo "  3. Then download content: 'python3 download_language_content.py eng --books MAT:1'"
echo ""
