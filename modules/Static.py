from .Vector3 import Vector3
from .Side import Side
from math import pi as PI, isnan
from os.path import basename, splitext
import re

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

# some texture files have longer names than waw's limit.
# removing the characters from the middle of the file is a dirty but nice way to solve this issue.
def uniqueName(name: str):
    name = splitext(basename(name).strip())[0]
    return name[:14] + name[-14:] if len(name) > 28 else name

# some vmt files are written so badly, we have to fix them make sure they will be parsed correctly
def fixVmt(vmt: str):
    result = "";
    lines = vmt.replace("\t", " ").replace("\\", "/").replace(".vtf", "").split("\n");
    for line in lines:
        line = line.replace('"', " ").strip().lower()
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
        result += line + "\n"
    return result;