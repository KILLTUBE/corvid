from os import mkdir
from random import randint
from tempfile import gettempdir
import vpk
from os.path import isdir, isfile, exists
from shutil import copyfile
from sys import exit
from pathlib import Path
from typing import List, Union
from Helpers.FileHelpers import GetTempDir, NewPath
from .Gma import Addon

class SourceDir:
    """
    A class written in order to make it easier to read and copy files from a Source game's paks and directories.
    """
    __slot__ = ("dirs", "paks", "addons")

    dirs: List[str]
    paks: List[vpk.VPK]
    addons: List[Addon]

    def __init__(self) -> None:
        self.dirs = []
        self.paks = []
        self.addons = []
    
    def AddDir(self, path: str) -> None:
        if not isdir(path):
            print(f"Warning! \"{path}\" is not a valid directory.")
            return
        self.dirs.append(path)

    def AddPak(self, path: str) -> None:
        if not isfile(path) or not path.lower().endswith(".vpk"):
            print(f"Warning! \"{path}\" is not a valid VPK file.")
        self.paks.append(vpk.open(path))

    def AddAddon(self, path: str) -> None:
        if not isfile(path) or not path.lower().endswith(".gma"):
            print(f"Warning! \"{path}\" is not a valid GMA file.")
        self.paks.append(Addon(path))

    def Add(self, path: str) -> None:
        if isdir(path):
            self.AddDir(path)
        elif path.lower().endswith(".vpk"):
            self.AddPak(path)
        elif path.lower().endswith(".gma"):
            self.AddAddon(path)

    def Copy(self, src: str, dest: str, silent=False):
        # first look at paks, addons then dirs
        src = Path(src.lower()).as_posix()
        dest = Path(dest.lower()).as_posix()

        for pak in self.paks:
            try: pak.get_file(src).save(dest)
            except: continue
            else: return True

        for addon in self.addons:
            try: addon.entries[src].save(dest)
            except: continue
            else: return True

        for dir in self.dirs:
            if exists(src):
                copyfile(f"{dir}/{src}", dest)
                return True
            else:
                return False

        if not silent:
            print(f"Could not find \"{src}\" in game files.")

        return False

    def Open(self, src) -> Union[str, None]:
        tempDir = GetTempDir()
        filePath = tempDir + "/temp/" + NewPath(src)
        
        if self.Copy(src, filePath):
            file = open(filePath)
            res = file.read()
            file.close()
            return res

        return None
