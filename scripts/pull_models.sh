#!/usr/bin/env bash
set -euo pipefail

LLM_MODEL="${OLLAMA_LLM_MODEL:-llama3.1:8b}"
FAST_MODEL="${OLLAMA_FAST_MODEL:-qwen2.5:0.5b}"
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"

has_model() {
  ollama list 2>/dev/null | awk '{print $1}' | grep -qx "$1"
}

echo "Ensuring Ollama models: $LLM_MODEL, $FAST_MODEL, $EMBED_MODEL"
for m in "$LLM_MODEL" "$FAST_MODEL" "$EMBED_MODEL"; do
  if has_model "$m"; then
    echo "  $m already present"
  else
    ollama pull "$m"
  fi
done
echo "Models ready."
