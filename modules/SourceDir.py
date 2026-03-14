import vpk
from typing import List
from os.path import isdir, isfile
from shutil import copyfile
from pathlib import Path
from tempfile import gettempdir
from sys import exit
from .Gma import Addon, load as loadGma

class SourceDir:
    def __init__(self):
        self.dirs = []
        self.paks: List[vpk.VPK] = []
        self.addons: List[Addon] = []

    def add(self, path):
        if isfile(path):
            if path[-4:] not in [".vpk", ".gma"]:
                print(f"\"{path}\" is not a valid file.")
                exit()
            if path.endswith(".vpk"):
                self.paks.append(vpk.open(path))
            elif path.endswith(".gma"):
                self.addons.append(loadGma(path))

        elif isdir(path):
            self.dirs.append(path)
        else:
            print(f"\"{path}\" is an invalid path.")

    def read_bytes(self, src, silent=False):
        src = Path(src.replace("\\", "/")).as_posix().lower()
        for pak in self.paks:
            try:
                return pak.get_file(src).read()
            except:
                continue

        for addon in self.addons:
            if src in addon.entries:
                tmpPath = f"{gettempdir()}/corvid_addon_tmp"
                addon.entries[src].save(tmpPath)
                with open(tmpPath, "rb") as f:
                    return f.read()

        for dir in self.dirs:
            try:
                with open(f"{dir}/{src}", "rb") as f:
                    return f.read()
            except:
                continue

        if not silent:
            print(f"Could not find file {src}")
        return None

    def read_text(self, src, silent=False):
        data = self.read_bytes(src, silent)
        if data is not None:
            return data.decode("utf-8", errors="replace")
        return None