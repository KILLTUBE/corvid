from os import replace
from .Vector3 import Vector3, Vector3FromStr
from .Side import Side
from math import pi as PI, isnan
from os.path import basename, splitext, dirname
from pathlib import Path
from base64 import b64encode
from hashlib import md5

def deg2rad(deg: float):
    return deg * (PI / 180)

def rad2deg(rad: float):
    return rad * (180 / PI)

def getPlaneIntersectıon(side1: Side, side2: Side, side3: Side) -> Vector3:
    normal1: Vector3 = side1.normal().normalize()
    normal2: Vector3 = side2.normal().normalize()
    normal3: Vector3 = side3.normal().normalize()
    determinant = (
        (
            normal1.x * normal2.y * normal3.z +
            normal1.y * normal2.z * normal3.x +
            normal1.z * normal2.x * normal3.y
        )
        -
        (
            normal1.z * normal2.y * normal3.x +
            normal1.y * normal2.x * normal3.z +
            normal1.x * normal2.z * normal3.y
        )
    )
    # can't intersect parallel planes
    if (determinant <= 0.001 and determinant >= -0.001) or (isnan(determinant)):
        return None
    else:
        return (
            normal2.cross(normal3) * side1.distance() +
            normal3.cross(normal1) * side2.distance() +
            normal1.cross(normal2) * side3.distance()
        ) / determinant

"""
some texture files have longer names than waw's limit.
in Source, it is possible for two assets to have the same name since they can be stored in subdirectories
in order to keep the file names short enough for the engines to handle and avoid duplicate assets, I had to come up with something like this
"""
def uniqueName(path: str):
    path = Path(path.strip()).as_posix().lower().strip()
    baseName = basename(path)
    basePath = dirname(path)
    hashedPath = md5(basePath.encode("utf-8")).hexdigest()
    finalName = baseName if len(baseName) < 15 else baseName[:7] + baseName[-7:]
    return f"{hashedPath[:6]}{hashedPath[-7:]}_{finalName}"

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
        line = f'"{key}" "{value}"'
        result += line + "\n" + res2
    return result;

def rgbToHex(rgb):
    rgb = Vector3FromStr(rgb)
    return "%02x%02x%02x" % (int(rgb.x), int(rgb.y), int(rgb.z))