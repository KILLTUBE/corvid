import vpk
from os.path import isdir, isfile, basename
from shutil import copyfile
from pathlib import Path
class SourceDir:
    def __init__(self):
        self.dirs = []
        self.paks = [vpk.VPK]

    def add(self, path):
        if isfile(path):
            if not path.endswith(".vpk"):
                print(f"\"{path}\" is not a valid file.")
                exit()
            self.paks.append(vpk.open(path))
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