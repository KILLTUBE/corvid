from typing import Dict

from modules.Vector2 import Vector2
from modules.Vector3 import Vector3
from .AABB import AABB
from .Brush import Brush
from .Side import Side
from mathutils import Vector, Matrix

# loop through bounding boxes and add touching brushes
def AddBrusesToOctree(box: AABB, brush: Brush):
    if not brush.AABB().IsTouching(box):
        return
    
    if box.children is None:
        if brush["id"] not in box.brushes:
            box.brushes.append(brush["id"])
    else:
        for child in box.children:
            AddBrusesToOctree(child, brush)

def GetBrushes(arr: 'AABB', brushes: list):
    if arr.children is not None:
        for child in arr.children:
            GetBrushes(child, brushes)
    else:
        for brush in arr.brushes:
            brushes.append(brush)

def GetCollidingBrushes(decal: AABB, octree: AABB, brushes: Dict[str, Brush]):
    res = []

    if octree.children is not None:
        for child in octree.children:
            GetCollidingBrushes(decal, child, brushes)
    else:
        for _brush in octree.brushes:
            brush = brushes[_brush]

            if not decal.IsTouching(brush.AABB()):
                continue
            
            for side in brush.sides:
                if not side.IsTouching(decal):
                    continue

                point = side.getClosestPoint(decal.center)

                if point.isLegal(brush.sides):
                    res.append(side.id)

    return res

def ProjectDecal(decal: AABB, side: Side, material: str, size: Vector2):
    center = decal.center.ToBpy()

    points = [
        center + Vector((-size.x / 2, -size.y / 2, 0)),
        center + Vector((-size.x / 2, size.y / 2, 0)),
        center + Vector((size.x / 2, -size.y / 2, 0)),
        center + Vector((size.x / 2, size.y / 2, 0)),
    ]

    normal = side.normal().normalize().ToBpy()
    quat = normal.to_track_quat('Z', 'Y')
    mat = quat.to_matrix().to_4x4()
    mat.translation = side.center().ToBpy()

    return [mat @ point for point in points]
