from collections import OrderedDict
from typing import Dict, List, Tuple, Union
from mathutils import Vector
from Formats.BaseMap.Face import Face
from Formats.Common.ValveUV import ValveUV
from .Displacement import Displacement
from Helpers.MathHelpers import Vec2Str, VecFromList

class Side(Face):
    __slots__ = ("id", "lightmapScale", "dispInfo")

    uvData: ValveUV
    parent: 'Solid'
    id: int
    lightmapScale: float
    dispInfo: Union[Displacement, None]

    def __init__(self, data: Dict[str, Union[str, dict]]=None, plane: Tuple[Vector, Vector, Vector]=None, material: str=None, uvData: ValveUV=None) -> None:
        super().__init__()

        if data is None:
            self.id = None
            self.p1, self.p2, self.p3 = plane
            self.material = material
            self.uvData = uvData
            self.lightmapScale = 16
            self.dispInfo = None

        else:
            self.id = int(data["id"]) if "id" in data else None

            plane = data["plane"].replace("(", "").replace(")", "").split()
            self.p1 = VecFromList(plane[0:3])
            self.p2 = VecFromList(plane[3:6])
            self.p3 = VecFromList(plane[6:9])

            self.material = data["material"].strip().lower()

            self.uvData = ValveUV()
            
            u = data["uaxis"].split()
            self.uvData.uAxis = VecFromList((u[0][1:], u[1], u[2]))
            self.uvData.uOffset = float(u[3][:-1])
            self.uvData.uScale = float(u[4])

            v = data["vaxis"].split()
            self.uvData.vAxis = VecFromList((v[0][1:], v[1], v[2]))
            self.uvData.vOffset = float(v[3][:-1])
            self.uvData.vScale = float(v[4])

            self.lightmapScale = float(data["lightmapscale"])
            self.dispInfo = Displacement(data["dispinfo"]) if "dispinfo" in data else None

    def SliceDispVerts(self, v1: Vector, v2: Vector, uv1: Vector, uv2) -> List[Tuple[Vector, Vector]]:
        res: List[Tuple[Vector, Vector]] = []
        numRows = self.dispInfo.numRows

        for i in range(numRows):
            res.append((
                v1.lerp(v2, 1 / (numRows - 1) * i), # pos
                uv1.lerp(uv2, 1 / (numRows - 1) * i), # uv
            ))

        return res

    def GetDispVerts(self) -> List[List[Tuple[Vector, Vector, Vector, float, int]]]:
        disp, verts, uvs, numRows = self.dispInfo, self.GetVerts(), self.GetUVs(), self.dispInfo.numRows

        # shift the start position of the displacement to the start of the vert list
        s: int = None
        for i, v in enumerate(verts):
            if v == self.dispInfo.startPosition:
                s = i
                break

        if s is None:
            print(f"Can't find the start position of brush side {self.id}.")
            exit()

        a, UVa = verts[s], uvs[s]
        b, UVb = verts[(s + 1) % 4], uvs[(s + 1) % 4]
        c, UVc = verts[(s + 2) % 4], uvs[(s + 2) % 4]
        d, UVd = verts[(s + 3) % 4], uvs[(s + 3) % 4]

        # calculate the disp vert between each side
        ab = self.SliceDispVerts(a, b, UVa, UVb)
        dc = self.SliceDispVerts(d, c, UVd, UVc)

        res: List[List[Tuple[Vector, Vector, Vector, float, int]]] = [] 

        for i in range(numRows):
            res.append([])
            # calculate the verts between those verts
            dispVerts = self.SliceDispVerts(ab[i][0], dc[i][0], ab[i][1], dc[i][1])
            # add the vertex, uv and other displacement info in a 2d list
            for r, (pos, uv) in enumerate(dispVerts):
                res[i].append(
                    (pos, uv, disp.normals[r][i], disp.distances[r][i], disp.alphas[r][i])
                )
            
        return res

    def TriangulateDisp(self) -> List[Tuple[Vector, Vector, Vector, float, int]]:
        verts = self.GetDispVerts()
        tris: List[Tuple[Vector, Vector, Vector, float, int]] = []

        for i in range(self.dispInfo.numRows - 1):
            for k in range(self.dispInfo.numRows):
                if k != self.dispInfo.numRows - 1: # first vert in the row
                    tris.append((verts[i + 1][k], verts[i][k + 1], verts[i][k]))
                if k != 0: # last vert in the row
                    tris.append((verts[i + 1][k - 1], verts[i + 1][k], verts[i][k]))

        return tris

    def ToDict(self, id: int=None) -> dict:
        res = OrderedDict()
        if id is not None:
            res["id"] = id
        elif id is None and self.id is not None:
            res["id"] = self.id

        
        res["plane"] = f"({Vec2Str(self.p1)}) ({Vec2Str(self.p2)}) ({Vec2Str(self.p3)})"
        res["material"] = self.material.upper()

        uvData = self.uvData
        res["uaxis"] = f"[{uvData.uAxis} {uvData.uOffset:.6g}] {uvData.uScale:.6g}"
        res["vaxis"] = f"[{uvData.vAxis} {uvData.vOffset:.6g}] {uvData.vScale:.6g}"

        res["rotation"] = 0
        res["lightmapscale"] = f"{self.lightmapScale:.6g}"
        res["smoothing_groups"] = 0

        if self.dispInfo is not None:
            res["dispinfo"] = self.dispInfo.ToDict()

        return res

from Formats.Source.Solid import Solid
