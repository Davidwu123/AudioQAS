#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/Davidwu123/AudioQAS.git"
TARGET_DIR=""
BOOTSTRAP_ARGS=()

log() {
  printf '%s\n' "$*"
}

install_git_if_missing() {
  if command -v git >/dev/null 2>&1; then
    return
  fi
  log "[git] Purpose: clone or update AudioQAS source code from GitHub."
  if command -v brew >/dev/null 2>&1; then
    brew install git
    return
  fi
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y git
    return
  fi
  log "[git] Failed. Reason: git missing and no supported package manager found."
  exit 1
}

is_audioqas_repo() {
  dir="$1"
  [ -d "$dir/.git" ] || return 1
  (
    cd "$dir"
    git rev-parse --is-inside-work-tree >/dev/null 2>&1 &&
      git remote get-url origin 2>/dev/null | grep -Eq 'github.com[:/]Davidwu123/AudioQAS(\.git)?$'
  )
}

resolve_target_dir() {
  if [ -n "$TARGET_DIR" ]; then
    printf '%s\n' "$TARGET_DIR"
    return
  fi
  if is_audioqas_repo "."; then
    printf '%s\n' "."
    return
  fi
  printf '%s\n' "AudioQAS"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dir)
      shift
      [ "$#" -gt 0 ] || { log "--dir requires a path"; exit 1; }
      TARGET_DIR="$1"
      ;;
    --dir=*)
      TARGET_DIR="${1#--dir=}"
      ;;
    *)
      BOOTSTRAP_ARGS+=("$1")
      ;;
  esac
  shift
done

install_git_if_missing

target="$(resolve_target_dir)"
if [ -e "$target" ]; then
  if ! is_audioqas_repo "$target"; then
    log "[repo] Failed. Reason: $target already exists but is not AudioQAS repo. Next: choose another --dir or move that directory."
    exit 1
  fi
  log "[repo] Found AudioQAS repo at $target, updating."
  (cd "$target" && git pull --ff-only)
else
  log "[repo] Purpose: download AudioQAS source code."
  log "[repo] Source: $REPO_URL"
  git clone "$REPO_URL" "$target"
fi

cd "$target"
if [ "${#BOOTSTRAP_ARGS[@]}" -eq 0 ]; then
  exec ./scripts/audioqas-bootstrap
fi
exec ./scripts/audioqas-bootstrap "${BOOTSTRAP_ARGS[@]}"
