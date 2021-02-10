from math import pi, pow, sqrt, sin, cos

class Vector3:
    def __init__(self, a: float = float(0.0), b: float = float(0.0), c: float = float(0.0)):
        self.x = float(a) + 0
        self.y = float(b) + 0
        self.z = float(c) + 0

    def __add__(self, rhs):
        if isinstance(rhs, self.__class__):
            return Vector3(self.x + rhs.x, self.y + rhs.y, self.z + rhs.z)
        else:
            return Vector3(self.x + rhs, self.y + rhs, self.z + rhs)

    def __sub__(self, rhs):
        if isinstance(rhs, self.__class__):
            return Vector3(self.x - rhs.x, self.y - rhs.y, self.z - rhs.z)
        else:
            return Vector3(self.x - rhs, self.y - rhs, self.z - rhs)

    def __mul__(self, rhs):
        if isinstance(rhs, self.__class__):
            return Vector3(self.x * rhs.x, self.y * rhs.y, self.z * rhs.z)
        else:
            return Vector3(self.x * rhs, self.y * rhs, self.z * rhs)

    def __truediv__(self, rhs):
        if isinstance(rhs, self.__class__):
            return Vector3(self.x / rhs.x, self.y / rhs.y, self.z / rhs.z)
        else:
            return Vector3(self.x / rhs, self.y / rhs, self.z / rhs)

    def __eq__(self, rhs):
        if isinstance(rhs, self.__class__):
            return (self - rhs).len() <= 0.01
        return False

    def __str__(self):
        return f"{self.x} {self.y} {self.z}"

    def abs(self):
        return Vector3(abs(self.x), abs(self.y), abs(self.z))

    def dot(self, rhs):
        return (self.x * rhs.x) + (self.y * rhs.y) + (self.z * rhs.z)

    def sqrLen(self):
        return self.dot(self)

    def len(self):
        return sqrt(self.sqrLen())

    def normalize(self):
        return self / self.len()

    def cross(self, rhs):
        return Vector3(
            self.y * rhs.z - self.z * rhs.y,
            self.z * rhs.x - self.x * rhs.z,
            self.x * rhs.y - self.y * rhs.x
        )

    def distance(self, rhs):
        return sqrt(pow(self.x - rhs.x, 2) + pow(self.y - rhs.y, 2) + pow(self.z - rhs.z, 2))

    def lerp(self, rhs, alpha):
        return Vector3(
            self.x + ((rhs.x - self.x) * alpha),
            self.y + ((rhs.y - self.y) * alpha),
            self.z + ((rhs.z - self.z) * alpha)
        )

    def round(self):
        return Vector3(
            round(self.x), round(self.y), round(self.z)
        )

    def isLegal(self, sides):
        for side in sides:
            facing = (self - side.center()).normalize()
            if facing.dot(side.normal().normalize()) < -0.01:
                return False
        return True


