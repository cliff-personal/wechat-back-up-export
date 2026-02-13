#!/usr/bin/env bash
# Wrapper to run daily dingtalk_daily.py with environment setup, logging, and retries
set -euo pipefail
ROOT_DIR="/Users/cliff/workspace/wechat-business"
LOG_DIR="$ROOT_DIR/logs"
LOG_FILE="$LOG_DIR/dingtalk_daily_cron.log"
SCRIPT="$ROOT_DIR/src/dingtalk_daily.py"
VENV_PY="$ROOT_DIR/.venv/bin/python"
# Ensure log dir exists
mkdir -p "$LOG_DIR"
# Timestamp for this run
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
{
  echo "--- RUN START $TS ---"
  echo "pwd: $(pwd)"
  echo "whoami: $(whoami)"
  # Prefer sourcing a minimal env file for cron (avoid interactive zsh init)
  if [ -f "$HOME/.cron_env" ]; then
    # Export all vars in the file
    set -a
    # shellcheck disable=SC1090
    source "$HOME/.cron_env" >/dev/null 2>&1 || true
    set +a
  else
    # Fallback: source user's shell rc but defensively to avoid oh-my-zsh errors
    if [ -f "$HOME/.zshrc" ]; then
      # Source defensively: avoid failing on unbound vars in non-interactive shells
      set +u
      # shellcheck disable=SC1090
      source "$HOME/.zshrc" >/dev/null 2>&1 || true
      set -u
    fi
  fi
  echo "AMAP_KEY present: ${AMAP_KEY:+YES}"
  echo "Using python: $VENV_PY"
  # Activate venv if exists
  if [ -x "$VENV_PY" ]; then
    # Print environment snapshot (masked) and capture exit code and stderr/stdout
    echo "WEBHOOK present: ${WEBHOOK:+YES}" 
    if [ -n "${WEBHOOK:-}" ]; then
      # mask token part for logs (show prefix)
      echo "WEBHOOK sample: ${WEBHOOK:0:40}..."
    fi
    if [ -n "${SECRET:-}" ]; then
      echo "SECRET present: YES (masked)"
      echo "SECRET sample: ${SECRET:0:6}...${SECRET: -4}"
    fi
    # run and capture output
    set +e
    "$VENV_PY" "$SCRIPT" --webhook "${WEBHOOK:-}" --secret "${SECRET:-}" --city "包头" --llm-base-url "http://127.0.0.1:4141/" --llm-model "gpt-5.2" --llm-api-key "" > "$LOG_DIR/dingtalk_daily.out" 2> "$LOG_DIR/dingtalk_daily.err"
    rc=$?
    echo "dingtalk_daily exit:$rc"
    echo "--- STDOUT (tail 200) ---"
    tail -n 200 "$LOG_DIR/dingtalk_daily.out" || true
    echo "--- STDERR (tail 200) ---"
    tail -n 200 "$LOG_DIR/dingtalk_daily.err" || true
    set -e
    if [ $rc -ne 0 ]; then
      echo "dingtalk_daily failed with exit $rc"
    fi
  else
    echo "Virtualenv python not found: $VENV_PY"
    exit 2
  fi
  echo "--- RUN END $TS ---"
  echo ""
} >> "$LOG_FILE" 2>&1
