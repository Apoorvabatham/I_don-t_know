"""Make `python3 -m unittest discover -s tests -q` work from the repo root
without installation: put the repo root on sys.path."""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
