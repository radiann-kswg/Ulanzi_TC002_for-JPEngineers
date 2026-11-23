"""Project-local status observer. The host gets no permission decision or model input."""
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge.__main__ import main

if __name__=="__main__":
    main(sys.argv[1:])
