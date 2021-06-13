from math import isnan
from mathutils import Vector
from .Side import Side

def isLegal(point, sides):
    for side in sides:
        facing = (point - side.center()).normalized()
        if facing.dot(side.normal().normalized()) < -0.001:
            return False
    return True

def getPlaneIntersection(side1: Side, side2: Side, side3: Side) -> Vector:
    normal1: Vector = side1.normal().normalized()
    normal2: Vector = side2.normal().normalized()
    normal3: Vector = side3.normal().normalized()

    determinant = normal1.dot(normal2.cross(normal3))

    if (determinant <= 0.001 and determinant >= -0.001) or (isnan(determinant)):
        return None
    else:
        return (
            normal2.cross(normal3) * side1.distance() +
            normal3.cross(normal1) * side2.distance() +
            normal1.cross(normal2) * side3.distance()
        ) / determinant

class Brush:
    def __init__(self, sides: list, entity: str = "world", id="0"):
        self.id = id
        self.sides: list[Side] = sides
        self.hasDisp: bool = False
        # only after all the sides are defined can the intersection points be calculated
        self.getIntersectionPoints()
        self.entity = entity

    def getIntersectionPoints(self):
        n = len(self.sides)
        for i in range(n - 2):
            for j in range(n - 1):
                for k in range(n):
                    if i != j and i != k and j != k:
                        intersectionPoint: Vector = getPlaneIntersection(
                            self.sides[i], self.sides[j], self.sides[k]
                        )
                        if intersectionPoint is not None and isLegal(intersectionPoint, self.sides):
                            self.sides[i].points.append(intersectionPoint)
                            self.sides[j].points.append(intersectionPoint)
                            self.sides[k].points.append(intersectionPoint)

        for i in range(n):
            if len(self.sides[i].points) != 0:
                self.sides[i].sortVertices()
            if self.sides[i].hasDisp:
                self.hasDisp = True
