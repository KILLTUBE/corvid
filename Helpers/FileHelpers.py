from pathlib import Path
from os import makedirs
from os.path import basename, splitext, dirname
from hashlib import shake_256
from shutil import rmtree
from tempfile import gettempdir

# cod 4 and waw don't like images when their names contain more than 42 charcters including the extension
# so we need to make sure they won't cause any problems while being converted
def ShortenName(name: str, length=13) -> str:
    name = splitext(basename(name).strip())[0]
    return name[:length] + name[-length:] if len(name) > (length * 2) else name

# unlike in cod, you can store your assets in subfolders in source
# however, this means there can be assets that have the same name in different folders
# if a map has any assets that have the same name, one of them will override the others
# we can solve this issue by hashing the path to each file and adding that hash to the beggining of each asset's name
def ShortenPath(path: str, dig=4):
    return shake_256(path.encode()).hexdigest(dig)

# we can use the two functions above to avoid name classes in assets
def NewPath(path: str, shorten=False, prefix="") -> str:
    path = f"{prefix}/" + Path(path).as_posix().strip().lower().replace("{", "_").replace("}", "_").replace("(", "_").replace(")", "_").replace(" ", "_")
    fileName = basename(path)
    if shorten:
        fileName = ShortenName(fileName)
    dirName = dirname(path)
    return f"{ShortenPath(dirName)}_{fileName}"


# flatten an n dimensional list
def Flatten(lst: list) -> list:
    res: list = []
    for i in lst:
        if isinstance(i, list):
            res += Flatten(i)
        else:
            res.append(i)
    return res

def GetTempDir():
    return Path(gettempdir()).as_posix() + "/Corvid"

def CreateTempDirs():
    tmpDir = gettempdir() + "/Corvid"
    makedirs(f"{tmpDir}/temp", exist_ok=True)
    makedirs(f"{tmpDir}/materials", exist_ok=True)
    makedirs(f"{tmpDir}/textures", exist_ok=True)
    makedirs(f"{tmpDir}/models", exist_ok=True)

def CleanTempDirs():
    rmtree(GetTempDir(), True)

def ReadFile(path: str):
    file = open(path, "r")
    res = file.read()
    file.close()
    return res

def WriteFile(path: str, content: str):
    with open(path, "w") as file:
        file.truncate()
        file.write(content)