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

# OPTIMIZATION: Check if we need to recompile moshi-server
MOSHI_BINARY="$HOME/.cargo/bin/moshi-server"
ENV_HASH_FILE="dockerless/.venv/moshi_env_hash"
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

# Start STT server
moshi-server worker --config services/moshi-server/configs/stt.toml --port 8090
