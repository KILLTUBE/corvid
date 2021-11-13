from .Vector3 import Vector3
from os.path import basename, splitext
from hashlib import shake_256

# cod 4 and waw don't like images when their names contain more than 42 charcters including the extension
# so we need to make sure they won't cause any problems while being converted
def uniqueName(name: str, length=15):
    name = splitext(basename(name).strip())[0]
    return name[:length] + name[-length:] if len(name) > (length * 2) else name

def shortenPath(path: str, dig=4):
    return shake_256(path.encode()).hexdigest(dig)

# some vmt files are written so badly, we have to fix them make sure they will be parsed correctly
def fixVmt(vmt: str):
    result = ""
    lines = vmt.replace("\t", " ").replace("\\", "/").replace(".vtf", "").split("\n")
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
                line = f'"{key}" "{value}"'
        result += line + "\n" + res2
    return result
