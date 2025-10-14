#!/bin/bash
set -ex
cd "$(dirname "$0")/.."

# RTX 50 FIX: Ensure nvidia-smi is in PATH for Rust compilation
export PATH="$HOME/.local/bin:$PATH"

# RTX 50 FIX: Force compute capability to 90 (Hopper/Ada) since CUDA 12.6 doesn't support 120 (Blackwell)
# This allows compilation to succeed. The RTX 50 series is backward compatible with compute capability 90.
export CUDA_COMPUTE_CAP=90

# A fix for building Sentencepiece on GCC 15, see: https://github.com/google/sentencepiece/issues/1108
export CXXFLAGS="-include cstdint"

# Ensure we have the same Python venv as TTS and activate it
if [ ! -d "dockerless/.venv" ]; then
  cd dockerless
  uv venv
  source .venv/bin/activate
  cd ..
else
  source dockerless/.venv/bin/activate
fi

# Export Python runtime paths so the embedded Python can be found at runtime
export LD_LIBRARY_PATH=$(python -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')
export PYTHONPATH=$(python -c 'import sys; print(":".join(sys.path))')

# Optional: rebuild if needed. Usually not required for STT, so skip --force here
cargo install --features cuda moshi-server@0.6.4

# Start STT server
moshi-server worker --config services/moshi-server/configs/stt.toml --port 8090
