from mathutils import Vector
from .StandardUV import StandardUV

class CoDUV(StandardUV):
    __slots__ = ("lxScale", "lyScale")

    lxScale: float
    lyScale: float

    def GetUV(self, vertex: Vector, normal: Vector, texSize: Vector = None) -> Vector:
        texSize = Vector((512, 512))
        return super().GetUV(vertex, normal, texSize)
