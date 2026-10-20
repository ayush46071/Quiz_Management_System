"""Launch the Python-only desktop app: python app.py [--demo]."""
import argparse
import sys
from pathlib import Path
from quizcore.config import Config, ROOT
from quizcore.service import Service
from quizcore.demo import seed_demo


def main(argv=None):
    parser = argparse.ArgumentParser(description='Native Python quiz application')
    parser.add_argument('--demo', action='store_true', help='Seed demonstration accounts only when the database is empty')
    parser.add_argument('--data-dir', type=Path, default=ROOT/'data')
    parser.add_argument('--check', action='store_true', help='Check dependencies without opening a window')
    args = parser.parse_args(argv)
    try:
        import tkinter as tk
        from quizui.application import QuizApplication
    except ImportError as error:
        print(f'Cannot load the desktop interface: {error}\nInstall Python with Tcl/Tk support and extract the entire project ZIP.')
        return 1
    if args.check:
        print(f'Python {sys.version.split()[0]} | Tk {tk.TkVersion} | Native interface imports OK')
        try:
            import matplotlib
            print(f'Matplotlib {matplotlib.__version__}: charts available')
        except ImportError:
            print('Charts require: python -m pip install -r requirements.txt')
            return 1
        print('Dependency check complete. Run python app.py to test the actual desktop window.')
        return 0
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError as error:
        print(f'A graphical desktop is required: {error}\nRun this application in a normal Windows, macOS or Linux desktop session.')
        return 1
    service = None
    try:
        config = Config(args.data_dir)
        config.demo = args.demo
        service = Service(config)
        if args.demo: seed_demo(service)
        QuizApplication(root, service, args.demo)
        service.start_worker()
        root.deiconify()
    except Exception as error:
        from tkinter import messagebox
        messagebox.showerror('Unable to start', f'{error}\n\nCheck that the app folder is writable. Recovery tools are in the scripts folder.', parent=root)
        if service:
            try: service.close()
            except Exception: pass
        root.destroy()
        return 1
    root.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
