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


def _inverse_bilinear_2d(q: np.ndarray, p0: np.ndarray, p1: np.ndarray,
                         p2: np.ndarray, p3: np.ndarray) -> Tuple[float, float]:
    """Find (s, t) such that bilinear interpolation across the four 2D corners
    p0,p1,p2,p3 (mapped to (0,0),(0,1),(1,1),(1,0)) gives q.

    Solves the standard quadratic from
        q = (1-s)(1-t) p0 + (1-s)t p1 + s t p2 + s(1-t) p3
    by viewing q as lying on the line lerp(p0,p3,s)→lerp(p1,p2,s) for some s,
    and requiring that line to pass through q. Falls back to the linear case
    when the warp term is ~0 (parallelogram)."""
    a = p3 - p0           # ∂q/∂s at t=0
    b = p1 - p0           # ∂q/∂t at s=0
    h = p2 - p3 - p1 + p0 # warp; zero for parallelograms
    d = q - p0

    def cross2(u, v):
        return u[0] * v[1] - u[1] * v[0]

    qa = -cross2(a, h)
    qb = cross2(d, h) - cross2(a, b)
    qc = cross2(d, b)

    if abs(qa) < 1e-12:
        s = -qc / qb if abs(qb) > 1e-12 else 0.0
    else:
        disc = qb * qb - 4.0 * qa * qc
        if disc < 0.0:
            disc = 0.0
        sq = disc ** 0.5
        s1 = (-qb + sq) / (2.0 * qa)
        s2 = (-qb - sq) / (2.0 * qa)
        # pick the root in (or closest to) [0,1]
        def clamp_dist(x):
            if x < 0.0: return -x
            if x > 1.0: return x - 1.0
            return 0.0
        s = s1 if clamp_dist(s1) <= clamp_dist(s2) else s2

    m = p0 + s * a              # = lerp(p0, p3, s)
    n = p1 + s * (p2 - p1)      # = lerp(p1, p2, s)
    mn = n - m
    denom = mn[0] * mn[0] + mn[1] * mn[1]
    if denom < 1e-12:
        t = 0.0
    else:
        qm = q - m
        t = (qm[0] * mn[0] + qm[1] * mn[1]) / denom
    return float(s), float(t)


