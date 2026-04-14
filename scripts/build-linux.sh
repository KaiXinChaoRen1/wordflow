#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

venv_path="$project_root/.venv-build-linux"
python_exe="$venv_path/bin/python"
dist_path="$project_root/dist/linux"
work_path="$project_root/build/pyinstaller"
spec_path="$project_root/build/pyinstaller-spec"

if [[ ! -x "$python_exe" ]]; then
  python3 -m venv "$venv_path"
fi

"$python_exe" -m pip install --upgrade pip
"$python_exe" -m pip install --upgrade ".[build]"

"$python_exe" -m PyInstaller \
  --noconfirm \
  --clean \
  --onefile \
  --console \
  --name wordflow \
  --paths src \
  --collect-all textual \
  --collect-all rich \
  --distpath "$dist_path" \
  --workpath "$work_path" \
  --specpath "$spec_path" \
  tools/wordflow_launcher.py

echo
echo "Built: $dist_path/wordflow"
