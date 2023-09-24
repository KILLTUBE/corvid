from mathutils import Vector
from .StandardUV import StandardUV

class CoDUV(StandardUV):
    __slots__ = ("lxScale", "lyScale")

    lxScale: float
    lyScale: float

    def GetUV(self, vertex: Vector, normal: Vector, texSize: Vector = None) -> Vector:
        texSize = Vector((512, 512))
        return super().GetUV(vertex, normal, texSize)

    def __str__(self) -> str:
        return f"{self.xScale} {self.yScale} {self.xOffset} {self.yOffset} {self.rotation} 0 lightmap_gray {self.lxScale} {self.lyScale} 0 0 0 0"
