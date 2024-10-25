from typing import List
# from .Vector3 import Vector3
from glm import vec3, min, max

class AABB:
    min: vec3
    max: vec3
    top: vec3
    forward: vec3
    right: vec3
    center: vec3

    def __init__(self, _min: vec3 = vec3(0, 0, 0), _max: vec3 = vec3(0, 0, 0), generateTree=False) -> 'AABB':
        self.min = _min
        self.max = _max
        self.center = (_min + _max) * 0.5
        self.extents = _max - self.center
        
        self.children: List[AABB] = []
        self.brushes = []

        if generateTree:
            self.GenerateOctree()
    
    def update(self, new):
        self.min = min(self.min, new)
        self.max = max(self.min, new)
    
    def setMin(self, min: vec3):
        self.min = min

    def setMax(self, max: vec3):
        self.max = max

    @staticmethod
    def FromPoint(point: vec3, size: int = 8) -> 'AABB':
        hs = size / 2 # half size
        _min = point + vec3(hs, -hs, -hs)
        _max = point + vec3(-hs, hs, hs)
        return AABB(_min, _max)
    
    # check if it collides with another AABB
    def IsTouching(self, box: 'AABB') -> bool:
        return (
            (self.min.x <= box.max.x and self.max.x >= box.min.x) and
            (self.min.x <= box.max.y and self.max.y >= box.min.y) and
            (self.min.x <= box.max.z and self.max.z >= box.min.z)
        )
    
    def GenerateOctree(self):
        # if the AABB is small enough, don't create children
        # 128**3 = 2097152, 64**3 = 262144, 32**3 = 32768
        if self.extents.x * self.extents.y * self.extents.z < 512:
            self.children = None
            return
        
        a, c, e = self.max, self.center, self.extents
        
        # top 4
        self.children.append(AABB(c, a, True))
        self.children.append(AABB(c + vec3(e.x, 0, 0), a + vec3(e.x, 0, 0), True))
        self.children.append(AABB(c + vec3(0, e.y, 0), a + vec3(0, e.y, 0), True))
        self.children.append(AABB(c + vec3(e.x, e.y, 0), a + vec3(e.x, e.y, 0), True))
        # bottom 4
        self.children.append(AABB(c + vec3(0, 0, -e.z), a + vec3(0, 0, -e.z), True))
        self.children.append(AABB(c + vec3(e.x, 0, -e.z), a + vec3(e.x, 0, -e.z), True))
        self.children.append(AABB(c + vec3(0, e.y, -e.z), a + vec3(0, e.y, -e.z), True))
        self.children.append(AABB(c + vec3(e.x, e.y, -e.z), a + vec3(e.x, e.y, -e.z), True))
    
    def GetTouchingFaces(self, box: 'AABB'):
        res = []

        for child in box.children:
            if child.children is not None:
                self.GetTouchingFaces(child)
            else:
                for brush in child.brushes:
                    if self.IsTouching(brush.AABB()):
                        res.append()

    def __repr__(self) -> str:
        return f"<AABB center: {self.center}, min: {self.min}, max: {self.max}, extents: {self.extents}, children: {len(self.children) if self.children is not None else 0}>"

def GetBrushes(arr: 'AABB', brushes: list):
    if arr.children is not None:
        for child in arr.children:
            GetBrushes(child, brushes)
    else:
        for brush in arr.brushes:
            brushes.append(brush)
