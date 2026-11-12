#!/usr/bin/env bash
set -Eeuo pipefail

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

printf "${BLUE}==>${NC} Installing MimicType in an isolated virtual environment (PEP 668 compliant)...\n"

# 1. Check Python
if ! command -v python3 >/dev/null 2>&1; then
    printf "${RED}Error:${NC} python3 is not installed. Please install Python 3.10+.\n" >&2
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
printf "${BLUE}==>${NC} Detected Python %s\n" "$PYTHON_VERSION"

# 2. Create virtual environment (.venv)
VENV_DIR="$SCRIPT_DIR/.venv"
if [[ ! -d "$VENV_DIR" ]]; then
    printf "${BLUE}==>${NC} Creating virtual environment in %s...\n" "$VENV_DIR"
    python3 -m venv "$VENV_DIR"
else
    printf "${BLUE}==>${NC} Using existing virtual environment in %s\n" "$VENV_DIR"
fi

# 3. Upgrade pip and install package in editable mode
printf "${BLUE}==>${NC} Installing dependencies (evdev, pyyaml) into .venv...\n"
"$VENV_DIR/bin/pip" install --upgrade pip setuptools >/dev/null 2>&1 || true
"$VENV_DIR/bin/pip" install -e "$SCRIPT_DIR"

# 4. Link binary to ~/.local/bin
BIN_DIR="${HOME}/.local/bin"
mkdir -p "$BIN_DIR"
TARGET_LINK="$BIN_DIR/mimictype"

printf "${BLUE}==>${NC} Creating launcher symlink: %s -> %s/bin/mimictype\n" "$TARGET_LINK" "$VENV_DIR"
ln -sf "$VENV_DIR/bin/mimictype" "$TARGET_LINK"

# 5. Check PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    printf "${YELLOW}Warning:${NC} %s is not in your PATH.\n" "$BIN_DIR"
    printf "Add it to your shell config (~/.bashrc, ~/.zshrc, or ~/.config/fish/config.fish):\n"
    printf "    export PATH=\"\$HOME/.local/bin:\$PATH\"\n"
fi

# 6. Check /dev/uinput permissions
printf "${BLUE}==>${NC} Checking /dev/uinput permissions...\n"
if [[ -w /dev/uinput ]]; then
    printf "${GREEN}✓ /dev/uinput is writable by current user (%s).${NC}\n" "$USER"
else
    printf "${YELLOW}Notice:${NC} Current user does not have write access to /dev/uinput.\n"
    printf "To use MimicType without sudo, add yourself to the 'input' group:\n"
    printf "    sudo usermod -aG input \$USER\n"
    printf "Then log out and log back in (or run 'newgrp input').\n"
fi

printf "\n${GREEN}✓ MimicType installed successfully!${NC}\n"
printf "Usage:\n"
printf "    mimictype                 # Types clipboard content after 3s countdown\n"
printf "    mimictype \"Hello world\"   # Types custom string\n"
printf "    mimictype daemon          # Runs background daemon with global hotkey (Ctrl+Alt+V)\n"
printf "    mimictype --help          # Shows all options\n"
