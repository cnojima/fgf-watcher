"""Driver for PaddleX module training, following its documented pattern
(paddlex.engine.Engine reads a -c/--config CLI arg via argparse, so this
just needs to exist as an entry point - PaddleX ships no main.py of its
own for this, only the CLI's --pipeline inference path, which is a
different thing from module training).

Usage (from the ocr_training/ directory, with the dedicated Paddle venv -
see the ocr-training scoping conversation for why a separate venv/Python
version is needed):
    ../.venv-paddle/bin/python train.py -c orange_kid_rec.yaml
"""
from paddlex.engine import Engine

if __name__ == "__main__":
    Engine().run()
