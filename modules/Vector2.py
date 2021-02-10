from math import pow, sqrt


class Vector2:
    def __init__(self, a: float = float(0.0), b: float = float(0.0)):
        self.x = float(a)
        self.y = float(b)

    def __add__(self, rhs):
        if isinstance(rhs, self.__class__):
            return Vector2(self.x + rhs.x, self.y + rhs.y)
        else:
            return Vector2(self.x + rhs, self.y + rhs)

    def __sub__(self, rhs):
        if isinstance(rhs, self.__class__):
            return Vector2(self.x - rhs.x, self.y - rhs.y)
        else:
            return Vector2(self.x - rhs, self.y - rhs)

    def __mul__(self, rhs):
        if isinstance(rhs, self.__class__):
            return Vector2(self.x * rhs.x, self.y * rhs.y)
        else:
            return Vector2(self.x * rhs, self.y * rhs)

    def __truediv__(self, rhs):
        if isinstance(rhs, self.__class__):
            return Vector2(self.x / rhs.x, self.y / rhs.y)
        else:
            return Vector2(self.x / rhs, self.y / rhs)

    def __eq__(self, rhs):
        if isinstance(rhs, self.__class__):
            return (self - rhs).len() <= 0.01
        return False

    def __str__(self):
        return str(self.x) + " " + str(self.y)

    def dot(self, rhs):
        return (self.x * rhs.x) + (self.y * rhs.y)

    def sqrLen(self):
        return self.dot(self)

    def len(self):
        return sqrt(self.sqrLen())

    def normalize(self):
        return self / self.len()

    def distance(self, rhs):
        return sqrt(pow(self.x - rhs.x, 2) + pow(self.y - rhs.y, 2))

    def lerp(self, rhs, alpha):
        return Vector2(
            self.x + (rhs.x - self.x) * alpha,
            self.y + (rhs.y - self.y) * alpha
        )

    def flip(self):
        self.x, self.y = self.y, self.x
