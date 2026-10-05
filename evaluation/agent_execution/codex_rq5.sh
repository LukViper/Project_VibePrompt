#!/usr/bin/env bash
# RQ5 Codex wrapper — reads prompt from file; never interpolates secrets into logs.
# Required env: VIBEPROMPT_TASK_DIR, VIBEPROMPT_TASK_PROMPT
set -euo pipefail

die() {
  echo "codex_rq5: ERROR: $*" >&2
  exit 1
}

: "${VIBEPROMPT_TASK_DIR:?VIBEPROMPT_TASK_DIR is required}"
: "${VIBEPROMPT_TASK_PROMPT:?VIBEPROMPT_TASK_PROMPT is required}"

[[ -d "$VIBEPROMPT_TASK_DIR" ]] || die "VIBEPROMPT_TASK_DIR is not a directory: $VIBEPROMPT_TASK_DIR"
[[ -f "$VIBEPROMPT_TASK_PROMPT" ]] || die "VIBEPROMPT_TASK_PROMPT is not a file: $VIBEPROMPT_TASK_PROMPT"
[[ -s "$VIBEPROMPT_TASK_PROMPT" ]] || die "VIBEPROMPT_TASK_PROMPT is empty: $VIBEPROMPT_TASK_PROMPT"

if ! command -v codex >/dev/null 2>&1; then
  die "codex CLI not found on PATH. Install Codex CLI or fix PATH before scientific RQ5."
fi

# Prompt is fed via stdin to avoid ARG_MAX truncation and shell-word splitting.
# Working directory is set with -C so the agent sandbox matches the task workspace.
exec codex exec \
  --sandbox workspace-write \
  -C "$VIBEPROMPT_TASK_DIR" \
  - <"$VIBEPROMPT_TASK_PROMPT"

