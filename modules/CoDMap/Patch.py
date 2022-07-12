from ..Vector3 import Vector3
from ..Vector2 import Vector2
import numpy as np
from math import ceil
from typing import List, Tuple, Union

def Color2Str(c: Tuple[int, int, int, int]):
    return "%i %i %i %i" % c

class PatchVert:
    pos: Vector3
    color: Tuple[int, int, int, int]
    uv: Vector2
    lm: Vector2
    nolightmap: bool

    def __init__(self, pos, uv, lm, color=None) -> None:
        self.pos = pos
        self.color = color
        self.uv = uv
        self.lm = lm
        self.nolightmap = False
    
    def __str__(self) -> str:
        if self.nolightmap:
            if self.color == None:
                return f"v {self.pos} t {self.uv}"
            return f"v {self.pos} c {self.color} t {self.uv}"
        elif self.color == None:
            return f"v {self.pos} t {self.uv} {self.lm}"
        return f"v {self.pos} c {Color2Str(self.color)} t {self.uv} {self.lm}"

class Patch:
    type: str
    toolflags: List[str]
    contents: List[str]
    texture: str
    lightmap: str
    size: Tuple[int, int]
    samplesize: int
    verts: List[List[PatchVert]]
    layer: str
    smoothing: str
    filters: dict
    blend: bool
    nolightmap: bool

    def __init__(self,
        type="mesh", toolflags=[], contents=[], texture="case", lightmap="lightmap_gray", size=None, samplesize=16,
        smoothing=None, layer=None
    ) -> None:
        self.type = type
        self.toolflags = toolflags
        self.contents = contents
        self.texture = texture
        self.lightmap = lightmap
        self.samplesize = samplesize if samplesize != 0 else 16
        self.size = size
        self.verts = []
        self.layer = None
        self.smoothing = smoothing
        self.blend = False
        self.nolightmap = False

    def Slice(self, maxsize=30) -> List['Patch']:
        if self.size[0] <= maxsize and self.size[1] <= maxsize:
            return [self]

        res: List['Patch'] = []

        # create a 2d numpy array of vertices
        arr: np.ndarray = np.array(self.verts)

        # slice the 2d array into smaller 2d arrays
        numvert = ceil((len(arr) - 1) / (maxsize - 1))
        numhorz = ceil((len(arr[0]) - 1) / (maxsize - 1))

        for i in range(numvert):
            for j in range(numhorz):
                startvert = i * (maxsize - 1)
                endvert = (i + 1) * (maxsize - 1) + 1
                starthorz = j * (maxsize - 1)
                endhorz = (j + 1) * (maxsize - 1) + 1

                if endvert > len(arr):
                    endvert = len(arr)
                if endhorz > len(arr[0]):
                    endhorz = len(arr[0])
                
                newarr = arr[startvert:endvert, starthorz:endhorz].tolist()
                newpatch = Patch(
                    self.type, self.toolflags, self.contents, self.texture, self.lightmap,
                    (len(newarr), len(newarr[0])), self.samplesize, self.smoothing, self.layer
                )
                newpatch.verts = newarr
                res.append(newpatch)
        
        return res
    
    def Triangulate(self):
        tris: List[Tuple[PatchVert, PatchVert, PatchVert]] = []

        for i in range(self.size[0] - 1):
            for k in range(self.size[1]):
                if k != self.size[1] - 1: # first vert in the row
                    tris.append((self.verts[i + 1][k], self.verts[i][k + 1], self.verts[i][k]))
                if k != 0: # last vert in the row
                    tris.append((self.verts[i + 1][k - 1], self.verts[i + 1][k], self.verts[i][k]))

        return tris

    def __str__(self) -> str:            
        res = (
            "{\n"
            + self.type + "\n"
            + "{\n"
            + (f"contents {' '.join([content for content in self.contents])};\n" if len(self.contents) != 0 else "")
            + (f"toolFlags {' '.join([flag for flag in self.toolflags])};\n" if len(self.toolflags) != 0 else "")
            + self.texture + "\n"
            + self.lightmap + "\n"
            + (f"smoothing {self.smoothing}\n" if self.smoothing is not None else "")
            + f"{self.size[0]} {self.size[1]} {self.samplesize} 8\n"
        )

        for row in self.verts:
            res += "(\n"

            for vert in row:
                vert.nolightmap = self.nolightmap
                res += str(vert) + "\n"

            res += ")\n"

        res += "}\n"
        res += "}\n"
        return res
