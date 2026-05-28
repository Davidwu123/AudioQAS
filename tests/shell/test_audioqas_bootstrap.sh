#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT_DIR/scripts/audioqas-bootstrap"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

mkdir -p "$TMP_DIR/repo/scripts" "$TMP_DIR/bin"
cp "$SCRIPT" "$TMP_DIR/repo/scripts/audioqas-bootstrap"
chmod +x "$TMP_DIR/repo/scripts/audioqas-bootstrap"

cat >"$TMP_DIR/bin/python3" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
echo "python3 $*" >> "$AUDIOQAS_TEST_LOG"
if [ "${1:-}" = "-" ]; then
  exit 1
fi
if [ "${1:-}" = "-m" ] && [ "${2:-}" = "venv" ]; then
  echo "wrong-python-created-venv" >> "$AUDIOQAS_TEST_LOG"
fi
exit 1
STUB
chmod +x "$TMP_DIR/bin/python3"

cat >"$TMP_DIR/bin/python3.11" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
echo "python3.11 $*" >> "$AUDIOQAS_TEST_LOG"
if [ "${1:-}" = "-" ]; then
  exit 0
fi
if [ "${1:-}" = "-m" ] && [ "${2:-}" = "venv" ]; then
  mkdir -p .venv/bin
  cat > .venv/bin/python <<'PYTHON'
#!/usr/bin/env bash
if [ "${1:-}" = "-" ]; then
  exit 0
fi
echo "venv-python $*" >> "$AUDIOQAS_TEST_LOG"
PYTHON
  chmod +x .venv/bin/python
  exit 0
fi
exit 1
STUB
chmod +x "$TMP_DIR/bin/python3.11"

export AUDIOQAS_TEST_LOG="$TMP_DIR/log"
export PATH="$TMP_DIR/bin:/usr/bin:/bin"

cd "$TMP_DIR/repo"
./scripts/audioqas-bootstrap --no-start --no-open

grep -q "python3.11 -m venv .venv" "$AUDIOQAS_TEST_LOG" || fail "python3.11 was not used to create .venv"
grep -q "venv-python -m audioqas.bootstrap --no-start --no-open" "$AUDIOQAS_TEST_LOG" || fail "venv python did not run bootstrap"
if grep -q "wrong-python-created-venv" "$AUDIOQAS_TEST_LOG"; then
  fail "unsupported python3 created .venv"
fi

mkdir -p "$TMP_DIR/old/repo/scripts" "$TMP_DIR/old/repo/.venv/bin"
cp "$SCRIPT" "$TMP_DIR/old/repo/scripts/audioqas-bootstrap"
chmod +x "$TMP_DIR/old/repo/scripts/audioqas-bootstrap"
cat > "$TMP_DIR/old/repo/.venv/bin/python" <<'PYTHON'
#!/usr/bin/env bash
echo "old-venv-python $*" >> "$AUDIOQAS_TEST_LOG"
if [ "${1:-}" = "-" ]; then
  exit 1
fi
exit 1
PYTHON
chmod +x "$TMP_DIR/old/repo/.venv/bin/python"
cd "$TMP_DIR/old/repo"
./scripts/audioqas-bootstrap --no-start

grep -q "python3.11 -m venv .venv" "$AUDIOQAS_TEST_LOG" || fail "old .venv was not rebuilt with python3.11"
grep -q "venv-python -m audioqas.bootstrap --no-start" "$AUDIOQAS_TEST_LOG" || fail "rebuilt venv did not run bootstrap"
