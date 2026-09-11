#!/usr/bin/env zsh
source .venv/bin/activate
# python src/calibrate.py list
# python src/calibrate.py shot "Foundation: Galactic Frontier"
# python src/collect_all_flagships.py
# source /Users/curisu/dev/fgf-watcher/.venv/bin/activate && python3 -m py_compile src/calibrate.py && echo OK && ./scripts/test.sh

CAPTURE_DIR=data/captures/20260911-082553
OUTPUT_DIR=$CAPTURE_DIR/output

python src/replay_all_flagships.py --output $OUTPUT_DIR $CAPTURE_DIR