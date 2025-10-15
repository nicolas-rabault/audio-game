#!/bin/bash
# RTX 50 Series Startup Script
# This script starts the TTS and STT services natively to work around
# Docker CUDA compatibility issues with RTX 50 series GPUs

set -e

echo "=========================================="
echo "RTX 50 Series Service Starter"
echo "=========================================="
echo ""
echo "This script will start the TTS, STT, and Voice Cloning services"
echo "natively on your system to utilize CUDA 12.9."
echo ""
echo "Make sure you have already started Docker Compose"
echo "with 'docker compose up --build' in another terminal."
echo ""
echo "Press Ctrl+C to stop all services."
echo "=========================================="
echo ""

# RTX 50 FIX: Ensure nvidia-smi is in PATH for Rust compilation
export PATH="$HOME/.local/bin:$PATH"

# RTX 50 FIX: Force compute capability to 90 since CUDA 12.6 doesn't support 120 (Blackwell)
export CUDA_COMPUTE_CAP=90

# Check if HUGGING_FACE_HUB_TOKEN is set
if [ -z "$HUGGING_FACE_HUB_TOKEN" ]; then
    echo "ERROR: HUGGING_FACE_HUB_TOKEN is not set!"
    echo "Please set it with: export HUGGING_FACE_HUB_TOKEN=hf_..."
    exit 1
fi

# Verify nvidia-smi is accessible
if ! command -v nvidia-smi &> /dev/null; then
    echo "ERROR: nvidia-smi not found in PATH!"
    echo "The wrapper should be at ~/.local/bin/nvidia-smi"
    echo "Please check the RTX50_SETUP_GUIDE.md for troubleshooting."
    exit 1
fi

# Kill lingering moshi-server processes to avoid port conflicts and CUDA deinit errors
if pgrep -x moshi-server >/dev/null; then
  echo "Killing existing moshi-server processes..."
  pkill -x moshi-server || true
  sleep 1
fi

# Function to cleanup background processes
cleanup() {
    echo ""
    echo "Stopping services..."
    kill $(jobs -p) 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

# Change to project directory
cd "$(dirname "$0")"

echo "Starting TTS service on port 8089..."
./dockerless/start_tts.sh > logs/tts.log 2>&1 &
TTS_PID=$!

echo "Starting STT service on port 8090..."
./dockerless/start_stt.sh > logs/stt.log 2>&1 &
STT_PID=$!

echo "Starting Voice Cloning service on port 8092..."
./dockerless/start_voice_cloning.sh > logs/voice-cloning.log 2>&1 &
VOICE_CLONING_PID=$!

echo ""
echo "=========================================="
echo "Services started!"
echo "TTS PID: $TTS_PID"
echo "STT PID: $STT_PID"
echo "Voice Cloning PID: $VOICE_CLONING_PID"
echo "=========================================="
echo ""
echo "Logs are being written to:"
echo "  - TTS: logs/tts.log"
echo "  - STT: logs/stt.log"
echo "  - Voice Cloning: logs/voice-cloning.log"
echo ""
echo "You can monitor them with:"
echo "  tail -f logs/tts.log"
echo "  tail -f logs/stt.log"
echo ""
echo "Press Ctrl+C to stop all services."
echo "=========================================="

# Wait for all background processes
wait
