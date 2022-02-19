from .Vector3 import Vector3
from .Side import Side
from .AABB import AABB
from math import isnan

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
    if abs(determinant) <= 1e-5 or (isnan(determinant)):
        return None
    else:
        return (
            normal2.cross(normal3) * side1.distance() +
            normal3.cross(normal1) * side2.distance() +
            normal1.cross(normal2) * side3.distance()
        ) / determinant

class Brush:
    def __init__(self, sides: list, entity: str = "world", id="0", entData={}):
        self.id = id
        self.sides: list[Side] = sides
        self.hasDisp: bool = False
        # only after all the sides are defined can the intersection points be calculated
        self.getIntersectionPoints()
        self.entity = entity
        self.entData = entData

    def getIntersectionPoints(self):
        n = len(self.sides)
        for i in range(n - 2):
            for j in range(n - 1):
                for k in range(n):
                    if i != j and i != k and j != k:
                        intersectionPoint: Vector3 = getPlaneIntersectıon(
                            self.sides[i], self.sides[j], self.sides[k]
                        )
                        if intersectionPoint is not None and intersectionPoint.isLegal(self.sides):
                            self.sides[i].points.append(intersectionPoint)
                            self.sides[j].points.append(intersectionPoint)
                            self.sides[k].points.append(intersectionPoint)

        for i in range(n):
            if len(self.sides[i].points) != 0:
                self.sides[i].sortVertices()
            if self.sides[i].hasDisp:
                self.hasDisp = True

    # get the bounding box of a brush
    def getAABB(self):
        res = AABB()

        for side in self.sides:
            for point in side.points:
                res.update(point)
        
        return res