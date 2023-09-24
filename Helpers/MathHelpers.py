from mathutils import Vector

def Vec2Str(vec: Vector) -> str:
    return " ".join([f"{v:.5g}" for v in vec])

def VecFromStr(vec: str) -> Vector:
    return Vector([float(v) for v in vec.split()])

def VecFromList(vec: list):
    return Vector([float(v) for v in vec])

def VecMin(v1: Vector, v2: Vector):
    return Vector((
        min(v1.x, v2.x),
        min(v1.y, v2.y),
        min(v1.z, v2.z),
    ))

def VecMax(v1: Vector, v2: Vector):
    return Vector((
        max(v1.x, v2.x),
        max(v1.y, v2.y),
        max(v1.z, v2.z),
    ))

def VecUp() -> Vector:
    return Vector((0.0, 0.0, 1.0))

def VecRight() -> Vector:
    return Vector((0.0, 1.0, 0.0))

def VecForward() -> Vector:
    return Vector((1.0, 0.0, 0.0))

def VecZero(size: int=3) -> Vector:
    return Vector([0] * size)

def Vec2Hex(vec: Vector) -> str:
    return "".join(["%02x" % i for i in vec])
