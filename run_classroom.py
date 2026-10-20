"""Start a separate classroom database without demonstration accounts."""
from pathlib import Path
import subprocess
import sys

if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    python = root/('.venv/Scripts/python.exe' if sys.platform == 'win32' else '.venv/bin/python')
    if not python.is_file(): python = Path(sys.executable)
    raise SystemExit(subprocess.call([str(python), str(root/'app.py'), '--data-dir', str(root/'data/classroom'), *sys.argv[1:]]))
