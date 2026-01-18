# from .Vector3 import Vector3
from .Side import Side
from .AABB import AABB
from math import isnan
from glm import vec3, normalize, cross, dot, min, max, length

class Brush:
    def __init__(self, sides: list, entity: str = "world", id="0", entData={}):
        self.id = id
        self.sides: list[Side] = sides
        self.hasDisp: bool = False
        # only after all the sides are defined can the intersection points be calculated
        self.rebuildGeometry()
        self.entity = entity
        self.entData = entData
        self.isToolBrush = False
        self._box: AABB = None

    def isPointInside(self, point: vec3, epsilon: float = 1e-4) -> bool:
        for side in self.sides:
            normal, dist = side.getPlane()
            if dot(point, normal) - dist < -epsilon:
                return False
        return True

    def rebuildGeometry(self):
        for side in self.sides:
            # Start with a large winding on this side's plane
            winding = side.getBaseWinding()
            
            # Clip it against every other side
            for other in self.sides:
                if side == other:
                    continue
                
                normal, dist = other.getPlane()
                winding = Side.clipWinding(winding, normal, dist)
                
                if len(winding) == 0:
                    break
            
            # Ensure unique points
            unique_points = []
            for p in winding:
                if not any(length(p - up) < 1e-3 for up in unique_points):
                    unique_points.append(p)
            side.points = unique_points
            unique_points.reverse()
            
            if side.hasDisp:
                self.hasDisp = True
            if not side.material.startswith("tools"):
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
            if self.isPointInside(point):
                res.append(point)
        
        return res
