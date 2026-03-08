from typing import Dict, List, Tuple
from math import isclose

import numpy as np
from glm import vec2, vec3, normalize, cross as glm_cross

from modules.Static import newPath
from .Side import Side
from .CoDMap.Patch import Patch, PatchVert

# based on https://github.com/lasa01/io_import_vmf/blob/master/io_import_vmf/import_vmf.py#L871

def _vec_isclose(a: np.ndarray, b: np.ndarray, rel_tol: float = 1e-6, abs_tol: float = 1e-6) -> bool:
    return (isclose(a[0], b[0], rel_tol=rel_tol, abs_tol=abs_tol)
            and isclose(a[1], b[1], rel_tol=rel_tol, abs_tol=abs_tol)
            and isclose(a[2], b[2], rel_tol=rel_tol, abs_tol=abs_tol))

def _vertices_center(verts) -> np.ndarray:
    return sum(verts) / len(verts)

def _vec3_to_np(v) -> np.ndarray:
    """Convert a glm vec3 or similar to numpy array."""
    if isinstance(v, np.ndarray):
        return v
    return np.array([v.x, v.y, v.z], dtype=np.float64)

def _parse_vec3(s: str) -> np.ndarray:
    """Parse a space-separated string into a numpy 3D vector."""
    s = s.replace("[","").replace("]","").replace("{","").replace("}","").replace("  ", " ").strip()
    tok = [float(i) for i in s.split()]
    while len(tok) < 3:
        tok.append(0.0)
    return np.array(tok[:3], dtype=np.float64)

def _distance_point_to_plane(point: np.ndarray, plane_point: np.ndarray, plane_normal: np.ndarray) -> float:
    """Signed distance from point to plane."""
    norm = np.linalg.norm(plane_normal)
    if norm == 0:
        return 0.0
    return np.dot(point - plane_point, plane_normal) / norm

def _intersect_line_plane(line_a: np.ndarray, line_b: np.ndarray, plane_point: np.ndarray, plane_normal: np.ndarray):
    """Intersect line (defined by two points) with plane. Returns intersection point or None."""
    line_dir = line_b - line_a
    denom = np.dot(plane_normal, line_dir)
    if abs(denom) < 1e-10:
        return None
    t = np.dot(plane_normal, plane_point - line_a) / denom
    return line_a + line_dir * t


