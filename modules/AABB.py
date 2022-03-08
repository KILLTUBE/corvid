from copy import copy
from ctypes import Union
from re import A
from typing import Iterable, List
from .Vector3 import Vector3
import weakref

class AABB:
    min: Vector3
    max: Vector3
    top: Vector3
    forward: Vector3
    right: Vector3
    center: Vector3

    def __init__(self, _min: Vector3 = Vector3.Zero(), _max: Vector3 = Vector3.Zero(), generateTree=False) -> 'AABB':
        self.min = _min
        self.max = _max
        self.center = (_min + _max) * 0.5
        self.extents = _max - self.center
        
        self.children: list[AABB] = []
        self.brushes = []

        if generateTree:
            self.GenerateOctree()
    
    def update(self, new):
        self.min = self.min.min(new)
        self.max = self.max.max(new)

    @staticmethod
    def FromPoint(point: Vector3, size: int = 8) -> 'AABB':
        hs = size / 2 # half size
        _min = point + Vector3(hs, -hs, -hs)
        _max = point + Vector3(-hs, hs, hs)
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
        self.children.append(AABB(c + Vector3(e.x, 0, 0), a + Vector3(e.x, 0, 0), True))
        self.children.append(AABB(c + Vector3(0, e.y, 0), a + Vector3(0, e.y, 0), True))
        self.children.append(AABB(c + Vector3(e.x, e.y, 0), a + Vector3(e.x, e.y, 0), True))
        # bottom 4
        self.children.append(AABB(c + Vector3(0, 0, -e.z), a + Vector3(0, 0, -e.z), True))
        self.children.append(AABB(c + Vector3(e.x, 0, -e.z), a + Vector3(e.x, 0, -e.z), True))
        self.children.append(AABB(c + Vector3(0, e.y, -e.z), a + Vector3(0, e.y, -e.z), True))
        self.children.append(AABB(c + Vector3(e.x, e.y, -e.z), a + Vector3(e.x, e.y, -e.z), True))
    
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