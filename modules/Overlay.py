from math import isclose
from typing import Dict, List, Tuple

from .Static import newPath
from .Vector3 import Vector3
from .Vector2 import Vector2
from .Side import Side

from mathutils import Vector, Matrix, geometry

# based on https://github.com/lasa01/io_import_vmf/blob/master/io_import_vmf/import_vmf.py#L871

def _vec_isclose(a: Vector, b: Vector, rel_tol: float = 1e-6, abs_tol: float = 1e-6) -> bool:
    return (isclose(a.x, b.x, rel_tol=rel_tol, abs_tol=abs_tol)
            and isclose(a.y, b.y, rel_tol=rel_tol, abs_tol=abs_tol)
            and isclose(a.z, b.z, rel_tol=rel_tol, abs_tol=abs_tol))

def _vertices_center(verts) -> Vector:
    return sum(verts, Vector((0, 0, 0))) / len(verts)

class Overlay:
    id: int
    origin: Vector3
    angles: Vector3
    BasisNormal: Vector3
    BasisOrigin: Vector3
    BasisU: Vector3
    BasisV: Vector3

    StartU: float
    StartV: float
    EndU: float
    EndV: float
    
    material: str
    RenderOrder: int = 0
    sides: List[Side] = []
    texSize: Vector2 = Vector2(512, 512)
    
    uv0: Vector3
    uv1: Vector3
    uv2: Vector3
    uv3: Vector3

    empty: bool = False

    points: List[Vector3]
    uvs: List[Vector2]
    polys: List

    epsilon: float = 0.001

    def __init__(self, entity: Dict[str, str], sideDict: Dict[str, Side], matSizes):
        self.id = int(entity["id"])

        self.origin = Vector3.FromStr(entity["origin"])
        if "angles" in entity:
            self.angles = Vector3.FromStr(entity["angles"])
        self.BasisNormal = Vector3.FromStr(entity["BasisNormal"])
        self.BasisOrigin = Vector3.FromStr(entity["BasisOrigin"])
        self.BasisU = Vector3.FromStr(entity["BasisU"])
        self.BasisV = Vector3.FromStr(entity["BasisV"])

        self.StartU = float(entity["StartU"])
        self.StartV = float(entity["StartV"])
        self.EndU = float(entity["EndU"])
        self.EndV = float(entity["EndV"])

        self.material = newPath(entity["material"])
        self.texSize = matSizes[self.material]
        
        if "RenderOrder" in entity:
            self.RenderOrder = int(entity["RenderOrder"])

        if entity["sides"] != "":
            for side in entity["sides"].split(" "):
                self.sides.append(sideDict[side])
        else:
            self.empty = True
            return None
        
        self.uv0 = Vector3.FromStr(entity["uv0"]).ToBpy()
        self.uv1 = Vector3.FromStr(entity["uv1"]).ToBpy()
        self.uv2 = Vector3.FromStr(entity["uv2"]).ToBpy()
        self.uv3 = Vector3.FromStr(entity["uv3"]).ToBpy()

        origin = self.BasisOrigin.ToBpy()
        normal = self.BasisNormal.ToBpy()
        u_axis = self.BasisU.ToBpy()
        v_axis = self.BasisV.ToBpy()

        # matrix to convert coords from uv rotation space to world space (hopefully)
        uv_rot_to_global_matrix = Matrix((
            (u_axis.x, v_axis.x, normal.x),
            (u_axis.y, v_axis.y, normal.y),
            (u_axis.z, v_axis.z, normal.z)
        ))

        global_to_uv_rot_matrix = uv_rot_to_global_matrix.inverted()

        vertices: List[Vector3] = []
        face_vertices: List[List[int]] = []
        face_normals: List[Vector] = [side.normal().normalize().ToBpy() for side in self.sides]

        offset = 0.1
        offset *= (1 + self.RenderOrder)

        for side in self.sides:
            face_vertices.append([])
            for point in side.points:
                if point not in vertices:
                    vertices.append(point)
                    face_vertices[-1].append(vertices.index(point))

        vertices = [vert.ToBpy() for vert in vertices.copy()]

        if len(vertices) == 0:
            self.empty = True
            return None

        # uv point space versions of overlay vertices
        uv_rot_vertices = [global_to_uv_rot_matrix @ (v - origin) for v in vertices]

        uv_points = (
            Vector(self.uv0),
            Vector(self.uv1),
            Vector(self.uv2),
            Vector(self.uv3)
        )

        up_vector = Vector((0, 0, 1))
        remove_vertices = set()

        # cut faces partially outside the uv range and mark vertices outside for removal
        for side_vert_a, side_vert_b in (uv_points[:2], uv_points[1:3], uv_points[2:4], (uv_points[3], uv_points[0])):
            cut_plane_normal: Vector = up_vector.cross(side_vert_b - side_vert_a)
            # find out which vertices are outside this uv side
            outside_vertices = {
                i for i, v in enumerate(uv_rot_vertices)
                if geometry.distance_point_to_plane(v, side_vert_a, cut_plane_normal) > self.epsilon
            }
            if len(outside_vertices) == 0:
                continue
            # mark them for removal
            remove_vertices |= outside_vertices
            # cut faces inside uv border
            for face_vert_idxs in face_vertices:
                if (all(v_idx not in outside_vertices for v_idx in face_vert_idxs)
                        or all(v_idx in outside_vertices for v_idx in face_vert_idxs)):
                    # skip faces completely on either side
                    continue
                # find a vertice inside the border,
                inside_idx = next(i for i, v_idx in enumerate(face_vert_idxs) if v_idx not in outside_vertices)
                # rotate the face vert list so that it starts from a vertice inside
                while inside_idx > 0:
                    face_vert_idxs.append(face_vert_idxs.pop(0))
                    inside_idx -= 1
                # and find the first and last face vertices that are outside the uv border,
                out_idx1 = next(i for i, v_idx in enumerate(face_vert_idxs) if v_idx in outside_vertices)
                *_, out_idx2 = (i for i, v_idx in enumerate(face_vert_idxs) if v_idx in outside_vertices)
                # and create new vertice on the uv border
                # by intersecting the first edge crossing the uv border with the uv border plane,
                split_line = (
                    uv_rot_vertices[face_vert_idxs[(out_idx1 - 1) % len(face_vert_idxs)]],
                    uv_rot_vertices[face_vert_idxs[out_idx1]],
                )
                new_uv_rot_vertice = geometry.intersect_line_plane(*split_line, side_vert_a, cut_plane_normal)
                new_vertice = origin + uv_rot_to_global_matrix @ new_uv_rot_vertice
                for other_idx, other_vert in enumerate(vertices):
                    if other_idx in remove_vertices:
                        continue
                    if _vec_isclose(other_vert, new_vertice, self.epsilon, self.epsilon):
                        new_vert_idx1 = other_idx
                        break
                else:
                    new_vert_idx1 = len(uv_rot_vertices)
                    uv_rot_vertices.append(new_uv_rot_vertice)
                    vertices.append(new_vertice)
                # do the same for the last face vertice that is outside the border
                split_line = (
                    uv_rot_vertices[face_vert_idxs[(out_idx2 + 1) % len(face_vert_idxs)]],
                    uv_rot_vertices[face_vert_idxs[out_idx2]],
                )
                new_uv_rot_vertice = geometry.intersect_line_plane(*split_line, side_vert_a, cut_plane_normal)
                new_vertice = origin + uv_rot_to_global_matrix @ new_uv_rot_vertice
                for other_idx, other_vert in enumerate(vertices):
                    if other_idx in remove_vertices:
                        continue
                    if _vec_isclose(other_vert, new_vertice, self.epsilon, self.epsilon):
                        new_vert_idx2 = other_idx
                        break
                else:
                    new_vert_idx2 = len(uv_rot_vertices)
                    uv_rot_vertices.append(new_uv_rot_vertice)
                    vertices.append(new_vertice)
                # and replace the face vertices that were outside the uv border with the 2 newly created ones
                face_vert_idxs[out_idx1:out_idx2 + 1] = new_vert_idx1, new_vert_idx2

        # ensure no new vertices are outside
        for side_vert_a, side_vert_b in (uv_points[:2], uv_points[1:3], uv_points[2:4], (uv_points[3], uv_points[0])):
            cut_plane_normal = up_vector.cross(side_vert_b - side_vert_a)
            remove_vertices |= {
                i for i, v in enumerate(uv_rot_vertices)
                if geometry.distance_point_to_plane(v, side_vert_a, cut_plane_normal) > self.epsilon
            }

        # remove marked vertices and faces referencing them
        old_vertices = vertices
        vertices = []
        old_uv_rot_vertices = uv_rot_vertices
        uv_rot_vertices = []
        vertice_idx_map = {}
        for vertice_idx, vertice in enumerate(old_vertices):
            if vertice_idx in remove_vertices:
                continue
            vertice_idx_map[vertice_idx] = len(vertices)
            vertices.append(vertice)
            uv_rot_vertices.append(old_uv_rot_vertices[vertice_idx])

        old_face_vertices = face_vertices
        face_vertices = []
        old_face_normals = face_normals
        face_normals = []
        for face_idx, face_vert_idxs in enumerate(old_face_vertices):
            if any(v_idx in remove_vertices for v_idx in face_vert_idxs):
                continue
            face_vertices.append([vertice_idx_map[v_idx] for v_idx in face_vert_idxs])
            face_normals.append(old_face_normals[face_idx])

        if len(vertices) == 0:
            print(f"Could not calculate overlay for {self.id}")
            self.empty = True
            return None

        # calculate projective transformation for the vertices into uvs based on the 4 supplied points
        # https://math.stackexchange.com/a/339033
        # FIXME: should be probably linear, not projective

        # compute matrix for mapping global coordinates to basis vectors
        coeff_matrix = Matrix((
            (uv_points[0].x, uv_points[1].x, uv_points[2].x),
            (uv_points[0].y, uv_points[1].y, uv_points[2].y),
            (1, 1, 1)
        ))
        coeffs: Vector = coeff_matrix.inverted() @ Vector((uv_points[3].x, uv_points[3].y, 1))
        basis_to_global = Matrix((
            (coeffs.x * uv_points[0].x, coeffs.y * uv_points[1].x, coeffs.z * uv_points[2].x),
            (coeffs.x * uv_points[0].y, coeffs.y * uv_points[1].y, coeffs.z * uv_points[2].y),
            (coeffs.x, coeffs.y, coeffs.z)
        ))
        global_to_basis = basis_to_global.inverted()

        # matrix for mapping basis vectors to uv coordinates
        u1, u2, v1, v2 = self.StartU, self.EndU, 1 - self.EndV, 1 - self.StartV
        coeff_matrix = Matrix((
            (u1, u1, u2),
            (v2, v1, v1),
            (1, 1, 1)
        ))
        coeffs = coeff_matrix.inverted() @ Vector((u2, v2, 1))
        basis_to_uv = Matrix((
            (coeffs.x * u1, coeffs.y * u1, coeffs.z * u2),
            (coeffs.x * v2, coeffs.y * v1, coeffs.z * v1),
            (coeffs.x, coeffs.y, coeffs.z)
        ))

        # combined matrix to map global to uv
        map_matrix = basis_to_uv @ global_to_basis

        # calculate texture coordinates for the vertices
        face_loop_uvs: List[List[Tuple[float, float]]] = []
        for face_vert_idxs in face_vertices:
            face_uvs: List[Tuple[float, float]] = []
            for vert_idx in face_vert_idxs:
                uv_vertice = uv_rot_vertices[vert_idx]
                uv_vertice.z = 1
                product_vec = map_matrix @ uv_vertice
                face_uvs.append((product_vec.x / product_vec.z, product_vec.y / product_vec.z))
            face_loop_uvs.append(face_uvs)

        center = _vertices_center(vertices)

        self.verts = [Vector3.FromArray(v - center + self.BasisOrigin.ToBpy()) for v in vertices]
        self.uvs = [Vector2.FromArray(v) for v in face_uvs]
        self.face_vertices = face_vertices # nested lists of vertex indices
        self.face_vert_idxs = face_vert_idxs # 
        self.face_uvs = face_uvs
        self.face_idx = face_idx
        self.face_loop_uvs = face_loop_uvs

    def __str__(self):
        if self.empty:
            return ""

        res = f"// Overlay {self.id}\n"

        self.texSize.y *= -1

        for face_indices, loop_uvs in zip(self.face_vertices, self.face_loop_uvs):
            verts = [self.verts[i] for i in face_indices]
            uvs = [Vector2.FromArray(uv) for uv in loop_uvs]

            if len(verts) % 2 == 1:
                verts.append(verts[-1])
                uvs.append(uvs[-1])

            count = int(len(verts))
            rows = int(count / 2)

            if rows == 0:
                continue

            mat = self.material
            # mat = "icbm_bunkermural2"


            res += (
                "{\n"
                + "mesh\n"
                + "{\n"
                + f"{mat}\n"
                + "lightmap_gray\n"
                + str(rows) + " 2 16 8\n"
            )

            for i in range(rows):
                p1 = {
                    "pos": str((verts[i])),
                    "uv": str(uvs[i] * self.texSize * 2)
                }
                p2 = {
                    "pos": str((verts[count - i - 1])),
                    "uv": str(uvs[count - i - 1] * self.texSize * 2)
                }
                res += (
                    "(\n" +
                    f'v {p1["pos"]} t {p1["uv"]}\n' +
                    f'v {p2["pos"]} t {p2["uv"]}\n' +
                    ")\n"
                )

            res += (
                "}\n"
                + "}\n"
            )

        return res 

