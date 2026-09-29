#!/usr/bin/env bash
# Лінтери: ruff (Python, правила — ruff.toml) і shellcheck (bash, винятки — .shellcheckrc).
# Лише правила, що ловлять помилки, а не стиль. Архіви (_deprecated/, versions/, latest/) не перевіряються.
# Використання: tools/lint.sh      Код виходу 0 — чисто.
# Лінтери живуть у tools/.venv (tools/requirements-dev.txt); немає — поставити:
#   tools/.venv/bin/python -m pip install -r tools/requirements-dev.txt
cd "$(dirname "$0")/.." || exit 1
BIN=tools/.venv/bin
for t in ruff shellcheck; do
  [ -x "$BIN/$t" ] || { echo "lint: немає $BIN/$t — tools/.venv/bin/python -m pip install -r tools/requirements-dev.txt"; exit 2; }
done
bad=0
echo "== ruff"
"$BIN/ruff" check . || bad=1
echo "== shellcheck"
# --others: і ще не додані в git скрипти (новий скрипт перевіряється до першого коміту)
if { git ls-files --cached --others --exclude-standard '*.sh' | grep -vE '^(_deprecated|versions|latest)/'; echo tools/git-hooks/pre-commit; } \
   | xargs "$BIN/shellcheck"; then echo "All checks passed!"; else bad=1; fi
exit $bad
