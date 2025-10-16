#!/bin/bash
set -ex
cd "$(dirname "$0")/"

# RTX 50 FIX: Ensure nvidia-smi is in PATH for Rust compilation
export PATH="$HOME/.local/bin:$PATH"

# RTX 50 FIX: Force compute capability to 90 (Hopper/Ada) since CUDA 12.6 doesn't support 120 (Blackwell)
# This allows compilation to succeed. The RTX 50 series is backward compatible with compute capability 90.
export CUDA_COMPUTE_CAP=90

# This is part of a hack to get dependencies needed for the TTS Rust server, because it integrates a Python component
[ -f pyproject.toml ] || wget https://raw.githubusercontent.com/kyutai-labs/moshi/9837ca328d58deef5d7a4fe95a0fb49c902ec0ae/rust/moshi-server/pyproject.toml
[ -f uv.lock ] || wget https://raw.githubusercontent.com/kyutai-labs/moshi/9837ca328d58deef5d7a4fe95a0fb49c902ec0ae/rust/moshi-server/uv.lock

uv venv
source .venv/bin/activate

# Install Python dependencies for TTS with CUDA 12.8-capable wheels
# 1) Install Torch/Torchaudio from the official cu128 index (supports Blackwell)
# 2) Install remaining deps
# 3) Install moshi without deps to avoid downgrading Torch
uv pip install --upgrade pip
uv pip install --index-url https://download.pytorch.org/whl/cu128 torch==2.8.0+cu128 torchaudio==2.8.0+cu128
uv pip install huggingface-hub sentencepiece sphn safetensors pydantic numpy
uv pip install --no-deps moshi==0.2.8

# This env var must be set to get the correct environment for the Rust build.
# Must be set before running `cargo install`!
export LD_LIBRARY_PATH=$(python -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')
export PYTHONPATH=$(python -c 'import sys; print(":".join(sys.path))')

# Verify Python environment
echo "Using Python: $(which python)"
echo "LD_LIBRARY_PATH: $LD_LIBRARY_PATH"
python - <<'PYCHK'
import sys, torch
print('Torch version:', torch.__version__)
print('CUDA available:', torch.cuda.is_available())
print('Device capability (if available):', torch.cuda.get_device_capability() if torch.cuda.is_available() else 'n/a')
PYCHK

cd ..

# A fix for building Sentencepiece on GCC 15, see: https://github.com/google/sentencepiece/issues/1108
export CXXFLAGS="-include cstdint"

# OPTIMIZATION: Check if we need to recompile moshi-server
MOSHI_BINARY="$HOME/.cargo/bin/moshi-server"
ENV_HASH_FILE=".venv/moshi_env_hash"
NEED_RECOMPILE=true

# Create environment hash to detect changes
create_env_hash() {
    {
        echo "PYTHON_PATH:$(which python)"
        echo "LD_LIBRARY_PATH:$LD_LIBRARY_PATH"
        echo "PYTHONPATH:$PYTHONPATH"
        echo "CUDA_COMPUTE_CAP:$CUDA_COMPUTE_CAP"
        echo "CXXFLAGS:$CXXFLAGS"
        echo "MOSHI_VERSION:0.6.4"
        # Include Python package versions that affect compilation
        python -c "import torch, moshi, huggingface_hub; print(f'PYTHON_DEPS:torch={torch.__version__},moshi={moshi.__version__},hf_hub={huggingface_hub.__version__}')" 2>/dev/null || echo "PYTHON_DEPS:unknown"
    } | sha256sum | cut -d' ' -f1
}

# Check if binary exists and environment hasn't changed
if [ -f "$MOSHI_BINARY" ] && [ -f "$ENV_HASH_FILE" ]; then
    CURRENT_HASH=$(create_env_hash)
    STORED_HASH=$(cat "$ENV_HASH_FILE" 2>/dev/null || echo "")
    
    if [ "$CURRENT_HASH" = "$STORED_HASH" ]; then
        echo "✅ Using cached moshi-server binary (environment unchanged)"
        NEED_RECOMPILE=false
    else
        echo "🔄 Environment changed, need to recompile moshi-server"
    fi
else
    echo "🔄 No cached binary found, need to compile moshi-server"
fi

if [ "$NEED_RECOMPILE" = true ]; then
    echo "Compiling moshi-server with venv Python (takes ~2 minutes)..."
    cargo install --features cuda --force moshi-server@0.6.4
    
    # Store environment hash for next time
    create_env_hash > "$ENV_HASH_FILE"
    echo "✅ Binary compiled and cached"
fi

# Verify imports work before starting
echo "Verifying Python imports..."
python -c "import huggingface_hub, moshi; print('✅ deps found')"

# Now run moshi-server with the correct Python environment (venv still active)
echo "Starting TTS service on port 8089..."
moshi-server worker --config services/moshi-server/configs/tts.toml --port 8089
