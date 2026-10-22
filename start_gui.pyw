"""Double-click to launch with the project's virtual environment."""
from pathlib import Path
import subprocess
import sys


root = Path(__file__).resolve().parent
pythonw = root / '.venv' / 'Scripts' / 'pythonw.exe'
if pythonw.exists() and Path(sys.executable).resolve() != pythonw.resolve():
    subprocess.Popen([str(pythonw), str(Path(__file__).resolve())], cwd=root)
else:
    from casino.gui import main
    main()
