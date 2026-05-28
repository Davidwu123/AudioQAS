#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT_DIR/scripts/audioqas-install.sh"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

mkdir -p "$TMP_DIR/bin"
cat >"$TMP_DIR/bin/git" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
echo "git $*" >> "$AUDIOQAS_TEST_LOG"
case "$1" in
  rev-parse)
    if [ "${PWD##*/}" = "AudioQAS" ] && [ -f ".git/audioqas-remote" ]; then
      exit 0
    fi
    exit 1
    ;;
  remote)
    if [ -f ".git/audioqas-remote" ]; then
      cat ".git/audioqas-remote"
      exit 0
    fi
    exit 1
    ;;
  clone)
    target="$3"
    mkdir -p "$target/.git" "$target/scripts"
    echo "https://github.com/Davidwu123/AudioQAS.git" > "$target/.git/audioqas-remote"
    cat > "$target/scripts/audioqas-bootstrap" <<'BOOT'
#!/usr/bin/env bash
echo "bootstrap $*" >> "$AUDIOQAS_TEST_LOG"
BOOT
    chmod +x "$target/scripts/audioqas-bootstrap"
    ;;
  pull)
    ;;
esac
STUB
chmod +x "$TMP_DIR/bin/git"

export AUDIOQAS_TEST_LOG="$TMP_DIR/log"
export PATH="$TMP_DIR/bin:$PATH"

cd "$TMP_DIR"
"$SCRIPT" --with-test --no-start --no-open

grep -q "git clone https://github.com/Davidwu123/AudioQAS.git AudioQAS" "$AUDIOQAS_TEST_LOG" || fail "clone not called"
grep -q "bootstrap --with-test --no-start --no-open" "$AUDIOQAS_TEST_LOG" || fail "bootstrap args not forwarded"

mkdir -p "$TMP_DIR/existing/AudioQAS/.git" "$TMP_DIR/existing/AudioQAS/scripts"
echo "https://github.com/Davidwu123/AudioQAS.git" > "$TMP_DIR/existing/AudioQAS/.git/audioqas-remote"
cat > "$TMP_DIR/existing/AudioQAS/scripts/audioqas-bootstrap" <<'BOOT'
#!/usr/bin/env bash
echo "bootstrap-existing $*" >> "$AUDIOQAS_TEST_LOG"
BOOT
chmod +x "$TMP_DIR/existing/AudioQAS/scripts/audioqas-bootstrap"
cd "$TMP_DIR/existing"
"$SCRIPT" --dir AudioQAS --check-only
grep -q "git pull --ff-only" "$AUDIOQAS_TEST_LOG" || fail "existing repo not updated"
grep -q "bootstrap-existing --check-only" "$AUDIOQAS_TEST_LOG" || fail "existing repo bootstrap not called"

mkdir -p "$TMP_DIR/current/AudioQAS/.git" "$TMP_DIR/current/AudioQAS/scripts"
echo "https://github.com/Davidwu123/AudioQAS.git" > "$TMP_DIR/current/AudioQAS/.git/audioqas-remote"
cat > "$TMP_DIR/current/AudioQAS/scripts/audioqas-bootstrap" <<'BOOT'
#!/usr/bin/env bash
echo "bootstrap-current $*" >> "$AUDIOQAS_TEST_LOG"
BOOT
chmod +x "$TMP_DIR/current/AudioQAS/scripts/audioqas-bootstrap"
cd "$TMP_DIR/current/AudioQAS"
"$SCRIPT" --no-start
grep -q "bootstrap-current --no-start" "$AUDIOQAS_TEST_LOG" || fail "current repo bootstrap not called"

mkdir -p "$TMP_DIR/conflict/AudioQAS"
cd "$TMP_DIR/conflict"
if "$SCRIPT" >/tmp/audioqas-install-conflict.log 2>&1; then
  fail "installer should reject non-repo AudioQAS directory"
fi
grep -q "already exists but is not AudioQAS repo" /tmp/audioqas-install-conflict.log || fail "missing conflict error"
