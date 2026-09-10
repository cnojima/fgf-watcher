#!/usr/bin/env zsh
source .venv/bin/activate
python src/calibrate.py list
python src/calibrate.py shot "Foundation: Galactic Frontier"

python src/collect_all_flagships.py

# source /Users/curisu/dev/fgf-watcher/.venv/bin/activate && python3 -m py_compile src/calibrate.py && echo OK && ./scripts/test.sh

