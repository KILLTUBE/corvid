from typing import Dict, List, Tuple

import numpy as np
from glm import vec2, vec3, cross as glm_cross, distance

from modules.Static import newPath
from .Side import Side
from .CoDMap.Patch import Patch, PatchVert


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


def _project_point_onto_triangle(point: np.ndarray, v0: np.ndarray, v1: np.ndarray, v2: np.ndarray):
    """Project a point onto a triangle's plane. Returns projected point if it falls
    within the triangle (with tolerance), otherwise None."""
    e1 = v1 - v0
    e2 = v2 - v0
    tri_normal = np.cross(e1, e2)
    norm_sq = np.dot(tri_normal, tri_normal)
    if norm_sq < 1e-12:
        return None

    # project point onto triangle plane
    dist = np.dot(tri_normal, point - v0) / norm_sq
    projected = point - dist * tri_normal

    # barycentric coordinates to check if inside triangle
    d = projected - v0
    d11 = np.dot(e1, e1)
    d12 = np.dot(e1, e2)
    d22 = np.dot(e2, e2)
    d1p = np.dot(e1, d)
    d2p = np.dot(e2, d)
    denom = d11 * d22 - d12 * d12
    if abs(denom) < 1e-12:
        return None

    u = (d22 * d1p - d12 * d2p) / denom
    v = (d11 * d2p - d12 * d1p) / denom

    tol = 0.01
    if u >= -tol and v >= -tol and (u + v) <= 1.0 + tol:
        return projected
    return None


class Overlay:
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
        self.empty = False
        self._flat_faces = []
        self._disp_patches = []
        self._disp_border_faces = []

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

        # matrix to convert coords from overlay-local space to world space
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

        # clip each flat side polygon against overlay bounds using Sutherland-Hodgman
        for side in flat_sides:
            side_polygon = [_vec3_to_np(p) for p in side.points]
            clipped = _clip_polygon_by_planes(side_polygon, self._slab_planes)
            if len(clipped) < 3:
                continue
            n = side.normal()
            face_normal = np.array([n.x, n.y, n.z], dtype=np.float64)
            norm_len = np.linalg.norm(face_normal)
            if norm_len > 0:
                face_normal /= norm_len
            clipped = _ensure_winding(clipped, face_normal)
            self._flat_faces.append(clipped)

        # process displacement sides
        self._disp_grids = []  # store full grids for surface projection
        for side in disp_sides:
            self._process_displacement_side(side, origin, uv_rot_to_global_matrix, global_to_uv_rot_matrix)

        if len(self._flat_faces) == 0 and len(self._disp_patches) == 0 and len(self._disp_border_faces) == 0:
            self.empty = True
            return

        # store data needed for UV computation
        self._origin = origin
        self._basis_normal = normal.copy()
        norm_len = np.linalg.norm(self._basis_normal)
        if norm_len > 0:
            self._basis_normal /= norm_len
        self._global_to_uv_rot_matrix = global_to_uv_rot_matrix

    def _compute_uv_from_world(self, world_point: np.ndarray) -> Tuple[float, float]:
        """Compute texture UV by projecting onto overlay plane and using bilinear interpolation
        within the UV quad, matching the Source engine's approach."""
        # project world point onto overlay plane
        delta = world_point - self._origin
        dist = np.dot(self._basis_normal, delta)
        plane_point = world_point - dist * self._basis_normal

        # get 2D overlay-local coordinates
        local = self._global_to_uv_rot_matrix @ (plane_point - self._origin)

        # find parametric (s, t) within the UV quad
        # uv0 → s=0,t=0; uv1 → s=0,t=1; uv2 → s=1,t=1; uv3 → s=1,t=0
        p0 = self.uv_points[0][:2]
        edge_s = self.uv_points[3][:2] - p0  # s direction: uv0 → uv3
        edge_t = self.uv_points[1][:2] - p0  # t direction: uv0 → uv1

        d = local[:2] - p0

        s_denom = np.dot(edge_s, edge_s)
        t_denom = np.dot(edge_t, edge_t)

        s = np.dot(d, edge_s) / s_denom if s_denom > 1e-10 else 0.0
        t = np.dot(d, edge_t) / t_denom if t_denom > 1e-10 else 0.0

        u = self.StartU + s * (self.EndU - self.StartU)
        v = 1.0 - (self.StartV + t * (self.EndV - self.StartV))
        return (u, v)

    def _project_onto_disp_surface(self, point: np.ndarray) -> np.ndarray:
        """Project a point onto the nearest triangle in the displacement grids.
        Uses the same triangulation pattern as CoD's Patch.Triangulate()."""
        best_point = point
        best_dist = float('inf')

        for grid in self._disp_grids:
            rows = len(grid)
            cols = len(grid[0])
            for i in range(rows - 1):
                for k in range(cols):
                    # triangle 1: (i+1,k), (i,k+1), (i,k) — matches Patch.Triangulate
                    if k < cols - 1:
                        projected = _project_point_onto_triangle(
                            point, grid[i+1][k], grid[i][k+1], grid[i][k])
                        if projected is not None:
                            d = np.linalg.norm(projected - point)
                            if d < best_dist:
                                best_dist = d
                                best_point = projected
                    # triangle 2: (i+1,k-1), (i+1,k), (i,k)
                    if k > 0:
                        projected = _project_point_onto_triangle(
                            point, grid[i+1][k-1], grid[i+1][k], grid[i][k])
                        if projected is not None:
                            d = np.linalg.norm(projected - point)
                            if d < best_dist:
                                best_dist = d
                                best_point = projected

        return best_point

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

        self._disp_grids.append(grid)

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

    def _build_patch_from_polygon(self, verts, uvs, mat, tex_scale):
        """Build a CoD patch mesh from a clipped polygon and its UVs."""
        if len(verts) < 3:
            return None

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
        return patch

    def to_patches(self) -> List[Patch]:
        """Convert the overlay to a list of CoD patches."""
        if self.empty:
            return []

        patches = []
        tex_scale = vec2(1024, -1024)
        mat = newPath(self.material)

        # flat side patches
        for face_verts in self._flat_faces:
            verts = list(face_verts)
            uvs = [self._compute_uv_from_world(v) for v in verts]
            patch = self._build_patch_from_polygon(verts, uvs, mat, tex_scale)
            if patch is not None:
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
        # project vertices onto displacement triangles to match CoD's triangulation
        for face_verts in self._disp_border_faces:
            verts = [self._project_onto_disp_surface(v) for v in face_verts]
            uvs = [self._compute_uv_from_world(v) for v in verts]
            patch = self._build_patch_from_polygon(verts, uvs, mat, tex_scale)
            if patch is not None:
                patches.append(patch)

        return self._weld_patches(patches)
