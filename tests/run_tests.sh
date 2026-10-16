#!/usr/bin/env bash
# 一键回归：单测 + 四 golden 必须 PASS；坏样本必须触发对应 rule id。
set -u
cd "$(dirname "$0")/.."
PY=python3
FAIL=0

echo "== unit tests =="
$PY tests/test_common.py 2>&1 | tail -1 || FAIL=1
$PY tests/test_pool.py 2>&1 | tail -1 || FAIL=1

echo "== golden: neutral (zero config) =="
$PY scripts/validate_issue.py tests/golden/neutral-issue.md || FAIL=1
echo "== golden: embodied-ai-weekly preset =="
P=presets/embodied-ai-weekly.json
$PY scripts/validate_issue.py tests/golden/issue-42.md --config "$P" || FAIL=1
$PY scripts/validate_issue.py tests/golden/issue-43.md --config "$P" || FAIL=1
echo "== golden: embodied-ai-weekly-legacy preset (板块变体) =="
$PY scripts/validate_issue.py tests/golden/issue-40-legacy.md --config presets/embodied-ai-weekly-legacy.json || FAIL=1

check_rule() {
  local file="$1" rule="$2" cfg="${3:-}"
  local out
  if [ -n "$cfg" ]; then
    out=$($PY scripts/validate_issue.py "$file" --config "$cfg" 2>&1)
  else
    out=$($PY scripts/validate_issue.py "$file" 2>&1)
  fi
  if echo "$out" | grep -q "$rule"; then
    echo "OK   $rule <- $file"
  else
    echo "MISS $rule <- $file"
    echo "$out"
    FAIL=1
  fi
}

echo "== bad samples (neutral config) =="
check_rule tests/bad/bad-e01.md "E01"
check_rule tests/bad/issue-9.md "E02"
check_rule tests/bad/bad-e03.md "E03"
check_rule tests/bad/bad-e05.md "E05"
check_rule tests/bad/bad-e07.md "E07"
check_rule tests/bad/bad-e08.md "E08"
check_rule tests/bad/bad-e10.md "E10"
check_rule tests/bad/bad-e11.md "E11"
check_rule tests/bad/bad-e13.md "E13"
check_rule tests/bad/bad-e14.md "E14"

echo "== bad samples (embodied-ai-weekly preset) =="
check_rule tests/bad/bad-e04.md "E04" "$P"
check_rule tests/bad/bad-e06.md "E06" "$P"
check_rule tests/bad/bad-e09.md "E09" "$P"
check_rule tests/bad/bad-e12.md "E12" "$P"
check_rule tests/bad/bad-w01.md "W01" "$P"

if [ "$FAIL" -eq 0 ]; then
  echo "ALL TESTS PASSED"
else
  echo "TESTS FAILED"
fi
exit $FAIL
