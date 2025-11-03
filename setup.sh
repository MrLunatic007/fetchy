#!/bin/bash
# Fetchy Download Manager Installation Script

set -e

echo "🚀 Installing Fetchy Download Manager..."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
if ! command -v python3 &>/dev/null; then
  echo -e "${RED}Error: Python 3 is required${NC}"
  exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"

# Create virtual environment
echo -e "${YELLOW}Creating virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip install --upgrade pip
pip install requests PyQt6 rich

echo -e "${GREEN}✓ Python dependencies installed${NC}"

# Install CLI tool
echo -e "${YELLOW}Installing CLI tool...${NC}"
sudo ln -sf "$(pwd)/cli.py" /usr/local/bin/fetchy
sudo chmod +x /usr/local/bin/fetchy
echo -e "${GREEN}✓ CLI tool installed${NC}"

# Install GUI launcher
echo -e "${YELLOW}Installing GUI launcher...${NC}"
sudo ln -sf "$(pwd)/gui.py" /usr/local/bin/fetchy-gui
sudo chmod +x /usr/local/bin/fetchy-gui
echo -e "${GREEN}✓ GUI launcher installed${NC}"

# Create desktop entry
echo -e "${YELLOW}Creating desktop entry...${NC}"
DESKTOP_FILE="/usr/share/applications/fetchy.desktop"
sudo tee $DESKTOP_FILE >/dev/null <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Fetchy Download Manager
Comment=Advanced download manager with parallel downloading
Exec=$(pwd)/venv/bin/python $(pwd)/gui.py
Icon=$(pwd)/extension/icons/icon-96.png
Terminal=false
Categories=Network;FileTransfer;
EOF

echo -e "${GREEN}✓ Desktop entry created${NC}"

# Setup Firefox extension
echo -e "${YELLOW}Setting up Firefox extension...${NC}"

# Create native messaging manifest
NATIVE_HOST_DIR="$HOME/.mozilla/native-messaging-hosts"
mkdir -p "$NATIVE_HOST_DIR"

MANIFEST_FILE="$NATIVE_HOST_DIR/com.fetchy.downloader.json"
cat >"$MANIFEST_FILE" <<EOF
{
  "name": "com.fetchy.downloader",
  "description": "Fetchy Download Manager",
  "path": "$(pwd)/native_host.py",
  "type": "stdio",
  "allowed_extensions": [
    "{YOUR_EXTENSION_ID}@fetchy.com"
  ]
}
EOF

chmod +x native_host.py

echo -e "${GREEN}✓ Native messaging host configured${NC}"

# Instructions for Firefox extension
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Installation complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}Usage:${NC}"
echo ""
echo "  • CLI Tool:"
echo "    $ fetchy download https://example.com/file.zip"
echo "    $ fetchy add https://example.com/file.zip"
echo "    $ fetchy queue"
echo "    $ fetchy process"
echo ""
echo "  • GUI Tool:"
echo "    $ fetchy-gui"
echo "    (Or launch from application menu)"
echo ""
echo -e "${YELLOW}Firefox Extension Setup:${NC}"
echo "  1. Open Firefox and navigate to: about:debugging#/runtime/this-firefox"
echo "  2. Click 'Load Temporary Add-on'"
echo "  3. Select the manifest.json file from: $(pwd)/extension/"
echo "  4. Copy the extension ID and update it in:"
echo "     $MANIFEST_FILE"
echo ""
echo -e "${YELLOW}For Firefox-based browsers (Librewolf, Waterfox, etc.):${NC}"
echo "  Follow the same steps as Firefox above."
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
