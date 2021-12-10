from pathlib import Path
from os.path import basename, splitext, dirname
from hashlib import shake_256

# cod 4 and waw don't like images when their names contain more than 42 charcters including the extension
# so we need to make sure they won't cause any problems while being converted
def shortenName(name: str, length=13):
    name = splitext(basename(name).strip())[0]
    return name[:length] + name[-length:] if len(name) > (length * 2) else name

# unlike in cod, you can store your assets in subfolders in source
# however, this means there can be assets that have the same name in different folders
# if a map has any assets that have the same name, one of them will override the others
# we can solve this issue by hashing the path to each file and adding that hash to the beggining of each asset's name
def shortenPath(path: str, dig=4):
    return shake_256(path.encode()).hexdigest(dig)

# we can use the two functions above to avoid name classes in assets
def newPath(path: str, shorten=False, prefix=""):
    path = f"{prefix}/" + Path(path).as_posix().strip().lower().replace("{", "_").replace("}", "_").replace("(", "_").replace(")", "_").replace(" ", "_")
    fileName = basename(path)
    if shorten:
        fileName = shortenName(fileName)
    dirName = dirname(path)
    return f"{shortenPath(dirName)}_{fileName}"

# some vmt files are written so badly, we have to fix them make sure they will be parsed correctly
def fixVmt(vmt: str):
    result = ""
    lines = vmt.replace("\t", " ").replace('""\n','"[emptyplaceholder]"\n').replace("\\", "/").replace(".vtf", "").replace(".tga", "").split("\n")
    for line in lines:
        res2 = ""
        line = line.replace('"', " ").strip().lower()
        if line.startswith("{") and line != "{":
            line = line[1:]
            result += "{\n"
        if line.endswith("}") and line != "}" and "{" not in line:
            line = line[:-1]
            res2 = "}\n"
        if len(line) == 0 or line.startswith("/"):
            continue
        line = " ".join(line.split())
        tok = line.split()
        if len(tok) == 1:
            result += line + "\n"
            continue
        key = tok[0]
        value = " ".join(tok[1:])
        if value == "{":
            line = key + "\n{"
        else:
            if "//" in value:
                value = value.split("//")
                line = f'"{key}" "{value[0].strip()}" // {value[1]}'
            else:
                value = value.replace(".vtf", "").replace(".tga", "")
                if value == "[emptyplaceholder]":
                    value = ""
                line = f'"{key}" "{value}"'
        result += line + "\n" + res2
    return result
