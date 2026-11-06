from __future__ import annotations
import math
import numpy as np
from typing import List
from glm import vec3, vec2


# CoD Radiant's axial texture planes (q3radiant's baseaxis): a normal, then the s and t texture axes.
# Order matters: when two planes are equally close, the first one wins.
_BASE_AXIS = (
    ((0, 0, 1), (1, 0, 0), (0, -1, 0)),
    ((0, 0, -1), (1, 0, 0), (0, -1, 0)),
    ((1, 0, 0), (0, 1, 0), (0, 0, -1)),
    ((-1, 0, 0), (0, 1, 0), (0, 0, -1)),
    ((0, 1, 0), (1, 0, 0), (0, 0, -1)),
    ((0, -1, 0), (1, 0, 0), (0, 0, -1)),
)


def _texture_axes(normal: vec3):
    """
    Same as Radiant's TextureAxisIndices: returns the coordinate index each texture axis runs
    along (sv, tv) and the sign of that axis (xs, ys).
    """
    best, bestAxis = 0.0, 0
    for i, (n, _, _) in enumerate(_BASE_AXIS):
        d = normal.x * n[0] + normal.y * n[1] + normal.z * n[2]
        if d > best:
            best, bestAxis = d, i
    _, xv, yv = _BASE_AXIS[bestAxis]
    sv = next(i for i in range(3) if xv[i] != 0)
    tv = next(i for i in range(3) if yv[i] != 0)
    return sv, tv, xv[sv], yv[tv]


def fit_uvs(vertices: List[vec3], uvs: List[vec2], normal: vec3):
    """
    Compute CoD texture parameters for a brush face from its vertices and their UVs.
    UVs are in texture repeats (1.0 = one full texture), the same unit Radiant uses.

    This is the inverse of how Radiant builds a face's texture matrix (Texdef_GetMatrix), done
    the same way Radiant itself does it (Face_UVsToTexdefs -> Texdef_FromSolved). Since the texture
    definition has 6 parameters including shear, any affine Source texture mapping can be
    represented exactly, including skewed texture axes.
    Unlike Radiant, nothing is snapped to "nice" values: a tiny scale change gets multiplied by the
    distance from the origin, which can shift textures by several pixels on large maps.
    Returns (h_scale, v_scale, h_shift, v_shift, rotation, shear).
    """
    fallback = (128.0, 128.0, 0.0, 0.0, 0.0, 0.0)

    if len(vertices) < 3 or len(vertices) != len(uvs):
        return fallback

    nLen = math.sqrt(normal.x ** 2 + normal.y ** 2 + normal.z ** 2)
    if nLen < 1e-12:
        return fallback
    n = vec3(normal.x / nLen, normal.y / nLen, normal.z / nLen)
    sv, tv, xs, ys = _texture_axes(n)

    # Texture coordinates are an affine function of the two coordinates the axial plane keeps:
    #   u = A * P[sv] + B * P[tv] + C
    #   v = D * P[sv] + E * P[tv] + F
    # Every vertex is used (least squares), so slivers and nearly collinear points don't matter.
    M = np.array([[float(p[sv]), float(p[tv]), 1.0] for p in vertices])
    U = np.array([float(uv.x) for uv in uvs])
    V = np.array([float(uv.y) for uv in uvs])
    (A, B, C), _, rankU, _ = np.linalg.lstsq(M, U, rcond=None)
    (D, E, F), _, rankV, _ = np.linalg.lstsq(M, V, rcond=None)
    if rankU < 3 or rankV < 3:
        return fallback

    # rows of the texture matrix along the s and t axes
    S = [0.0, 0.0, 0.0]
    T = [0.0, 0.0, 0.0]
    S[sv], S[tv] = A, B
    T[sv], T[tv] = D, E

    tLen2 = T[0] ** 2 + T[1] ** 2 + T[2] ** 2
    if tLen2 < 1e-18:
        return fallback

    # the part of s that runs along t is the shear
    shear = (S[0] * T[0] + S[1] * T[1] + S[2] * T[2]) / tLen2
    S = [S[i] - shear * T[i] for i in range(3)]

    sLen = math.sqrt(S[0] ** 2 + S[1] ** 2 + S[2] ** 2)
    if sLen < 1e-9:
        return fallback
    xScale = 1.0 / sLen
    yScale = 1.0 / math.sqrt(tLen2)
    # mirrored textures get a negative vertical scale
    if (T[tv] * (S[sv] * xs)) * ys - (T[sv] * (S[tv] * xs)) * ys < 0.0:
        yScale = -yScale

    rotation = math.degrees(math.atan2(S[tv] * xs, S[sv] * xs))
    rotation %= 360.0

    # The texture repeats every |scale| units, so wrap the shifts into a single repeat.
    # This keeps them small, so they don't lose precision on faces far away from the origin.
    xShift = math.fmod(-C * xScale, abs(xScale))
    yShift = math.fmod(-F * yScale, abs(yScale))

    return (xScale, yScale, xShift, yShift, rotation, shear)
