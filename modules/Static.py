from .Vector3 import Vector3
from os.path import basename, splitext

# removing the characters from the middle of the file is a dirty but nice way to solve this issue.
def uniqueName(name: str):
    name = splitext(basename(name).strip())[0]
    return name[:14] + name[-14:] if len(name) > 28 else name

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
