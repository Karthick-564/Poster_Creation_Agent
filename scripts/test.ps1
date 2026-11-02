# Minimal test policy for the poster pipeline.
#
#   scripts\test.ps1          -> CORE suite  (fast invariants, no rendering)
#   scripts\test.ps1 -All     -> FULL suite  (render paths, composer, loops)
#
# Policy: agents and auditors run CORE by default after commits that touch
# resolver / planner / house style / doctrine / gates config.
# FULL is required only when composer.py, unified_pipeline.py, qa/gates.py,
# or anything rendering-adjacent changed.
param([switch]$All)
Set-Location (Join-Path $PSScriptRoot "..")

$core = @(
  "tests/test_assets.py",
  "tests/test_doctrine_c4.py",
  "tests/test_house_style.py",
  "tests/test_gates.py",
  "tests/test_planner_c2.py",
  "tests/test_no_hardcoded_paths.py",
  "tests/test_palette_policy.py"
)

if ($All) {
  python -m pytest tests/ -q
} else {
  python -m pytest @core -q
}
