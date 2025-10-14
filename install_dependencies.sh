#!/bin/bash
# Install system dependencies for native TTS/STT compilation
# Required for RTX 50 series setup

set -e

echo "=========================================="
echo "Installing Dependencies for Native Build"
echo "=========================================="
echo ""
echo "This will install system packages needed to compile"
echo "the TTS and STT services natively on your system."
echo ""
echo "Packages to install:"
echo "  - cmake (build system)"
echo "  - libopus-dev (audio codec library)"
echo "  - libssl-dev (already in Dockerfile, good to have)"
echo ""

# Check if running with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "This script needs sudo to install packages."
    echo "You may be prompted for your password."
    echo ""
    SUDO="sudo"
else
    SUDO=""
fi

echo "Updating package list..."
$SUDO apt-get update

echo ""
echo "Installing packages..."
$SUDO apt-get install -y \
    cmake \
    libopus-dev \
    libssl-dev \
    pkg-config

echo ""
echo "=========================================="
echo "✅ All dependencies installed!"
echo "=========================================="
echo ""
echo "You can now run:"
echo "  ./start_rtx50_services.sh"
echo ""

