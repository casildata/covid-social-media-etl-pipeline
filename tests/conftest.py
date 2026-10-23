import sys
from pathlib import Path

# the pipeline's modules live in src/ and import each other by name
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
