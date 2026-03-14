from typing import Dict, List, Tuple
from math import isclose, pow

import numpy as np
from glm import vec2, vec3, normalize, cross as glm_cross, lerp, distance

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

def _lerp_np(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    return a + (b - a) * t

def _ensure_winding(verts: List[np.ndarray], desired_normal: np.ndarray) -> List[np.ndarray]:
    """Reverse vertex order if polygon normal doesn't match the desired normal direction."""
    if len(verts) < 3:
        return verts
    edge1 = verts[1] - verts[0]
    edge2 = verts[2] - verts[0]
    poly_normal = np.cross(edge1, edge2)
    if np.dot(poly_normal, desired_normal) < 0:
        verts.reverse()
    return verts

def _clip_polygon_by_planes(verts: List[np.ndarray], planes: List[Tuple[np.ndarray, np.ndarray]]) -> List[np.ndarray]:
    """Clip a polygon against a list of planes using Sutherland-Hodgman. Each plane is (point, inward_normal)."""
    for plane_point, plane_normal in planes:
        if len(verts) < 3:
            return []
        out = []
        n = len(verts)
        for i in range(n):
            curr = verts[i]
            nxt = verts[(i + 1) % n]
            d_curr = np.dot(plane_normal, curr - plane_point)
            d_nxt = np.dot(plane_normal, nxt - plane_point)
            if d_curr >= 0:
                out.append(curr)
                if d_nxt < 0:
                    t = d_curr / (d_curr - d_nxt)
                    out.append(_lerp_np(curr, nxt, t))
            elif d_nxt >= 0:
                t = d_curr / (d_curr - d_nxt)
                out.append(_lerp_np(curr, nxt, t))
        verts = out
    return verts


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
            # decompiled maps often have broken overlay data, so we silently skip them
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
            self.empty = True
            return

        # build slab clipping planes from the 4 UV edges in world space
        # these define the overlay's boundary
        uv_edges = [self.uv_points[:2], self.uv_points[1:3], self.uv_points[2:4], (self.uv_points[3], self.uv_points[0])]
        up_vector = np.array([0.0, 0.0, 1.0])
        self._slab_planes = []
        for side_vert_a, side_vert_b in uv_edges:
            cut_normal_uv = np.cross(up_vector, side_vert_b - side_vert_a)
            # convert plane to world space: normal and a point on the plane
            world_normal = uv_rot_to_global_matrix @ cut_normal_uv
            norm_len = np.linalg.norm(world_normal)
            if norm_len > 0:
                world_normal /= norm_len
            world_point = origin + uv_rot_to_global_matrix @ side_vert_a
            # inward normal (points inside the overlay)
            self._slab_planes.append((world_point, -world_normal))

        # separate displacement sides from flat sides
        # treat displacements with all-zero distances as flat
        disp_sides = []
        flat_sides = []
        for s in self.sides:
            if s.hasDisp and any(d != 0 for row in s.dispinfo["row"] for d in row["distances"]):
                disp_sides.append(s)
            else:
                flat_sides.append(s)

        vertices: List[np.ndarray] = []
        face_vertices: List[List[int]] = []

        # process flat sides (existing approach)
        face_normals = []
        for side in flat_sides:
            n = side.normal()
            norm_len = (n.x**2 + n.y**2 + n.z**2)**0.5
            if norm_len > 0:
                face_normals.append(np.array([n.x/norm_len, n.y/norm_len, n.z/norm_len]))
            else:
                face_normals.append(np.array([0.0, 0.0, 1.0]))

        for side in flat_sides:
            face_vertices.append([])
            for point in side.points:
                np_point = _vec3_to_np(point)
                found = False
                for idx, existing in enumerate(vertices):
                    if _vec_isclose(np_point, existing, 0.1, 0.1):
                        face_vertices[-1].append(idx)
                        found = True
                        break
                if not found:
                    face_vertices[-1].append(len(vertices))
                    vertices.append(np_point)

        # process displacement sides
        self._disp_patches = []  # list of (grid_verts_2d, grid_uvrot_2d) for sub-grid patches
        self._disp_border_faces = []  # list of clipped polygon verts for border patches

        for side in disp_sides:
            self._process_displacement_side(side, origin, uv_rot_to_global_matrix, global_to_uv_rot_matrix)

        if len(vertices) == 0 and len(self._disp_patches) == 0 and len(self._disp_border_faces) == 0:
            self.empty = True
            return

        # clip flat side vertices against UV boundary (existing approach)
        if len(vertices) > 0:
            uv_rot_vertices = [global_to_uv_rot_matrix @ (v - origin) for v in vertices]
            remove_vertices = set()

            for side_vert_a, side_vert_b in uv_edges:
                cut_plane_normal = np.cross(up_vector, side_vert_b - side_vert_a)
                outside_vertices = {
                    i for i, v in enumerate(uv_rot_vertices)
                    if _distance_point_to_plane(v, side_vert_a, cut_plane_normal) > 0.001
                }
                if len(outside_vertices) == 0:
                    continue
                remove_vertices |= outside_vertices
                for face_vert_idxs in face_vertices:
                    if (all(v_idx not in outside_vertices for v_idx in face_vert_idxs)
                            or all(v_idx in outside_vertices for v_idx in face_vert_idxs)):
                        continue
                    inside_idx = next(i for i, v_idx in enumerate(face_vert_idxs) if v_idx not in outside_vertices)
                    while inside_idx > 0:
                        face_vert_idxs.append(face_vert_idxs.pop(0))
                        inside_idx -= 1
                    out_idx1 = next(i for i, v_idx in enumerate(face_vert_idxs) if v_idx in outside_vertices)
                    *_, out_idx2 = (i for i, v_idx in enumerate(face_vert_idxs) if v_idx in outside_vertices)
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
                    face_vert_idxs[out_idx1:out_idx2 + 1] = [new_vert_idx1, new_vert_idx2]

            # ensure no new vertices are outside
            for side_vert_a, side_vert_b in uv_edges:
                cut_plane_normal = np.cross(up_vector, side_vert_b - side_vert_a)
                remove_vertices |= {
                    i for i, v in enumerate(uv_rot_vertices)
                    if _distance_point_to_plane(v, side_vert_a, cut_plane_normal) > 0.001
                }

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
            for face_vert_idxs in old_face_vertices:
                if any(v_idx in remove_vertices for v_idx in face_vert_idxs):
                    continue
                face_vertices.append([vertice_idx_map[v_idx] for v_idx in face_vert_idxs])
        else:
            uv_rot_vertices = []

        if len(face_vertices) == 0 and len(self._disp_patches) == 0 and len(self._disp_border_faces) == 0:
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
            self.empty = True
            return

        u1, u2, v1, v2 = self.StartU, self.EndU, 1 - self.EndV, 1 - self.StartV
        coeff_matrix = np.array([
            [u1, u1, u2],
            [v2, v1, v1],
            [1, 1, 1]
        ], dtype=np.float64)

        try:
            coeffs = np.linalg.solve(coeff_matrix, np.array([u2, v2, 1.0]))
        except np.linalg.LinAlgError:
            self.empty = True
            return

        basis_to_uv = np.array([
            [coeffs[0] * u1, coeffs[1] * u1, coeffs[2] * u2],
            [coeffs[0] * v2, coeffs[1] * v1, coeffs[2] * v1],
            [coeffs[0], coeffs[1], coeffs[2]]
        ], dtype=np.float64)

        self._map_matrix = basis_to_uv @ global_to_basis
        self._global_to_uv_rot_matrix = global_to_uv_rot_matrix
        self._origin = origin

        # calculate texture coordinates for flat face vertices
        face_loop_uvs: List[List[Tuple[float, float]]] = []
        for face_vert_idxs in face_vertices:
            face_uvs: List[Tuple[float, float]] = []
            for vert_idx in face_vert_idxs:
                face_uvs.append(self._compute_uv(uv_rot_vertices[vert_idx]))
            face_loop_uvs.append(face_uvs)

        self.verts = list(vertices)
        self.face_vertices = face_vertices
        self.face_loop_uvs = face_loop_uvs

    def _compute_uv(self, uv_rot_vertex: np.ndarray) -> Tuple[float, float]:
        """Compute texture UV from a vertex in UV-rotation space."""
        v = uv_rot_vertex.copy()
        v[2] = 1.0
        product_vec = self._map_matrix @ v
        if abs(product_vec[2]) > 1e-10:
            return (product_vec[0] / product_vec[2], product_vec[1] / product_vec[2])
        return (0.0, 0.0)

    def _compute_uv_from_world(self, world_pos: np.ndarray) -> Tuple[float, float]:
        """Compute texture UV from a world-space position."""
        uv_rot = self._global_to_uv_rot_matrix @ (world_pos - self._origin)
        return self._compute_uv(uv_rot)

    def _process_displacement_side(self, side: Side, origin: np.ndarray,
                                    uv_rot_to_global: np.ndarray, global_to_uv_rot: np.ndarray):
        """Build displaced vertex grid, classify inside/outside, extract sub-grid and border faces."""
        disp = side.dispinfo
        power = int(disp["power"])
        num_verts = int(2 ** power) + 1
        points = side.points

        if len(points) != 4:
            return

        # face normal for winding order checks
        n = side.normal()
        face_normal = np.array([n.x, n.y, n.z], dtype=np.float64)
        norm_len = np.linalg.norm(face_normal)
        if norm_len > 0:
            face_normal /= norm_len

        # find start corner
        s = 0
        for i in range(4):
            if distance(points[i], disp["startpos"]) <= 1:
                s = i

        a = _vec3_to_np(points[s])
        b = _vec3_to_np(points[(s + 1) % 4])
        c = _vec3_to_np(points[(s + 2) % 4])
        d = _vec3_to_np(points[(s + 3) % 4])

        # build displaced vertex grid
        grid = []  # grid[row][col] = world position (np.ndarray)
        for i in range(num_verts):
            row = []
            ti = i / (num_verts - 1)
            edge_ab = _lerp_np(a, b, ti)
            edge_dc = _lerp_np(d, c, ti)
            for j in range(num_verts):
                tj = j / (num_verts - 1)
                base_pos = _lerp_np(edge_ab, edge_dc, tj)
                disp_normal = _vec3_to_np(disp["row"][j]["normals"][i])
                disp_dist = disp["row"][j]["distances"][i]
                elevation = np.array([0.0, 0.0, disp["elevation"]])
                world_pos = base_pos + elevation + disp_normal * disp_dist
                row.append(world_pos)
            grid.append(row)

        # classify each vertex as inside or outside the overlay slab
        inside = [[False] * num_verts for _ in range(num_verts)]
        for i in range(num_verts):
            for j in range(num_verts):
                pt = grid[i][j]
                is_inside = True
                for plane_point, plane_normal in self._slab_planes:
                    if np.dot(plane_normal, pt - plane_point) < -0.001:
                        is_inside = False
                        break
                inside[i][j] = is_inside

        # find bounding sub-grid of fully-inside vertices
        min_r, max_r = num_verts, -1
        min_c, max_c = num_verts, -1
        for i in range(num_verts):
            for j in range(num_verts):
                if inside[i][j]:
                    min_r = min(min_r, i)
                    max_r = max(max_r, i)
                    min_c = min(min_c, j)
                    max_c = max(max_c, j)

        if max_r < min_r:
            return  # no vertices inside

        # extract sub-grid patch (only fully-inside rows/cols)
        # shrink bounds to only include rows/cols where ALL vertices in the row/col range are inside
        inner_min_r, inner_max_r = max_r, min_r
        inner_min_c, inner_max_c = max_c, min_c
        for i in range(min_r, max_r + 1):
            all_inside = all(inside[i][j] for j in range(min_c, max_c + 1))
            if all_inside:
                inner_min_r = min(inner_min_r, i)
                inner_max_r = max(inner_max_r, i)
        for j in range(min_c, max_c + 1):
            all_inside = all(inside[i][j] for i in range(inner_min_r, inner_max_r + 1))
            if all_inside:
                inner_min_c = min(inner_min_c, j)
                inner_max_c = max(inner_max_c, j)

        has_inner = inner_max_r >= inner_min_r and inner_max_c >= inner_min_c
        if has_inner:
            sub_grid = []
            for i in range(inner_min_r, inner_max_r + 1):
                row = []
                for j in range(inner_min_c, inner_max_c + 1):
                    row.append(grid[i][j])
                sub_grid.append(row)
            if len(sub_grid) >= 2 and len(sub_grid[0]) >= 2:
                # check winding: first cell's cross product should align with face normal
                e1 = sub_grid[0][1] - sub_grid[0][0]
                e2 = sub_grid[1][0] - sub_grid[0][0]
                if np.dot(np.cross(e1, e2), face_normal) < 0:
                    # reverse row order to flip winding
                    sub_grid = sub_grid[::-1]
                self._disp_patches.append(sub_grid)

        # process border cells — cells that straddle the overlay boundary
        for i in range(num_verts - 1):
            for j in range(num_verts - 1):
                # skip cells fully inside the inner sub-grid
                if has_inner and (inner_min_r <= i and i + 1 <= inner_max_r and
                                  inner_min_c <= j and j + 1 <= inner_max_c):
                    continue

                cell_inside = [inside[i][j], inside[i][j+1], inside[i+1][j+1], inside[i+1][j]]
                cell_verts = [grid[i][j], grid[i][j+1], grid[i+1][j+1], grid[i+1][j]]

                if not any(cell_inside):
                    continue  # fully outside

                if all(cell_inside):
                    # fully inside but not part of inner grid — add as a quad
                    face = list(cell_verts)
                    self._disp_border_faces.append(_ensure_winding(face, face_normal))
                else:
                    # partially inside — clip the quad against slab planes
                    clipped = _clip_polygon_by_planes(list(cell_verts), self._slab_planes)
                    if len(clipped) >= 3:
                        self._disp_border_faces.append(_ensure_winding(clipped, face_normal))

    @staticmethod
    def _rows_match(row_a: List[PatchVert], row_b: List[PatchVert], tol: float = 0.1) -> bool:
        """Check if two patch rows have the same vertex positions (within tolerance)."""
        if len(row_a) != len(row_b):
            return False
        for va, vb in zip(row_a, row_b):
            dx = abs(va.pos.x - vb.pos.x)
            dy = abs(va.pos.y - vb.pos.y)
            dz = abs(va.pos.z - vb.pos.z)
            if dx > tol or dy > tol or dz > tol:
                return False
        return True

    @staticmethod
    def _weld_patches(patches: List[Patch]) -> List[Patch]:
        """Recursively merge patches that share a row edge until no more merges are possible."""
        merged = True
        while merged:
            merged = False
            i = 0
            while i < len(patches):
                j = i + 1
                while j < len(patches):
                    a = patches[i]
                    b = patches[j]
                    # only merge patches with the same column count
                    if len(a.verts) == 0 or len(b.verts) == 0:
                        j += 1
                        continue
                    if len(a.verts[0]) != len(b.verts[0]):
                        j += 1
                        continue

                    result = None
                    # a's last row == b's first row
                    if Overlay._rows_match(a.verts[-1], b.verts[0]):
                        result = Patch(type=a.type, texture=a.texture, lightmap=a.lightmap,
                                       size=(len(a.verts) + len(b.verts) - 1, len(a.verts[0])),
                                       samplesize=a.samplesize)
                        result.nolightmap = a.nolightmap
                        result.verts = a.verts + b.verts[1:]
                    # b's last row == a's first row
                    elif Overlay._rows_match(b.verts[-1], a.verts[0]):
                        result = Patch(type=a.type, texture=a.texture, lightmap=a.lightmap,
                                       size=(len(b.verts) + len(a.verts) - 1, len(a.verts[0])),
                                       samplesize=a.samplesize)
                        result.nolightmap = a.nolightmap
                        result.verts = b.verts + a.verts[1:]

                    if result is not None:
                        patches[i] = result
                        patches.pop(j)
                        merged = True
                        # don't increment j, recheck from same position
                    else:
                        j += 1
                i += 1
        return patches

    def _fix_patch_winding(self, patch: Patch):
        """Check if a patch faces away from BasisNormal and flip columns if so."""
        if len(patch.verts) < 2 or len(patch.verts[0]) < 2:
            return
        # check winding using first quad of the patch
        p00 = patch.verts[0][0].pos
        p01 = patch.verts[0][1].pos
        p10 = patch.verts[1][0].pos
        e1 = vec3(p01.x - p00.x, p01.y - p00.y, p01.z - p00.z)
        e2 = vec3(p10.x - p00.x, p10.y - p00.y, p10.z - p00.z)
        cross = glm_cross(e1, e2)
        basis = vec3(float(self.BasisNormal[0]), float(self.BasisNormal[1]), float(self.BasisNormal[2]))
        from glm import dot
        if dot(cross, basis) > 0:
            # flip by reversing columns in each row
            for row in patch.verts:
                row.reverse()

    def to_patches(self) -> List[Patch]:
        """Convert the overlay to a list of CoD patches."""
        if self.empty:
            return []

        patches = []
        tex_scale = vec2(1024, -1024)
        mat = newPath(self.material)

        # flat side patches
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

            self._fix_patch_winding(patch)
            patches.append(patch)

        # displacement sub-grid patches
        for sub_grid in self._disp_patches:
            rows = len(sub_grid)
            cols = len(sub_grid[0])

            patch = Patch(type="mesh", texture=mat, lightmap="lightmap_gray", size=(rows, cols), samplesize=16)
            patch.nolightmap = True

            for i in range(rows):
                row = []
                for j in range(cols):
                    world_pos = sub_grid[i][j]
                    uv = self._compute_uv_from_world(world_pos)
                    pos = vec3(float(world_pos[0]), float(world_pos[1]), float(world_pos[2])) * self.scale
                    uv_scaled = vec2(float(uv[0]), float(uv[1])) * tex_scale
                    row.append(PatchVert(pos, uv_scaled, vec2(0, 0)))
                patch.verts.append(row)

            self._fix_patch_winding(patch)
            patches.append(patch)

        # displacement border face patches (clipped quads/triangles)
        for face_verts in self._disp_border_faces:
            verts = list(face_verts)
            uvs = [self._compute_uv_from_world(v) for v in verts]

            if len(verts) < 3:
                continue

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

                pos1 = vec3(float(p1[0]), float(p1[1]), float(p1[2])) * self.scale
                uv1_scaled = vec2(float(uv1[0]), float(uv1[1])) * tex_scale
                pos2 = vec3(float(p2[0]), float(p2[1]), float(p2[2])) * self.scale
                uv2_scaled = vec2(float(uv2[0]), float(uv2[1])) * tex_scale

                patch.verts.append([
                    PatchVert(pos1, uv1_scaled, vec2(0, 0)),
                    PatchVert(pos2, uv2_scaled, vec2(0, 0)),
                ])

            self._fix_patch_winding(patch)
            patches.append(patch)

        return self._weld_patches(patches)
