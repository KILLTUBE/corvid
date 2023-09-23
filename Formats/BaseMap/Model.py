from typing import List, Tuple
from mathutils import Vector

PolyVert = Tuple[int, int, int] # position uv normal
Triangle = Tuple[int, PolyVert, PolyVert, PolyVert] # material idx vert vert vert

class Group:
    __slots__ = ("vertices", "uvs", "normals", "name", "faces")

    vertices: List[Vector]
    uvs: List[Vector]
    normals: List[Vector]
    name: str
    faces: List[Triangle]

    def __init__(self, name: str) -> None:
        self.vertices = []
        self.uvs = []
        self.normals = []
        self.name = name
        self.faces = []

class Model:
    __slots__ = ("groups", "materials", "modelData")

    groups: List[Group]
    materials: List[str]

    def __init__(self) -> None:
        self.groups = []
        self.materials = []
