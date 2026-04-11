from __future__ import annotations
import math
import numpy as np
from typing import List
from glm import vec3, vec2, dot, normalize


def fit_uvs(vertices: List[vec3], uvs: List[vec2], normal: vec3):
    """
    Compute CoD UV parameters from 3 vertices, their UVs, and face normal.
    CoD Radiant treats all textures as 512x512.
    Returns (h_scale, v_scale, h_offset, v_offset, rotation).
    """
    fallback = (128.0, 128.0, 0.0, 0.0, 0.0)

    # Project vertices to 2D using CoD's axis convention
    n = normalize(normal)
    UP, RIGHT, FORWARD = vec3(0, 0, 1), vec3(0, 1, 0), vec3(1, 0, 0)
    du, dr, df = abs(dot(n, UP)), abs(dot(n, RIGHT)), abs(dot(n, FORWARD))

    def project(v):
        if du >= dr and du >= df:
            return (v.x, -v.y)
        elif df >= du and df >= dr:
            return (v.y, -v.z)
        else:
            return (v.x, -v.z)

    proj = [project(v) for v in vertices[:3]]

    # Solve affine system:
    #   uv.x = a1*px + a2*py + a3
    #   uv.y = a4*px + a5*py + a6
    M = np.array([[p[0], p[1], 1.0] for p in proj])

    try:
        a1, a2, a3 = np.linalg.solve(M, [uvs[i].x for i in range(3)])
        a4, a5, a6 = np.linalg.solve(M, [uvs[i].y for i in range(3)])
    except np.linalg.LinAlgError:
        return fallback

    # Decompose: a1 = c/sx, a2 = -s/sx => rotation = atan2(-a2, a1)
    kx = math.sqrt(a1**2 + a2**2)
    if kx < 1e-9:
        return fallback

    angle = math.atan2(-a2, a1)
    rotation = math.degrees(angle)
    if rotation < 0:
        rotation += 360.0
    if rotation == 360.0:
        rotation = 0.0

    # y-scale with sign: ky = a4*sin(angle) + a5*cos(angle) = 1/sy
    ky = a4 * math.sin(angle) + a5 * math.cos(angle)
    if abs(ky) < 1e-9:
        return fallback

    # Radiant assumes 512x512, so scale = 1/k directly
    x_scale = round(1.0 / kx)
    y_scale = round(1.0 / ky)
    rotation = round(rotation)

    # Recompute offset from vertex 0 using the rounded rotation and scale,
    # since the .map format writes these as integers. Computing offset against
    # the rounded values ensures consistency with what CoD Radiant actually uses.
    if x_scale == 0 or y_scale == 0:
        return fallback

    p0 = proj[0]
    angle_r = math.radians(rotation)
    cos_a, sin_a = math.cos(angle_r), math.sin(angle_r)
    r0_x = p0[0] * cos_a - p0[1] * sin_a
    r0_y = p0[0] * sin_a + p0[1] * cos_a

    x_offset = r0_x - uvs[0].x * x_scale
    y_offset = r0_y - uvs[0].y * y_scale

    return (x_scale, y_scale, x_offset, y_offset, rotation)
