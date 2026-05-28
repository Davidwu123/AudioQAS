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
"$SCRIPT"
grep -q "bootstrap $" "$AUDIOQAS_TEST_LOG" || fail "bootstrap without args not called"

cd "$TMP_DIR"
rm -rf AudioQAS
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

mkdir -p "$TMP_DIR/git-install/bin"
cat > "$TMP_DIR/git-install/bin/bash" <<'STUB'
#!/bin/sh
exec /bin/bash "$@"
STUB
chmod +x "$TMP_DIR/git-install/bin/bash"
cat > "$TMP_DIR/git-install/bin/awk" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
key=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    -v)
      shift
      key="${1#key=}"
      ;;
    -*)
      ;;
    *)
      file="$1"
      ;;
  esac
  shift
done
while IFS= read -r line; do
  case "$line" in
    "$key="*)
      value="${line#*=}"
      value="${value%\"}"
      value="${value#\"}"
      printf '%s\n' "$value"
      exit 0
      ;;
  esac
done < "$file"
STUB
chmod +x "$TMP_DIR/git-install/bin/awk"
cat > "$TMP_DIR/git-install/bin/dirname" <<'STUB'
#!/usr/bin/env bash
path="${1%/*}"
if [ "$path" = "$1" ]; then
  printf '.\n'
else
  printf '%s\n' "$path"
fi
STUB
chmod +x "$TMP_DIR/git-install/bin/dirname"
cat > "$TMP_DIR/git-install/bin/grep" <<'STUB'
#!/usr/bin/env bash
/usr/bin/grep "$@"
STUB
chmod +x "$TMP_DIR/git-install/bin/grep"
cat > "$TMP_DIR/git-install/bin/mkdir" <<'STUB'
#!/usr/bin/env bash
/bin/mkdir "$@"
STUB
chmod +x "$TMP_DIR/git-install/bin/mkdir"
cat > "$TMP_DIR/git-install/bin/chmod" <<'STUB'
#!/usr/bin/env bash
/bin/chmod "$@"
STUB
chmod +x "$TMP_DIR/git-install/bin/chmod"
cat > "$TMP_DIR/git-install/bin/cat" <<'STUB'
#!/usr/bin/env bash
/bin/cat "$@"
STUB
chmod +x "$TMP_DIR/git-install/bin/cat"
cat > "$TMP_DIR/git-install/bin/apt-get" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
echo "install-apt-get $*" >> "$AUDIOQAS_TEST_LOG"
if [ "${1:-}" = "install" ]; then
  cat > "$(dirname "$0")/git" <<'GIT'
#!/usr/bin/env bash
set -euo pipefail
echo "installed-git $*" >> "$AUDIOQAS_TEST_LOG"
if [ "${1:-}" = "rev-parse" ]; then
  exit 1
fi
if [ "${1:-}" = "clone" ]; then
  target="$3"
  mkdir -p "$target/.git" "$target/scripts"
  echo "https://github.com/Davidwu123/AudioQAS.git" > "$target/.git/audioqas-remote"
  cat > "$target/scripts/audioqas-bootstrap" <<'BOOT'
#!/usr/bin/env bash
echo "bootstrap-git-install $*" >> "$AUDIOQAS_TEST_LOG"
BOOT
  chmod +x "$target/scripts/audioqas-bootstrap"
fi
GIT
  chmod +x "$(dirname "$0")/git"
fi
STUB
chmod +x "$TMP_DIR/git-install/bin/apt-get"
cat > "$TMP_DIR/git-install/bin/sudo" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
"$@"
STUB
chmod +x "$TMP_DIR/git-install/bin/sudo"
cd "$TMP_DIR/git-install"
if PATH="$TMP_DIR/git-install/bin" AUDIOQAS_TEST_OS_RELEASE="$TMP_DIR/git-install/missing-os-release" /bin/bash "$SCRIPT" --no-start \
  >"$TMP_DIR/git-install/error.log" 2>&1; then
  fail "git install should reject non-Ubuntu 22.04"
fi
grep -q "Failed. Reason: automatic apt install is only supported on Ubuntu 22.04" "$TMP_DIR/git-install/error.log" || fail "git install should reject non-Ubuntu 22.04"

cat > "$TMP_DIR/git-install/os-release" <<'OS'
ID=ubuntu
VERSION_ID="22.04"
OS
PATH="$TMP_DIR/git-install/bin" AUDIOQAS_TEST_OS_RELEASE="$TMP_DIR/git-install/os-release" /bin/bash "$SCRIPT" --no-start
grep -q "install-apt-get install -y git" "$AUDIOQAS_TEST_LOG" || fail "Ubuntu 22.04 git install not used"
grep -q "bootstrap-git-install --no-start" "$AUDIOQAS_TEST_LOG" || fail "bootstrap after git install not called"
