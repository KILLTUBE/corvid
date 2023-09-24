from math import cos, fabs, radians, sin, sqrt, pow
from typing import List, Tuple, Union
from functools import cmp_to_key
from mathutils import Vector
from Helpers.MathHelpers import VecUp, VecRight, VecForward, VecZero
from Formats.Common.StandardUV import StandardUV 
from Formats.Common.ValveUV import ValveUV 
from Formats.Common.CoDUV import CoDUV 

class Face:
    """
    Base class that has all the properties and methods used by a brush face.
    """

    __slots__ = (
        "p1", "p2", "p3", "material", "uvData", "texSize", "vert_idx", "uv_idx", "parent",
        "__center__", "__normal__", "__distance__"
    )

    p1: Vector
    p2: Vector
    p3: Vector
    material: str
    uvData: StandardUV | ValveUV | CoDUV
    texSize: Vector
    vert_idx: List[int]
    uv_idx: List[int]
    parent: 'Brush'

    __center__: Vector
    __normal__: Vector
    __distance__: float

    def __init__(self) -> None:
        self.__center__, self.__normal__, self.__distance__ = None, None, None
        self.vert_idx = []
        self.uv_idx = []
        self.texSize = Vector((512, 512))

    def AddVert(self, vert: Vector) -> None:
        """
        Adds a vertex to `vert_idx`. The value will be added to the list if it is not a duplicate.
        """

        idx = self.parent.verts.index(vert)
        
        if idx not in self.vert_idx:
            self.vert_idx.append(idx)
    
    def AddUV(self, uv: Vector) -> None:
        """
        Adds a vertex to `uv_idx`. The value will be added to the list if it is not a duplicate.
        """

        self.parent.AddUV(uv)
        idx = self.parent.uvs.index(uv)
        
        self.uv_idx.append(idx)

    def GetVerts(self) -> List['Vector']:
        """
        Returns a list of `Vector` objects referencing the vertices of the brush face.
        """
        return [self.parent.verts[i] for i in self.vert_idx]

    def GetUVs(self) -> List['Vector']:
        """
        Returns a list of `Vector` objects referencing the vertices of the brush face.
        """
        return [self.parent.uvs[i] for i in self.uv_idx]

    def GetNormal(self) -> Vector:
        """
        Calculates the direction where the brush face is facing.
        """

        if self.__normal__ is not None:
            return self.__normal__
        
        ab: Vector = self.p2 - self.p1
        ac: Vector = self.p3 - self.p1
        self.__normal__ = ab.cross(ac).normalized()
        return self.__normal__

    def GetCenter(self) -> Vector:
        """
        Calculates the center of the brush face.
        """
        
        if self.__center__ is not None:
            return self.__center__

        res = VecZero()

        for vert in self.vert_idx:
            res += self.parent.verts[vert]
        
        res /= len(self.vert_idx)
        self.__center__ = res
        return res
    
    def GetDistance(self) -> float:
        normal: Vector = self.GetNormal()
        return ((self.p1.x * normal.x) + (self.p1.y * normal.y) + (self.p1.z * normal.z)) / sqrt(pow(normal.x, 2) + pow(normal.y, 2) + pow(normal.z, 2))
    
    def SortVertices(self) -> None:
        """
        Sorts vertices clockwise.
        """

        if len(self.vert_idx) == 0:
            return

        center: Vector = self.GetCenter()
        normal: Vector = self.GetNormal()

        def compare(_a: int, _b: int):
            a = self.parent.verts[_a]
            b = self.parent.verts[_b]
            ca: Vector = center - a
            cb: Vector = center - b
            caXcb: Vector = ca.cross(cb)
            if normal.dot(caXcb) > 0:
                return 1
            return -1
        
        self.vert_idx.sort(key=cmp_to_key(compare))

    def CalculateUVs(self) -> None:
        normal = self.GetNormal()

        for idx in self.vert_idx:
            self.AddUV(self.uvData.GetUV(self.parent.verts[idx], normal, self.texSize))

    def Triangulate(self, return_idx=False) -> List[Tuple[Vector, Vector]]:
        verts = self.vert_idx if return_idx else self.GetVerts()
        uvs = self.uv_idx if return_idx else self.GetUVs()

        res: List[Tuple[Tuple[Vector, Vector], Tuple[Vector, Vector], Tuple[Vector, Vector]]] = []
        numVerts = len(verts)

        res.append((
            (verts[0], uvs[0]),
            (verts[numVerts - 1], uvs[numVerts - 1]),
            (verts[1], uvs[1])
        ))

        for i in range(int(numVerts / 2)):
            res.append((
                (verts[i], uvs[i]),
                (verts[numVerts - i], uvs[numVerts - i]),
                (verts[i + 1], uvs[i + 1])
            ))

            res.append((
                (verts[numVerts - i], uvs[numVerts - i]),
                (verts[numVerts - i - 1], uvs[numVerts - i - 1]),
                (verts[i + 1], uvs[i + 1])
            ))

        return res

    @staticmethod
    def FromPoints(p1: Vector, p2: Vector, p3: Vector):
        """
        Returns a `Face` object using the points given.

        Apart from the plane points, all the other properties are set to `None`. 
        """

        res = Face()
        res.p1, res.p2, res.p3 = p1, p2, p3
        res.material = res.uvData = None
        return res
        
from .Brush import Brush
