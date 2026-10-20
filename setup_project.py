"""Create .venv and install chart dependencies using Python alone."""
from pathlib import Path
import subprocess
import sys
import venv

def main():
    root = Path(__file__).resolve().parent
    environment = root/'.venv'
    if sys.version_info < (3, 10):
        print('Please install Python 3.10 or later.');return 1
    try:
        import tkinter
    except ImportError:
        print('Install Python with Tcl/Tk support before setup.');return 1
    executable = environment/('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    if not executable.is_file():
        venv.EnvBuilder(with_pip=True).create(environment)
    result = subprocess.run([str(executable), '-m', 'pip', 'install', '-r', str(root/'requirements.txt')])
    if result.returncode:
        print('Chart installation failed. Retry when connected. The core quiz functions use only Python standard libraries.')
        return result.returncode
    print('Setup complete. Run python run_demo.py, or activate .venv and run python app.py.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
