from io import TextIOWrapper
from typing import Tuple, Union
from mathutils import Vector
from Formats.BaseMap.Face import Face as BaseFace
from Formats.Common.CoDUV import CoDUV
from Helpers.MathHelpers import VecFromList, Vec2Str

class Face(BaseFace):
    __slots__ = ("smoothing")

    uvData: CoDUV
    smoothing: str

    def __init__(self, plane: Tuple[Vector, Vector, Vector], material: str, uvData: CoDUV, smoothing: Union[str, None]) -> None:
        super().__init__()
        self.p1, self.p2, self.p3 = plane
        self.material = material
        self.uvData = uvData
        self.smoothing = smoothing
    
    def __str__(self) -> str:
        res = f"( {Vec2Str(self.p1)} ) ( {Vec2Str(self.p2)} ) ( {Vec2Str(self.p3)} ) {self.material} {self.uvData}"
        
        if self.smoothing is not None:
            res += " smoothing " + self.smoothing

        return res

    def __repr__(self) -> str:
        address = "%.2x" % id(self)
        return f"<Face ({Vec2Str(self.p1)} {Vec2Str(self.p2)} {Vec2Str(self.p3)}) object at {address}>"

    def Save(self, file: TextIOWrapper):
        file.write(str(self) + "\n")

    @staticmethod
    def FromStr(face: str) -> 'Face':
        # (p1) (p2) (p3) texture hScale vScale hShift vShift rotation 0 lmap lhScale lvScale lhShift lvShift lrot 0
        tok = face.split()
        plane = (VecFromList(tok[1:4]), VecFromList(tok[6:9]), VecFromList(tok[11:14]))
        uvData = CoDUV()
        uvData.xScale = float(tok[16])
        uvData.yScale = float(tok[17])
        uvData.xOffset = float(tok[18])
        uvData.yOffset = float(tok[19])
        uvData.rotation = float(tok[20])
        uvData.lxScale = float(tok[23])
        uvData.lyScale = float(tok[24])

        if len(tok) > 29 and tok[29] == "smoothing":
            smoothing = tok[30]
        else:
            smoothing = None

        return Face(plane, tok[15], uvData, smoothing)

