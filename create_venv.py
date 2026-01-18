import os
import sys
import subprocess
import venv
from pathlib import Path

def main():
    venv_dir = Path("corvid_venv")

    if not venv_dir.exists():
        print("Creating virtual environment...")
        venv.create(venv_dir, with_pip=True)

    if os.name == "nt":  # Windows
        python_bin = Path(f"{venv_dir}/Scripts/python.exe")
    else:  # Linux/macOS
        python_bin = Path(f"{venv_dir}/bin/python"
)
    if not os.path.exists(python_bin):
        print("Error: could not find Python inside venv.")
        sys.exit(1)

    if Path("requirements.txt").exists():
        print("Installing requirements...")
        subprocess.check_call([str(python_bin), "-m", "pip", "install", "-r", "requirements.txt"])

if __name__ == "__main__":
    main()
