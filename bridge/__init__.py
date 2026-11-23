"""Windows-side collectors for the TC002 developer clock."""
from pathlib import Path
import sys

# Project-local installation used by the Windows launcher and the SDK build instructions.
dependencies=Path(__file__).resolve().parents[1]/"build"/"bridge-deps"
if dependencies.is_dir():
    sys.path.append(str(dependencies))
