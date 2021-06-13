from mathutils import Vector
from os.path import basename, splitext

def Vector3FromStr(s: str):
    s = s.replace("[","").replace("]","").replace("{","").replace("}","").strip()
    tok = s.split(" ")
    return Vector((float(tok[0]), float(tok[1]), float(tok[2])))

def Vector2Str(vec: Vector):
    return ' '.join([f'{v:.5g}' for v in vec])

# some texture files have longer names than waw's limit.
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
            line = f'"{key}" "{value}"'
        result += line + "\n" + res2
    return result;

def rgbToHex(rgb):
    rgb = Vector3FromStr(rgb)
    return "%02x%02x%02x" % (int(rgb.x), int(rgb.y), int(rgb.z))