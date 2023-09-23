import numpy as np
from math import ceil
from typing import List, Tuple, Union
from mathutils import Vector

class PatchVert:
    __slots__ = ("pos", "uv")
    pos: Vector
    uv: Vector

    def __init__(self, pos: Vector, uv: Vector) -> None:
        self.pos, self.uv = pos, uv

    def __add__(self, rhs: 'PatchVert') -> 'PatchVert':
        return PatchVert(
            self.pos + rhs.pos,
            self.uv + rhs.uv
        )

    def __mul__(self, rhs: Union['PatchVert', float]) -> 'PatchVert':
        if isinstance(rhs, PatchVert):
            return PatchVert(
                self.pos * rhs.pos,
                self.uv * rhs.uv
            )
        else:
            return PatchVert(
                self.pos * rhs,
                self.uv * rhs
            )

    @staticmethod
    def FromStr(row: str):
        raise NotImplementedError()

class Patch:
    __slots__ = ("size", "material", "verts")
    size: Tuple[int, int]
    material: str
    verts: List[List[PatchVert]]

    def __init__(self, size: Tuple[int, int], material: str) -> None:
        self.size = size
        self.material = material
        self.verts = []

    def Slice(self, maxSize: int=16) -> List['Patch']:
        if self.size[0] <= maxSize and self.size[1] <= maxSize:
            return [self]
        
        res: List['Patch'] = []

        # create a 2d numpy array of vertices
        arr: np.ndarray = np.array(self.verts)

        # slice the 2d array into smaller 2d arrays
        numvert = ceil((len(arr) - 1) / (maxSize - 1))
        numhorz = ceil((len(arr[0]) - 1) / (maxSize - 1))

        for i in range(numvert):
            for j in range(numhorz):
                startvert = i * (maxSize - 1)
                endvert = (i + 1) * (maxSize - 1) + 1
                starthorz = j * (maxSize - 1)
                endhorz = (j + 1) * (maxSize - 1) + 1

                if endvert > len(arr):
                    endvert = len(arr)
                if endhorz > len(arr[0]):
                    endhorz = len(arr[0])
                
                newarr = arr[startvert:endvert, starthorz:endhorz].tolist()

                newPatch = Patch((len(newarr), len(newarr[0])), self.material)
                newPatch.verts = newarr
                res.append(newPatch)

        return res

