import os
import sys
import subprocess
import venv
from pathlib import Path

def main():
    if os.name == "nt":  # Windows
        venv_dir = Path("corvid_venv_win")
        python_bin = venv_dir / "Scripts" / "python.exe"
    else:  # Linux/macOS
        venv_dir = Path("corvid_venv_linux")
        python_bin = venv_dir / "bin" / "python"

    if not venv_dir.exists():
        print("Creating virtual environment...")
        venv.create(venv_dir, with_pip=True)

    if not python_bin.exists():
        print("Error: could not find Python inside venv.")
        sys.exit(1)

    if Path("requirements.txt").exists():
        print("Installing requirements...")
        subprocess.check_call([str(python_bin), "-m", "pip", "install", "-r", "requirements.txt"])

if __name__ == "__main__":
    main()
