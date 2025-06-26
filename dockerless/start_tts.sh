#!/bin/bash
set -ex
cd "$(dirname "$0")/.."

# A fix for building Sentencepiece on GCC 15, see: https://github.com/google/sentencepiece/issues/1108
export CXXFLAGS="-include cstdint"

cargo install --features cuda moshi-server@0.6.1
moshi-server worker --config services/moshi-server/configs/tts-py.toml --port 8089


# cd ../moshi-rs
# cd moshi-server
# uv sync
# export PATH=$(pwd)/.venv/bin:$PATH
# export LD_LIBRARY_PATH=$(python -c "from distutils.sysconfig import get_config_var as s; print(s('LIBDIR'))")
# cd ..
# cargo run --features=cuda --bin=moshi-server -r -- worker --config=moshi-server/config-py-swarm-small.toml --port 8089
