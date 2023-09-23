from mathutils import Vector

class ValveUV:
    """
    A relatively newer texture alignment format used by Valve.

    It supports skewing the texture applied on a brush face.
    """

    __slots__ = ("uAxis", "uOffset", "uScale", "vAxis", "vOffset", "vScale")
    uAxis: Vector
    uOffset: float
    uScale: float
    vAxis: Vector
    vOffset: float
    vScale: float

    def GetUV(self, vertex: Vector, normal: Vector, texSize: Vector=None) -> Vector:
        if texSize is None:
            texSize = Vector(512, 512)

        return Vector(
            vertex.dot(self.uAxis) / (texSize.x * self.uScale) +
            (self.uOffset / texSize.x),
            vertex.dot(self.vAxis) / (texSize.y * self.vScale) +
            (self.vOffset / texSize.y)
        )
