# from .Vector3 import Vector3
from .Side import Side
from .AABB import AABB
from math import isnan
from glm import vec3, normalize, cross, dot, min, max
from itertools import combinations

def getPlaneIntersection(side1: Side, side2: Side, side3: Side) -> vec3:
    normal1: vec3 = normalize(side1.normal())
    normal2: vec3 = normalize(side2.normal())
    normal3: vec3 = normalize(side3.normal())
    determinant = dot(normal1, cross(normal2, normal3))
    # can't intersect parallel planes
    if abs(determinant) <= 1e-5 or (isnan(determinant)):
        return None
    else:
        return (
            cross(normal2, normal3) * side1.distance() +
            cross(normal3, normal1) * side2.distance() +
            cross(normal1, normal2) * side3.distance()
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
        self.isToolBrush = False
        self._box: AABB = None

    def isPointLegal(self, point: vec3)-> bool:
        for side in self.sides:
            facing = normalize((point - side.center()))
            if dot(facing, normalize(side.normal())) < -0.001:
                return False
        return True

    def getIntersectionPoints(self):
        n = len(self.sides)
        for side1, side2, side3 in combinations(self.sides, 3):
            intersectionPoint: vec3 = getPlaneIntersection(side1, side2, side3)
            if intersectionPoint is not None and self.isPointLegal(intersectionPoint):
                side1.points.append(intersectionPoint)
                side2.points.append(intersectionPoint)
                side3.points.append(intersectionPoint)

        for i in range(n):
            if len(self.sides[i].points) != 0:
                self.sides[i].sortVertices()
            if self.sides[i].hasDisp:
                self.hasDisp = True
            if not self.sides[i].material.startswith("tools"):
                self.isToolBrush = True

    # get the bounding box of a brush
    def AABB(self):
        if self._box is not None:
            return self._box

        _min = vec3(0, 0, 0)
        _max = vec3(0, 0, 0)

        for side in self.sides:
            for point in side.points:
               _min = min(_min, point)
               _max = max(_max, point)
        
        self._box = AABB(_min, _max)
        return self._box
    
    def GetDecalPoints(self, box: 'AABB'):
        # decals don't work on displacements
        if self.hasDisp:
            return None

        if not self.AABB().IsTouching(box):
            return None
        
        res: list[vec3] = []
        points: list[vec3] = []

        for side in self.sides:
            if side.IsTouching(box):
                if dot(normalize(side.normal), box.center - side.p1) < 0: # if it's behind the side, we don't need it
                    continue
                points.append(side.getClosestPoint(box.center))
        
        for point in points:
            if self.isPointLegal(point):
                res.append(point)
        
        return res
