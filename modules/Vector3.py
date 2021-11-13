from math import cos, pi, pow, sin, sqrt
from mathutils import Vector

class Vector3:

    def __init__(self, a: float = float(0.0), b: float = float(0.0), c: float = float(0.0)):
        self.x = float(a) + 0
        self.y = float(b) + 0
        self.z = float(c) + 0

    def __add__(self, rhs) -> 'Vector3':
        if isinstance(rhs, self.__class__):
            return Vector3(self.x + rhs.x, self.y + rhs.y, self.z + rhs.z)
        else:
            return Vector3(self.x + rhs, self.y + rhs, self.z + rhs)

    def __sub__(self, rhs) -> 'Vector3':
        if isinstance(rhs, self.__class__):
            return Vector3(self.x - rhs.x, self.y - rhs.y, self.z - rhs.z)
        else:
            return Vector3(self.x - rhs, self.y - rhs, self.z - rhs)

    def __mul__(self, rhs) -> 'Vector3':
        if isinstance(rhs, self.__class__):
            return Vector3(self.x * rhs.x, self.y * rhs.y, self.z * rhs.z)
        else:
            return Vector3(self.x * rhs, self.y * rhs, self.z * rhs)

    def __truediv__(self, rhs) -> 'Vector3':
        if isinstance(rhs, self.__class__):
            return Vector3(self.x / rhs.x, self.y / rhs.y, self.z / rhs.z)
        else:
            return Vector3(self.x / rhs, self.y / rhs, self.z / rhs)

    def __eq__(self, rhs) -> bool:
        if isinstance(rhs, self.__class__):
            return (self - rhs).len() <= 0.01
        return False

    def __pow__(self, p) -> float:
        return Vector3(self.x ** p, self.y ** p, self.z ** p)

    def __str__(self):
        return f"{self.x:.5g} {self.y:.5g} {self.z:.5g}"
    
    def __repr__(self):
        return f"<Vector3 {self.x} {self.y} {self.z}>"

    def abs(self) -> 'Vector3':
        return Vector3(abs(self.x), abs(self.y), abs(self.z))

    def dot(self, rhs) -> float:
        return (self.x * rhs.x) + (self.y * rhs.y) + (self.z * rhs.z)

    def sqrLen(self) -> float:
        return self.dot(self)

    def len(self) -> float:
        return sqrt(self.sqrLen())

    def normalize(self) -> 'Vector3':
        return self / self.len()

    def cross(self, rhs) -> 'Vector3':
        return Vector3(
            self.y * rhs.z - self.z * rhs.y,
            self.z * rhs.x - self.x * rhs.z,
            self.x * rhs.y - self.y * rhs.x
        )

    def distance(self, rhs) -> float:
        return sqrt(pow(self.x - rhs.x, 2) + pow(self.y - rhs.y, 2) + pow(self.z - rhs.z, 2))

    def lerp(self, rhs, alpha) -> 'Vector3':
        return Vector3(
            self.x + ((rhs.x - self.x) * alpha),
            self.y + ((rhs.y - self.y) * alpha),
            self.z + ((rhs.z - self.z) * alpha)
        )

    def round(self, digits=0) -> 'Vector3':
        return Vector3(
            round(self.x, digits), round(self.y, digits), round(self.z, digits)
        )

    def isLegal(self, sides)-> bool:
        for side in sides:
            facing = (self - side.center()).normalize()
            if facing.dot(side.normal().normalize()) < -0.001:
                return False
        return True

    def rotateX(self, rad) -> 'Vector3':
        Cos = cos(rad)
        Sin = sin(rad)
        return Vector3(self.x, self.y * Cos - self.z * Sin, self.z * Cos + self.y * Sin)
    
    def rotateY(self, rad) -> 'Vector3':
        Cos = cos(rad)
        Sin = sin(rad)
        return Vector3(self.x * Cos - self.z * Sin, self.y, self.z * Cos + self.x * Sin)

    def rotateZ(self, rad) -> 'Vector3':
        Cos = cos(rad)
        Sin = sin(rad)
        return Vector3(self.x * Cos - self.y * Sin, self.y * Cos + self.x * Sin, self.z)

    def rotate(self, rot: 'Vector3') -> 'Vector3':
        return self.rotateX(rot.x).rotateY(rot.y).rotateZ(rot.z)

    def min(self, value) -> 'Vector3':
        return Vector3(min(self.x, value), min(self.y, value), min(self.z, value))

    def max(self, value) -> 'Vector3':
        return Vector3(max(self.x, value), max(self.y, value), max(self.z, value))

    def ToBpy(self):
        return Vector((self.x, self.y, self.z))

    @staticmethod
    def Zero() -> 'Vector3':
        return Vector3(0.0, 0.0, 0.0)

    @staticmethod
    def FromStr(string: str):
        string = string.replace("[","").replace("]","").replace("{","").replace("}","").strip()
        tok = string.split(" ")
        return Vector3(tok[0], tok[1], tok[2])
    
    @staticmethod
    def FromArray(arr):
        return Vector3(arr[0], arr[1], arr[2])
