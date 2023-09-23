import numpy as np
from io import TextIOWrapper
from typing import List, Tuple, Union
from mathutils import Vector
from Formats.BaseMap.Patch import PatchVert as BaseVert, Patch as BasePatch
from Helpers.MathHelpers import VecFromList, Vec2Str, VecZero

def Color2Str(c: Tuple[int, int, int, int]):
    return "%i %i %i %i" % c

class PatchVert(BaseVert):
    __slots__ = ("color", "lm", "noLightmap")
    color: Tuple[int, int, int, int]
    lm: Vector
    noLightmap: bool

    def __init__(self, pos, uv, lm=None, color=None) -> None:
        self.pos = pos
        self.color = color
        self.uv = uv
        self.lm = lm
        self.noLightmap = lm is None

    def __str__(self) -> str:
        if self.noLightmap:
            if self.color == None:
                return f"v {Vec2Str(self.pos)} t {Vec2Str(self.uv)}"
            return f"v {Vec2Str(self.pos)} c {self.color} t {Vec2Str(self.uv)}"
        elif self.color == None:
            return f"v {Vec2Str(self.pos)} t {Vec2Str(self.uv)} {Vec2Str(self.lm)}"
        return f"v {Vec2Str(self.pos)} c {Color2Str(self.color)} t {Vec2Str(self.uv)} {Vec2Str(self.lm)}"

    def Save(self, file: TextIOWrapper):
        file.write(str(self) + "\n")

    @staticmethod
    def FromStr(row: str) -> 'PatchVert':
        tok = row.split()
        pos = color = uv = lm = None

        for i, t in enumerate(tok):
            if t == "v":
                pos = VecFromList(tok[i + 1:i + 4])

            elif t == "c":
                color = tuple(float(c) for c in tok[i + 1:i + 5])

            elif t == "t":
                uv = VecFromList(tok[i + 1:i + 3])
                lm = VecFromList(tok[i + 3:i + 5])

        return PatchVert(pos, uv, lm, color)

class Patch(BasePatch):
    __slots__ = ("type", "toolFlags", "contents", "sampleSize", "layer", "smoothing", "noLightmap")
    verts: List[List[PatchVert]]
    type: str
    toolFlags: List[str]
    contents: List[str]
    sampleSize: int
    layer: str
    smoothing: str
    noLightmap: bool

    def __init__(self) -> None:
        pass

    def __init__(self,
        type="mesh", toolFlags: List[str]=[], contents: List[str]=[], material: str="case", size: Tuple[int, int]=None, sampleSize=16,
        smoothing=None, layer=None, verts=None
    ) -> None:
        super().__init__(size, material)

        if verts is not None:
            self.verts = verts

        self.type = type
        self.toolFlags = toolFlags
        self.contents = contents
        self.sampleSize = sampleSize if sampleSize != 0 else 16
        self.layer = layer
        self.smoothing = smoothing
        self.noLightmap = False

    def Triangulate(self) -> Tuple[List[Vector], List[Vector], List[Vector], List[Tuple[int, int, int]]]:
        GetNormal = lambda p1, p2, p3: (p2 - p1).cross(p3 - p1).normalized() # get the normal of a triangle
        width, height = len(self.verts), len(self.verts[0])
        verts: List[Vector] = []
        uvs: List[Vector] = []
        normals: List[Vector] = [VecZero()] * width * height
        tris: List[Tuple[int, int, int]] = []

        for row in self.verts:
            for vert in row:
                verts.append(vert.pos)
                uvs.append(Vector((vert.uv.x, -vert.uv.y)) * 0.0009765625) # 1 / 1024

        for i in range(width - 1):
            for k in range(height):
                if k != height - 1: # first vert in the row
                    p1, p2, p3 = (i + 1) * width + k, i * width + k + 1, i * width + k
                    normal: Vector = GetNormal(verts[p1], verts[p2], verts[p3])
                    normals[p1] += normal
                    normals[p2] += normal
                    normals[p3] += normal
                    tris.append((p1, p2, p3))

                if k != 0: # last vert in the row
                    p1, p2, p3 = (i + 1) * width + k - 1, (i + 1) * width + k, i * width + k
                    normal: Vector = GetNormal(verts[p1], verts[p2], verts[p3])
                    normals[p1] += normal
                    normals[p2] += normal
                    normals[p3] += normal
                    tris.append((p1, p2, p3))

        for i, normal in enumerate(normals):
            normals[i] = normal.normalized()

        return verts, uvs, normals, tris

    def __str__(self) -> str:            
        res = (
            "{\n"
            + self.type + "\n"
            + "{\n"
            + (f"contents {' '.join([content for content in self.contents])};\n" if len(self.contents) != 0 else "")
            + (f"toolFlags {' '.join([flag for flag in self.toolFlags])};\n" if len(self.toolFlags) != 0 else "")
            + self.material + "\n"
            + "lightmap_gray" + "\n"
            + (f"smoothing {self.smoothing}\n" if self.smoothing is not None else "")
            + f"{self.size[0]} {self.size[1]} {self.sampleSize} 8\n"
        )

        for row in self.verts:
            res += "(\n"

            for vert in row:
                vert.noLightmap = self.noLightmap
                res += str(vert) + "\n"

            res += ")\n"

        res += "}\n"
        res += "}\n"
        return res
    
    def Save(self, file: TextIOWrapper):
        file.write("{\n")
        file.write(self.type + "\n")
        file.write("{\n")
        file.write((f"contents {' '.join([content for content in self.contents])};\n" if len(self.contents) != 0 else ""))
        file.write((f"toolFlags {' '.join([flag for flag in self.toolFlags])};\n" if len(self.toolFlags) != 0 else ""))
        file.write(self.material + "\n")
        file.write("lightmap_gray\n")
        file.write((f"smoothing {self.smoothing}\n" if self.smoothing is not None else ""))
        file.write(f"{self.size[0]} {self.size[1]} {self.sampleSize} 8\n")

        for row in self.verts:
            file.write("(\n")

            for vert in row:
                vert.noLightmap = self.noLightmap
                vert.Save(file)

            file.write(")\n")

        file.write("}\n")
        file.write("}\n")
