from .Vector3 import Vector3
from .Side import Side
from .Static import getPlaneIntersectıon


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
                        intersectionPoint: Vector3 = getPlaneIntersectıon(
                            self.sides[i], self.sides[j], self.sides[k]
                        )
                        if intersectionPoint is not None and intersectionPoint.isLegal(self.sides):
                            self.sides[i].points.append(intersectionPoint)
                            self.sides[j].points.append(intersectionPoint)
                            self.sides[k].points.append(intersectionPoint)

        for i in range(n):
            if len(self.sides[i].points) == 0:
                print(f"Brush face {self.sides[i].id} has no points. Skipping...")
                continue
            self.sides[i].sortVertices()
            if self.sides[i].hasDisp:
                self.hasDisp = True
