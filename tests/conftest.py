#it makes the scripts/ folder importable from the tests, wherever pytest is launched from
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))