class Overlay:
    id: int
    BasisNormal: np.ndarray
    BasisOrigin: np.ndarray
    BasisU: np.ndarray
    BasisV: np.ndarray
    EndU: float
    EndV: float
    material: str
    RenderOrder: int = 0
    sides: List[Side] = []
    StartU: float
    StartV: float
    uv_points: List[np.ndarray]
    origin: np.ndarray
    matSize: vec2

    verts: List[np.ndarray] = []
    uvs: List[Tuple[float, float]] = []

    texSize: vec2 = vec2(512, 512)

    empty: bool = False

    face_vertices = []
    face_vert_idxs = []
    face_uvs = []
    face_loop_uvs = []

    def __init__(self, entity: Dict[str, str], sideDict: Dict[str, Side], matSizes, scale: float = 1.0):
        self.id = entity["id"]
        self.BasisNormal = _parse_vec3(entity["BasisNormal"])
        self.BasisOrigin = _parse_vec3(entity["BasisOrigin"])
        self.BasisU = _parse_vec3(entity["BasisU"])
        self.BasisV = _parse_vec3(entity["BasisV"])
        self.EndU = float(entity["EndU"])
        self.EndV = float(entity["EndV"])
        self.material = entity["material"]
        self.scale = scale
        self.sides = []
        if "RenderOrder" in entity:
            self.RenderOrder = int(entity["RenderOrder"])
        else:
            self.RenderOrder = 0
        if entity["sides"] != "":
            self.sides = [sideDict[side] for side in entity["sides"].split(" ") if side in sideDict]

        if len(self.sides) == 0:
            print(f"No brush sides defined for overlay {self.id}")
            self.empty = True
            return

        self.StartU = float(entity["StartU"])
        self.StartV = float(entity["StartV"])
        self.uv_points = [
            _parse_vec3(entity["uv0"]),
            _parse_vec3(entity["uv1"]),
            _parse_vec3(entity["uv2"]),
            _parse_vec3(entity["uv3"])
        ]
        self.origin = _parse_vec3(entity["origin"])

        mat_key = newPath(entity["material"])
        if mat_key in matSizes:
            self.texSize = matSizes[mat_key]
        else:
            self.texSize = vec2(512, 512)

        origin = self.BasisOrigin.copy()
        normal = self.BasisNormal.copy()
        u_axis = self.BasisU.copy()
        v_axis = self.BasisV.copy()

        # matrix to convert coords from uv rotation space to world space
        uv_rot_to_global_matrix = np.array([
            [u_axis[0], v_axis[0], normal[0]],
            [u_axis[1], v_axis[1], normal[1]],
            [u_axis[2], v_axis[2], normal[2]]
        ], dtype=np.float64)

        try:
            global_to_uv_rot_matrix = np.linalg.inv(uv_rot_to_global_matrix)
        except np.linalg.LinAlgError:
            print(f"Singular matrix for overlay {self.id}")
            self.empty = True
            return

        vertices: List[np.ndarray] = []
        face_vertices: List[List[int]] = []

        # get face normals from sides
        face_normals = []
        for side in self.sides:
            n = side.normal()
            norm_len = (n.x**2 + n.y**2 + n.z**2)**0.5
            if norm_len > 0:
                face_normals.append(np.array([n.x/norm_len, n.y/norm_len, n.z/norm_len]))
            else:
                face_normals.append(np.array([0.0, 0.0, 1.0]))

        offset = 0.5
        if self.RenderOrder is not None:
            offset *= (1 + self.RenderOrder)

        for side in self.sides:
            face_vertices.append([])
            for point in side.points:
                np_point = _vec3_to_np(point)
                # check if vertex already exists
                found = False
                for idx, existing in enumerate(vertices):
                    if _vec_isclose(np_point, existing, 0.1, 0.1):
                        face_vertices[-1].append(idx)
                        found = True
                        break
                if not found:
                    face_vertices[-1].append(len(vertices))
                    vertices.append(np_point)

        if len(vertices) == 0:
            self.empty = True
            return

        # uv point space versions of overlay vertices
        uv_rot_vertices = [global_to_uv_rot_matrix @ (v - origin) for v in vertices]

        up_vector = np.array([0.0, 0.0, 1.0])
        remove_vertices = set()

        # cut faces partially outside the uv range and mark vertices outside for removal
        uv_edges = [self.uv_points[:2], self.uv_points[1:3], self.uv_points[2:4], (self.uv_points[3], self.uv_points[0])]
        for side_vert_a, side_vert_b in uv_edges:
            cut_plane_normal = np.cross(up_vector, side_vert_b - side_vert_a)
            # find out which vertices are outside this uv side
            outside_vertices = {
                i for i, v in enumerate(uv_rot_vertices)
                if _distance_point_to_plane(v, side_vert_a, cut_plane_normal) > 0.001
            }
            if len(outside_vertices) == 0:
                continue
            # mark them for removal
            remove_vertices |= outside_vertices
            # cut faces inside uv border
            for face_vert_idxs in face_vertices:
                if (all(v_idx not in outside_vertices for v_idx in face_vert_idxs)
                        or all(v_idx in outside_vertices for v_idx in face_vert_idxs)):
                    continue
                # find a vertex inside the border
                inside_idx = next(i for i, v_idx in enumerate(face_vert_idxs) if v_idx not in outside_vertices)
                # rotate the face vert list so it starts from a vertex inside
                while inside_idx > 0:
                    face_vert_idxs.append(face_vert_idxs.pop(0))
                    inside_idx -= 1
                # find first and last face vertices outside the uv border
                out_idx1 = next(i for i, v_idx in enumerate(face_vert_idxs) if v_idx in outside_vertices)
                *_, out_idx2 = (i for i, v_idx in enumerate(face_vert_idxs) if v_idx in outside_vertices)
                # create new vertex on the uv border by intersecting edge with border plane
                split_line = (
                    uv_rot_vertices[face_vert_idxs[(out_idx1 - 1) % len(face_vert_idxs)]],
                    uv_rot_vertices[face_vert_idxs[out_idx1]],
                )
                new_uv_rot_vertice = _intersect_line_plane(*split_line, side_vert_a, cut_plane_normal)
                if new_uv_rot_vertice is None:
                    continue
                new_vertice = origin + uv_rot_to_global_matrix @ new_uv_rot_vertice
                for other_idx, other_vert in enumerate(vertices):
                    if other_idx in remove_vertices:
                        continue
                    if _vec_isclose(other_vert, new_vertice, 0.001, 0.001):
                        new_vert_idx1 = other_idx
                        break
                else:
                    new_vert_idx1 = len(uv_rot_vertices)
                    uv_rot_vertices.append(new_uv_rot_vertice)
                    vertices.append(new_vertice)
                # do the same for the last face vertex outside the border
                split_line = (
                    uv_rot_vertices[face_vert_idxs[(out_idx2 + 1) % len(face_vert_idxs)]],
                    uv_rot_vertices[face_vert_idxs[out_idx2]],
                )
                new_uv_rot_vertice = _intersect_line_plane(*split_line, side_vert_a, cut_plane_normal)
                if new_uv_rot_vertice is None:
                    continue
                new_vertice = origin + uv_rot_to_global_matrix @ new_uv_rot_vertice
                for other_idx, other_vert in enumerate(vertices):
                    if other_idx in remove_vertices:
                        continue
                    if _vec_isclose(other_vert, new_vertice, 0.001, 0.001):
                        new_vert_idx2 = other_idx
                        break
                else:
                    new_vert_idx2 = len(uv_rot_vertices)
                    uv_rot_vertices.append(new_uv_rot_vertice)
                    vertices.append(new_vertice)
                # replace outside vertices with the 2 newly created ones
                face_vert_idxs[out_idx1:out_idx2 + 1] = [new_vert_idx1, new_vert_idx2]

        # ensure no new vertices are outside
        for side_vert_a, side_vert_b in uv_edges:
            cut_plane_normal = np.cross(up_vector, side_vert_b - side_vert_a)
            remove_vertices |= {
                i for i, v in enumerate(uv_rot_vertices)
                if _distance_point_to_plane(v, side_vert_a, cut_plane_normal) > 0.001
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
            if face_idx < len(old_face_normals):
                face_normals.append(old_face_normals[face_idx])

        if len(face_vertices) == 0:
            print(f"Overlay {self.id} has no valid faces after clipping")
            self.empty = True
            return

        # calculate projective transformation for the vertices into uvs based on the 4 supplied points
        # https://math.stackexchange.com/a/339033

        coeff_matrix = np.array([
            [self.uv_points[0][0], self.uv_points[1][0], self.uv_points[2][0]],
            [self.uv_points[0][1], self.uv_points[1][1], self.uv_points[2][1]],
            [1, 1, 1]
        ], dtype=np.float64)

        try:
            coeffs = np.linalg.solve(coeff_matrix, np.array([self.uv_points[3][0], self.uv_points[3][1], 1.0]))
        except np.linalg.LinAlgError:
            print(f"Singular UV matrix for overlay {self.id}")
            self.empty = True
            return

        basis_to_global = np.array([
            [coeffs[0] * self.uv_points[0][0], coeffs[1] * self.uv_points[1][0], coeffs[2] * self.uv_points[2][0]],
            [coeffs[0] * self.uv_points[0][1], coeffs[1] * self.uv_points[1][1], coeffs[2] * self.uv_points[2][1]],
            [coeffs[0], coeffs[1], coeffs[2]]
        ], dtype=np.float64)

        try:
            global_to_basis = np.linalg.inv(basis_to_global)
        except np.linalg.LinAlgError:
            print(f"Singular basis matrix for overlay {self.id}")
            self.empty = True
            return

        # matrix for mapping basis vectors to uv coordinates
        u1, u2, v1, v2 = self.StartU, self.EndU, 1 - self.EndV, 1 - self.StartV
        coeff_matrix = np.array([
            [u1, u1, u2],
            [v2, v1, v1],
            [1, 1, 1]
        ], dtype=np.float64)

        try:
            coeffs = np.linalg.solve(coeff_matrix, np.array([u2, v2, 1.0]))
        except np.linalg.LinAlgError:
            print(f"Singular UV coeff matrix for overlay {self.id}")
            self.empty = True
            return

        basis_to_uv = np.array([
            [coeffs[0] * u1, coeffs[1] * u1, coeffs[2] * u2],
            [coeffs[0] * v2, coeffs[1] * v1, coeffs[2] * v1],
            [coeffs[0], coeffs[1], coeffs[2]]
        ], dtype=np.float64)

        # combined matrix to map global to uv
        map_matrix = basis_to_uv @ global_to_basis

        # calculate texture coordinates for the vertices
        face_loop_uvs: List[List[Tuple[float, float]]] = []
        for face_vert_idxs in face_vertices:
            face_uvs: List[Tuple[float, float]] = []
            for vert_idx in face_vert_idxs:
                uv_vertice = uv_rot_vertices[vert_idx].copy()
                uv_vertice[2] = 1.0
                product_vec = map_matrix @ uv_vertice
                if abs(product_vec[2]) > 1e-10:
                    face_uvs.append((product_vec[0] / product_vec[2], product_vec[1] / product_vec[2]))
                else:
                    face_uvs.append((0.0, 0.0))
            face_loop_uvs.append(face_uvs)

        if len(vertices) == 0:
            self.empty = True
            return

        self.verts = list(vertices)
        self.face_vertices = face_vertices
        self.face_loop_uvs = face_loop_uvs

    def to_patches(self) -> List[Patch]:
        """Convert the overlay to a list of CoD patches."""
        if self.empty:
            print(f"No vertices could be calculated for overlay {self.id}")
            return []

        patches = []
        tex_scale = vec2(1024, -1024)
        mat = newPath(self.material)

        for face_indices, loop_uvs in zip(self.face_vertices, self.face_loop_uvs):
            verts = [self.verts[i] for i in face_indices]
            uvs = list(loop_uvs)

            if len(verts) < 2:
                continue

            if len(verts) % 2 == 1:
                verts.append(verts[-1])
                uvs.append(uvs[-1])

            count = len(verts)
            rows = count // 2

            patch = Patch(type="mesh", texture=mat, lightmap="lightmap_gray", size=(rows, 2), samplesize=16)
            patch.nolightmap = True

            for i in range(rows):
                row = []
                p1 = verts[i]
                uv1 = uvs[i]
                p2 = verts[count - i - 1]
                uv2 = uvs[count - i - 1]

                pos1 = vec3(float(p1[0]), float(p1[1]), float(p1[2])) * self.scale
                uv1_scaled = vec2(float(uv1[0]), float(uv1[1])) * tex_scale
                row.append(PatchVert(pos1, uv1_scaled, vec2(0, 0)))

                pos2 = vec3(float(p2[0]), float(p2[1]), float(p2[2])) * self.scale
                uv2_scaled = vec2(float(uv2[0]), float(uv2[1])) * tex_scale
                row.append(PatchVert(pos2, uv2_scaled, vec2(0, 0)))

                patch.verts.append(row)

            patches.append(patch)

        return patches
