from typing import List
from math import isnan
from mathutils import Vector, geometry

def GetPlaneIntersectionPoint(face1: 'Face', face2: 'Face', face3: 'Face') -> Vector | None:
    """
    Calculates the intersecion points of three planes in 3D space.

    If the planes intersect, it will return a `Vector` object with the coordinates of the intersecion point.

    It will will return `None` if the planes don't intersect (if two of the planes are parallel to each other for example)
    """

    line = geometry.intersect_plane_plane(face1.p1, face1.GetNormal(), face2.p1, face2.GetNormal())

    if line is not None and line[0] is not None:
        return geometry.intersect_line_plane(line[0], line[0] + line[1], face3.p1, face3.GetNormal())

class Brush:
    """ Base class that holds all the necessary properties and methods used by a brush. """
    __slots__ = ("faces", "verts", "uvs")

    faces: List['Face']
    verts: List[Vector]
    uvs: List[Vector]

    def __init__(self) -> None:
        self.faces = []
        self.verts = []
        self.uvs = []
    
    def AddFace(self, face: 'Face') -> None:
        self.faces.append(face)
        face.parent = self
    
    def AddVert(self, vert: Vector) -> None:
        for v in self.verts:
            if v == vert:
                return
        
        self.verts.append(vert)
    
    def AddUV(self, uv: Vector) -> None:
        for _uv in self.uvs:
            if uv == _uv:
                return
        
        self.uvs.append(uv)
    
    def IsVertLegal(self, vert: Vector) -> bool:
        """
        Checks if a point in space is a part of the brush.
        """

        for face in self.faces:
            center: Vector = (face.p1 + face.p2 + face.p3) / 3
            facing: Vector = (vert - center).normalized()

            if facing.dot(face.GetNormal()) < -0.001:
                return False

        return True


    def CalculateVerts(self) -> None:
        """
        Compares each brush face with others and calculates their intersection points.

        The results of the calculations are stored in a list of vertices in the `Brush` object,

        and their indices are referenced by the faces of the brush.
        """

        for i, face1 in enumerate(self.faces[:-2]):
            for k, face2 in enumerate(self.faces[:-1]):
                for j, face3 in enumerate(self.faces):
                    if i is k or i is j or k is j: # skip comparing faces to themselves
                        continue
                        
                    intersection: Vector = GetPlaneIntersectionPoint(face1, face2, face3)

                    # make sure the intersection point is inside the brush
                    if intersection is None or not self.IsVertLegal(intersection):
                        continue
                    
                    self.AddVert(intersection)
                    face1.AddVert(intersection)
                    face2.AddVert(intersection)
                    face3.AddVert(intersection)

        for face in self.faces:
            face.SortVertices()
    
    def CalculateUVs(self) -> None:
        """
        Calculates the UV coordinates of each vertex of every face of the brush.

        The results are stored in a list of `Vector` objects and referenced by the faces that use them by their indices.
        """

        for face in self.faces:
            face.CalculateUVs()

from .Face import Face

