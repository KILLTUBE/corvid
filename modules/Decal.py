from typing import Dict, List, Tuple
from math import fabs

from glm import vec2, vec3, normalize, cross, dot, length

from modules.Static import newPath
from .Brush import Brush
from .Side import Side
from .AABB import AABB
from .CoDMap.Patch import Patch, PatchVert


def _clip_polygon_by_edge(verts: List[vec3], uvs: List[vec2], plane_point: vec3, plane_normal: vec3) -> Tuple[List[vec3], List[vec2]]:
    """Clip a polygon (with associated UVs) against a plane using Sutherland-Hodgman."""
    if len(verts) == 0:
        return [], []

    out_verts = []
    out_uvs = []
    n = len(verts)

    for i in range(n):
        curr = verts[i]
        curr_uv = uvs[i]
        nxt = verts[(i + 1) % n]
        nxt_uv = uvs[(i + 1) % n]

        d_curr = dot(plane_normal, curr - plane_point)
        d_nxt = dot(plane_normal, nxt - plane_point)

        if d_curr >= 0:
            out_verts.append(curr)
            out_uvs.append(curr_uv)
            if d_nxt < 0:
                t = d_curr / (d_curr - d_nxt)
                out_verts.append(curr + (nxt - curr) * t)
                out_uvs.append(curr_uv + (nxt_uv - curr_uv) * t)
        elif d_nxt >= 0:
            t = d_curr / (d_curr - d_nxt)
            out_verts.append(curr + (nxt - curr) * t)
            out_uvs.append(curr_uv + (nxt_uv - curr_uv) * t)

    return out_verts, out_uvs


def _clip_quad_to_face(quad_verts: List[vec3], quad_uvs: List[vec2], face_points: List[vec3], face_normal: vec3) -> Tuple[List[vec3], List[vec2]]:
    """Clip a quad against a convex face polygon by clipping against each edge plane."""
    clipped_verts = list(quad_verts)
    clipped_uvs = list(quad_uvs)

    n = len(face_points)
    for i in range(n):
        if len(clipped_verts) < 3:
            return [], []
        a = face_points[i]
        b = face_points[(i + 1) % n]
        # edge plane normal points inward (into the face)
        edge_normal = normalize(cross(b - a, face_normal))
        clipped_verts, clipped_uvs = _clip_polygon_by_edge(clipped_verts, clipped_uvs, a, edge_normal)

    return clipped_verts, clipped_uvs


class Decal:
    def __init__(self, entity: dict, brushDict: Dict[str, Brush], matSizes: dict, vmts: dict, scale: float = 1.0):
        origin = entity["origin"].split()
        self.origin = vec3(float(origin[0]), float(origin[1]), float(origin[2]))
        self.texture = entity["texture"]
        self.scale = scale
        self.id = entity["id"] if "id" in entity else "?"

        mat_key = newPath(self.texture)
        if mat_key in matSizes:
            self.texSize = matSizes[mat_key]
        else:
            self.texSize = vec2(512, 512)

        # read $decalscale from VMT — units per texel (typically 0.25 or lower)
        self.decalScale = 0.25
        # vmts are keyed by the converted material name, same as matSizes
        if mat_key in vmts:
            vmt = vmts[mat_key]
            shader = list(vmt)[0]
            mat = vmt[shader]
            if "$decalscale" in mat:
                self.decalScale = float(mat["$decalscale"])

        self.half_w = (self.texSize.x * self.decalScale) / 2.0
        self.half_h = (self.texSize.y * self.decalScale) / 2.0

        self.faces: List[Tuple[Side, vec3]] = []
        self._find_colliding_faces(brushDict)

    def _find_colliding_faces(self, brushDict: Dict[str, Brush]):
        box = AABB.FromPoint(self.origin, size=8)

        for brush in brushDict.values():
            if not brush.AABB().IsTouching(box):
                continue

            for side in brush.sides:
                if side.material.startswith("tools"):
                    continue
                if len(side.points) < 3:
                    continue
                if not side.IsTouching(box):
                    continue

                closest = side.getClosestPoint(self.origin)
                self.faces.append((side, closest))

    def _get_closest_face(self) -> Tuple[Side, vec3]:
        """Return the face whose closest point is nearest to the decal origin."""
        best = None
        best_dist = float("inf")
        for side, closest in self.faces:
            d = length(closest - self.origin)
            if d < best_dist:
                best_dist = d
                best = (side, closest)
        return best

    def to_patches(self, zOffset=0.0) -> List[Patch]:
        if len(self.faces) == 0:
            return []

        closest_face = self._get_closest_face()
        if closest_face is None:
            return []

        primary_side, center = closest_face
        normal = normalize(primary_side.normal())

        # build tangent/bitangent from face normal
        if fabs(dot(normal, vec3(0, 0, 1))) < 0.9:
            up = vec3(0, 0, 1)
        else:
            up = vec3(0, 1, 0)

        tangent = normalize(cross(up, normal))
        bitangent = normalize(cross(normal, tangent))

        # full decal quad corners and UVs
        quad_verts = [
            center + tangent * (-self.half_w) + bitangent * ( self.half_h),
            center + tangent * ( self.half_w) + bitangent * ( self.half_h),
            center + tangent * ( self.half_w) + bitangent * (-self.half_h),
            center + tangent * (-self.half_w) + bitangent * (-self.half_h),
        ]
        quad_uvs = [
            vec2(1, 1),
            vec2(0, 1),
            vec2(0, 0),
            vec2(1, 0),
        ]

        patches = []
        tex_scale = vec2(1024, -1024)
        mat = newPath(self.texture)

        for side, _ in self.faces:
            face_normal = normalize(side.normal())

            # skip faces that face away from the decal projection direction
            if dot(face_normal, normal) < 0.1:
                continue

            # project quad verts onto this face's plane
            projected = []
            for v in quad_verts:
                projected.append(side.getClosestPoint(v))

            # clip the projected quad to the face polygon
            clipped_verts, clipped_uvs = _clip_quad_to_face(projected, list(quad_uvs), side.points, face_normal)

            if len(clipped_verts) < 3:
                continue

            # offset outward along face normal to avoid z-fighting
            # side.normal() points inward, so negate for outward direction
            offset = face_normal * -(zOffset)
            clipped_verts = [v + offset for v in clipped_verts]

            # build patch: pair vertices across the polygon
            verts = clipped_verts
            uvs = clipped_uvs

            if len(verts) % 2 == 1:
                verts.append(verts[-1])
                uvs.append(uvs[-1])

            count = len(verts)
            rows = count // 2

            patch = Patch(type="mesh", texture=mat, lightmap="lightmap_gray", size=(rows, 2), samplesize=16)
            patch.nolightmap = True

            for i in range(rows):
                p1 = verts[i]
                uv1 = uvs[i]
                p2 = verts[count - i - 1]
                uv2 = uvs[count - i - 1]

                row = [
                    PatchVert(p1 * self.scale, uv1 * tex_scale, vec2(0, 0)),
                    PatchVert(p2 * self.scale, uv2 * tex_scale, vec2(0, 0)),
                ]
                patch.verts.append(row)

            patches.append(patch)

        return patches
