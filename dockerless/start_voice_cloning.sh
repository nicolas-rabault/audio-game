#!/bin/bash
set -ex
cd "$(dirname "$0")/"

# RTX 50 FIX: Ensure nvidia-smi is in PATH for Rust compilation
export PATH="$HOME/.local/bin:$PATH"

# RTX 50 FIX: Force compute capability to 90 (Hopper/Ada) since CUDA 12.6 doesn't support 120 (Blackwell)
# This allows compilation to succeed. The RTX 50 series is backward compatible with compute capability 90.
export CUDA_COMPUTE_CAP=90

# Ensure required project files for building moshi-server Python integration exist
[ -f pyproject.toml ] || wget https://raw.githubusercontent.com/kyutai-labs/moshi/9837ca328d58deef5d7a4fe95a0fb49c902ec0ae/rust/moshi-server/pyproject.toml
[ -f uv.lock ] || wget https://raw.githubusercontent.com/kyutai-labs/moshi/9837ca328d58deef5d7a4fe95a0fb49c902ec0ae/rust/moshi-server/uv.lock

uv venv
source .venv/bin/activate

# Install Python dependencies (match TTS setup for compatibility)
uv pip install --upgrade pip
uv pip install --index-url https://download.pytorch.org/whl/cu128 torch==2.8.0+cu128 torchaudio==2.8.0+cu128
uv pip install huggingface-hub sentencepiece sphn safetensors pydantic numpy
uv pip install --no-deps moshi==0.2.8

# Environment for Rust build to locate Python
export LD_LIBRARY_PATH=$(python -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')
export PYTHONPATH=$(python -c 'import sys; print(":".join(sys.path))')

cd ..

# A fix for building Sentencepiece on GCC 15, see: https://github.com/google/sentencepiece/issues/1108
export CXXFLAGS="-include cstdint"

# Build moshi-server (force to ensure correct Python linkage)
echo "Compiling moshi-server with venv Python (takes ~2 minutes)..."
cargo install --features cuda --force moshi-server@0.6.4

# Verify imports
echo "Verifying Python imports..."
python -c "import huggingface_hub, moshi; print('✅ deps found')"

# Start voice cloning service
echo "Starting Voice Cloning service on port 8092..."
moshi-server worker --config services/moshi-server/configs/voice-cloning.toml --port 8092


