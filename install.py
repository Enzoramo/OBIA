#!/usr/bin/env python3
"""Public entry point. All runtime files are also shipped inside skills/obia."""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).resolve().parent / 'skills/obia/scripts/setup_obia.py'), run_name='__main__')
