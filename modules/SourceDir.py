import vpk
from typing import List
from os.path import isdir, isfile
from shutil import copyfile
from pathlib import Path
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
    
    def copy(self, src, dest, silent=False):
        src = Path(src).as_posix()
        for pak in self.paks:
            try:
                pak.get_file(src).save(dest)
            except:
                continue
            else:
                return True
            
        for addon in self.addons:
            if src in addon.entries:
                addon.entries[src].save(dest)
                return True

        for dir in self.dirs:
            try:
                copyfile(f"{dir}/{src}", dest)
            except:
                continue
            else:
                return True
        
        if not silent:
            print(f"Could not find file {src}")
        return False

    def open(self, src):
        src = Path(src).as_posix()
        for pak in self.paks:
            try:
                return pak.get_file(src).read()
            except:
                continue
        
        for addon in self.addons:
            if src in addon.entries:
                addon.entries[src].save()
        
        for dir in self.dirs:
            try:
                return open(f"{dir}/{src}").read()
            except:
                continue
            
        return None