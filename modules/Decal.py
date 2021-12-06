from math import radians
from typing import Dict, Tuple
from mathutils import Vector, Matrix, geometry
from .Side import Side
from .Vector3 import Vector3
from .Vector2 import Vector2

class AABB:
    origin: Vector
    extents: Vector

    def __init__(self, origin: Vector, extents: Vector):
        self.origin, self.extents = origin, extents

# based on https://gdbooks.gitbooks.io/3dcollisions/content/Chapter2/static_aabb_plane.html
def checkBoxPlaneCollision(origin: Vector, side: Side):
    box = AABB(origin, Vector((4, 4, 4)))
    normal = side.normal().normalize().ToBpy()
    radius = box.extents.x * abs(normal.x) + box.extents.y * abs(normal.y) + box.extents.z * abs(normal.z)
    dist = normal.dot(origin) - ((side.p2 - side.p1).cross(side.p3 - side.p1).normalize().dot(side.p1))
    return abs(dist) <= radius


def GetDecalPoints(origin: Vector, side: Side):
    # create a quat with the origin of the decal entity's origin as its center
    points = [
        origin + Vector((-128, -128, 0)),
        origin + Vector((-128, 128, 0)),
        origin + Vector((128, -128, 0)),
        origin + Vector((128, 128, 0)),
    ]

    # create a rotation matrix based on the side's normal
    normal = side.normal().normalize().ToBpy()
    quat = normal.to_track_quat('Z', 'Y')
    mat = quat.to_matrix().to_4x4()
    mat.translation = side.center().ToBpy()

    # rotate each point with the matrix
    return [mat @ point for point in points]

def convertDecal(entity, sideDict: Dict[str, Side]):
    origin = Vector3.FromStr(entity["origin"]).ToBpy()
    
    # iterate through sides
    for side in sideDict.values():
        # displacements can't have infodecals
        # if side.hasDisp:
        #    continue
        
        # check if the box is in the radius of the side
        # if (origin - side.center().ToBpy()).length < side.radius():
        #    continue

        # check if the box is colliding with the side
        # since we know it is inside the radius of the side, we only need to check if the box intersects with the side's plane
        if side.id == "14":
            print(GetDecalPoints(origin, side))

        # get points of the decal rotated with the side's normal
        # print(f"Decal {entity['id']} collides with side {side.id}.")
        