class Overlay:
    def __init__(self, entity: Dict[str, str], sideDict: Dict[str, Side], matSizes, scale: float = 1.0, origin: vec3 = None, offsetScale: float = None):
        """origin and scale transform the Source positions the same way as the brushes they're placed on
        (e.g. the 3d skybox's origin and scale). offsetScale is used for the z-offset and defaults to scale."""
        self.id = entity["id"]
        self.BasisNormal = _parse_vec3(entity["BasisNormal"])
        self.BasisOrigin = _parse_vec3(entity["BasisOrigin"])
        self.BasisU = _parse_vec3(entity["BasisU"])
        self.BasisV = _parse_vec3(entity["BasisV"])
        self.EndU = float(entity["EndU"])
        self.EndV = float(entity["EndV"])
        self.material = entity["material"]
        self.scale = scale
        self.mapOrigin = vec3(origin) if origin is not None else vec3(0, 0, 0)
        self.offsetScale = offsetScale if offsetScale is not None else scale
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
        # centroid of the UV quad (in overlay-local space) — used to pick the inward
        # plane normal regardless of whether uv_points are wound CW or CCW.
        uv_centroid = sum(self.uv_points) / 4.0
        world_centroid = origin + uv_rot_to_global_matrix @ uv_centroid
        self._slab_planes = []
        for side_vert_a, side_vert_b in uv_edges:
            cut_normal_uv = np.cross(up_vector, side_vert_b - side_vert_a)
            world_normal = uv_rot_to_global_matrix @ cut_normal_uv
            norm_len = np.linalg.norm(world_normal)
            if norm_len > 0:
                world_normal /= norm_len
            world_point = origin + uv_rot_to_global_matrix @ side_vert_a
            # flip if needed so the normal points toward the overlay's interior
            if np.dot(world_normal, world_centroid - world_point) < 0:
                world_normal = -world_normal
            self._slab_planes.append((world_point, world_normal))

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
            self._flat_faces.append((clipped, face_normal))

        # process displacement sides
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
        """Compute texture UV by projecting onto the overlay plane and inverse-bilinear-
        interpolating within the UV quad (matches Source's runtime overlay behaviour for
        non-rectangular UV handles)."""
        # project world point onto overlay plane
        delta = world_point - self._origin
        dist = np.dot(self._basis_normal, delta)
        plane_point = world_point - dist * self._basis_normal

        # get 2D overlay-local coordinates
        local = self._global_to_uv_rot_matrix @ (plane_point - self._origin)

        # uv0 → s=0,t=0; uv1 → s=0,t=1; uv2 → s=1,t=1; uv3 → s=1,t=0
        s, t = _inverse_bilinear_2d(
            local[:2],
            self.uv_points[0][:2], self.uv_points[1][:2],
            self.uv_points[2][:2], self.uv_points[3][:2],
        )

        u = self.StartU + s * (self.EndU - self.StartU)
        # CoD's V axis points up, Source's points down — invert to match.
        v = 1.0 - (self.StartV + t * (self.EndV - self.StartV))
        return (u, v)

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
                # don't reorient: any row/column reversal flips Patch.Triangulate's
                # diagonal direction in every cell, which desyncs the overlay's
                # triangulation from the underlying displacement and causes cracks.
                # MapExporter.convertDisplacement also relies on the natural a→b→c→d order.
                self._disp_patches.append((sub_grid, face_normal))

        # process border cells — clip each cell as the two triangles that
        # Patch.Triangulate would emit (anti-diagonal: top-right→bottom-left),
        # so the clipped polygon stays on the actual displacement surface
        # instead of cutting through it.
        for i in range(num_verts - 1):
            for j in range(num_verts - 1):
                # skip cells fully inside the inner sub-grid
                if has_inner and (inner_min_r <= i and i + 1 <= inner_max_r and
                                  inner_min_c <= j and j + 1 <= inner_max_c):
                    continue

                if not (inside[i][j] or inside[i][j+1] or inside[i+1][j] or inside[i+1][j+1]):
                    continue  # fully outside the slab

                # Triangle 1: (i+1,j), (i,j+1), (i,j)  [matches Patch.Triangulate, k=j]
                # Triangle 2: (i+1,j), (i+1,j+1), (i,j+1)  [matches Patch.Triangulate at k=j+1]
                for tri in (
                    [grid[i+1][j], grid[i][j+1], grid[i][j]],
                    [grid[i+1][j], grid[i+1][j+1], grid[i][j+1]],
                ):
                    clipped = _clip_polygon_by_planes(list(tri), self._slab_planes)
                    if len(clipped) >= 3:
                        self._disp_border_faces.append(
                            (_ensure_winding(clipped, face_normal), face_normal))

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

    def _build_patch_from_polygon(self, verts, uvs, mat, tex_scale, offset=vec3(0)):
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

            pos1 = self._transform(p1) + offset
            uv1_scaled = vec2(float(uv1[0]), float(uv1[1])) * tex_scale
            pos2 = self._transform(p2) + offset
            uv2_scaled = vec2(float(uv2[0]), float(uv2[1])) * tex_scale

            patch.verts.append([
                PatchVert(pos1, uv1_scaled, vec2(0, 0)),
                PatchVert(pos2, uv2_scaled, vec2(0, 0)),
            ])

        self._fix_patch_winding(patch)
        return patch

    def _transform(self, p) -> vec3:
        """Convert a Source position to a CoD position."""
        return (vec3(float(p[0]), float(p[1]), float(p[2])) - self.mapOrigin) * self.scale

    def _face_offset(self, face_normal, zOffset):
        """Compute outward offset from a numpy face normal. Negated because side.normal() points inward."""
        n = vec3(float(face_normal[0]), float(face_normal[1]), float(face_normal[2]))
        return n * -(zOffset) * self.offsetScale

    def to_patches(self, zOffset=0.0, maxPatchSize: int = 30) -> List[Patch]:
        """Convert the overlay to a list of CoD patches.

        maxPatchSize bounds the row/column count of any emitted patch — power-4
        displacements (17 verts/side), heavily-clipped flat faces, and welded
        chains can all blow past CoD4/CoD2's 9-vert limit, so the caller passes
        9 for those games."""
        if self.empty:
            return []

        patches = []
        tex_scale = vec2(1024, -1024)
        mat = newPath(self.material)

        # flat side patches
        for face_verts, face_normal in self._flat_faces:
            offset = self._face_offset(face_normal, zOffset)
            verts = list(face_verts)
            uvs = [self._compute_uv_from_world(v) for v in verts]
            patch = self._build_patch_from_polygon(verts, uvs, mat, tex_scale, offset)
            if patch is not None:
                patches.append(patch)

        # displacement sub-grid patches
        for sub_grid, face_normal in self._disp_patches:
            offset = self._face_offset(face_normal, zOffset)
            rows = len(sub_grid)
            cols = len(sub_grid[0])

            patch = Patch(type="mesh", texture=mat, lightmap="lightmap_gray", size=(rows, cols), samplesize=16)
            patch.nolightmap = True

            for i in range(rows):
                row = []
                for j in range(cols):
                    world_pos = sub_grid[i][j]
                    uv = self._compute_uv_from_world(world_pos)
                    pos = self._transform(world_pos) + offset
                    uv_scaled = vec2(float(uv[0]), float(uv[1])) * tex_scale
                    row.append(PatchVert(pos, uv_scaled, vec2(0, 0)))
                patch.verts.append(row)

            # No _fix_patch_winding here: reversing rows/cols would flip Patch.Triangulate's
            # diagonal and desync the overlay from the underlying displacement.
            patches.append(patch)

        # displacement border face patches — already clipped per displacement
        # triangle, so each polygon lies on the actual surface.
        for face_verts, face_normal in self._disp_border_faces:
            offset = self._face_offset(face_normal, zOffset)
            verts = list(face_verts)
            uvs = [self._compute_uv_from_world(v) for v in verts]
            patch = self._build_patch_from_polygon(verts, uvs, mat, tex_scale, offset)
            if patch is not None:
                patches.append(patch)

        welded = self._weld_patches(patches)
        if maxPatchSize and maxPatchSize > 1:
            sliced: List[Patch] = []
            for p in welded:
                sliced.extend(p.Slice(maxPatchSize))
            return sliced
        return welded
