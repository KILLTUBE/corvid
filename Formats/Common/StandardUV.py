from math import fabs, cos, sin, radians
from mathutils import Vector
from Helpers.MathHelpers import VecUp, VecForward, VecRight

class StandardUV:
    """
    Standard texture alignment format used by old Quake games.
    """

    __slots__ = ("xScale", "yScale", "xOffset", "yOffset", "rotation")
    xScale: float
    yScale: float
    xOffset: float
    yOffset: float
    rotation: float

    def __init__(self) -> None:
        pass

    def GetUV(self, vertex: Vector, normal: Vector, texSize: Vector=None) -> Vector:
        print(self.xScale, self.yScale)
        du: float = fabs(normal.Dot(VecUp()))
        dr: float = fabs(normal.Dot(VecRight()))
        df: float = fabs(normal.Dot(VecForward()))

        uv: Vector = None
        if du >= dr and du >= df:
            uv = Vector((vertex.x, -vertex.y))
        elif dr >= du and dr >= df:
            uv = Vector((vertex.x, -vertex.z))
        elif df >= du and df >= dr:
            uv = Vector((vertex.y, -vertex.z))

        angle: float = radians(self.rotation)
        uv.x = uv.x * cos(angle) - uv.y * sin(angle)
        uv.y = uv.x * sin(angle) + uv.y * cos(angle)
        
        uv /= texSize
        uv /= Vector((self.xScale, self.yScale))
        uv += Vector((self.xOffset, self.yOffset)) / texSize

        return uv
    
    def __str__(self) -> str:
        return f"{self.xOffset:.6g} {self.yOffset:.6g} {self.rotation:.6g} {self.xScale:.6g} {self.yScale:.6g}"