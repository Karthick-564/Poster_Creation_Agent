#!/usr/bin/env bash
# Minimal test policy for the poster pipeline.
#
#   scripts/test.sh        -> CORE suite  (fast invariants, no rendering)
#   scripts/test.sh --all  -> FULL suite  (render paths, composer, loops)
#
# Policy: agents and auditors run CORE by default after commits that touch
# resolver / planner / house style / doctrine / gates config.
# FULL is required only when composer.py, unified_pipeline.py, qa/gates.py,
# or anything rendering-adjacent changed.
set -e
cd "$(dirname "$0")/.."

CORE_TESTS=(
  tests/test_assets.py
  tests/test_doctrine_c4.py
  tests/test_house_style.py
  tests/test_gates.py
  tests/test_planner_c2.py
  tests/test_no_hardcoded_paths.py
  tests/test_palette_policy.py
)

if [ "$1" = "--all" ]; then
  exec python3 -m pytest tests/ -q
else
  exec python3 -m pytest "${CORE_TESTS[@]}" -q
fi
