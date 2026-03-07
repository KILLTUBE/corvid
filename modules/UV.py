from __future__ import annotations
import numpy as np
from numpy.linalg import solve
from typing import TYPE_CHECKING, List
from math import fabs, cos, sin, radians, degrees, atan2, sqrt
from glm import vec3, vec2, dot, normalize

if TYPE_CHECKING:
    from .Side import Side

class CoDUV:
    """
    Texture alignment format used by Call of Duty 2 and onwards.
    """
    __slots__ = ("parent", "x_scale", "y_scale", "x_offset", "y_offset", "rotation")
    
    parent: 'Side'
    x_scale: float
    y_scale: float
    x_offset: float
    y_offset: float
    rotation: float

    def __init__(self, parent: 'Side' = None) -> None:
        self.parent = parent
        self.x_scale = 1.0
        self.y_scale = 1.0
        self.x_offset = 0.0
        self.y_offset = 0.0
        self.rotation = 0.0

    def get_projection_coords(self, vertex: vec3) -> vec2:
        """
        Calculates the axis-aligned projection coordinates for a vertex based on the normal.
        """
        normal = normalize(self.parent.normal())
        UP, RIGHT, FORWARD = vec3(0, 0, 1), vec3(0, 1, 0), vec3(1, 0, 0)
        du, dr, df = fabs(dot(normal, UP)), fabs(dot(normal, RIGHT)), fabs(dot(normal, FORWARD))

        if du >= dr and du >= df:
            return vec2(vertex.x, -vertex.y)
        elif dr >= du and dr >= df:
            return vec2(vertex.x, -vertex.z)
        else:
            return vec2(vertex.y, -vertex.z)

    def get_uv(self, vertex: vec3) -> vec2:
        """
        Calculates the UV coordinates for a vertex based on the normal and texture size.
        """
        uv = self.get_projection_coords(vertex)
        tex_size = vec2(512, 512) # Radiant convention

        if self.rotation != 0:
            angle = radians(self.rotation)
            cos_a, sin_a = cos(angle), sin(angle)
            orig_x, orig_y = uv.x, uv.y
            uv.x = orig_x * cos_a - orig_y * sin_a
            uv.y = orig_x * sin_a + orig_y * cos_a

        uv.x -= self.x_offset
        uv.y -= self.y_offset
        
        if self.x_scale != 0:
            uv.x /= self.x_scale / 512
        if self.y_scale != 0:
            uv.y /= self.y_scale / 512
            
        uv.x /= tex_size.x
        uv.y /= tex_size.y

        return uv

    @classmethod
    def fit(cls, side: 'Side', vertices: List[vec3], uvs: List[vec2]) -> CoDUV:
        """
        Calculates CoD UV parameters (scale, offset, rotation) from a set of vertex-UV pairs.
        Needs at least 3 non-collinear vertices.
        """
        if len(vertices) < 3:
            raise ValueError("Fitting requires at least 3 vertices.")

        instance = cls(side)
        tex_size = vec2(512, 512)

        # Project vertices to 2D based on normal
        proj_pts = [instance.get_projection_coords(v) for v in vertices]

        # We need to solve:
        # u = a1*x + a2*y + a3
        # v = a4*x + a5*y + a6
        # where (x, y) are proj_pts
        
        # Build matrix M and targets T for u and v
        M = []
        Tu = []
        Tv = []
        for i in range(3):
            p = proj_pts[i]
            M.append([p.x, p.y, 1.0])
            Tu.append(uvs[i].x)
            Tv.append(uvs[i].y)

        try:
            A_u = solve(M, Tu) # [a1, a2, a3]
            A_v = solve(M, Tv) # [a4, a5, a6]
        except np.linalg.LinAlgError:
            # Fallback for collinear points or other issues
            return instance

        a1, a2, a3 = A_u
        a4, a5, a6 = A_v

        # Robust decomposition
        # Calculate x_scale and rotation from first axis
        kx = sqrt(a1**2 + a2**2)
        if kx > 1e-9:
            instance.x_scale = 512 / (kx * tex_size.x)
            angle = atan2(-a2, a1)
            instance.rotation = round(degrees(angle), 3)
            # Normalize rotation to [0, 360)
            if instance.rotation < 0:
                instance.rotation += 360.0
            if instance.rotation == 360.0:
                instance.rotation = 0.0
                
            instance.x_offset = -a3 / kx
            
            # Now determine y_scale using the found rotation
            # a4 = ky * sin(a), a5 = ky * cos(a)
            # Use projection to find signed ky
            ky = a4 * sin(angle) + a5 * cos(angle)
            if abs(ky) > 1e-9:
                instance.y_scale = 512 / (ky * tex_size.y)
                instance.y_offset = -a6 / ky
            else:
                instance.y_scale = 1.0
                instance.y_offset = 0.0
        else:
            instance.x_scale = 1.0
            instance.y_scale = 1.0
            instance.rotation = 0.0
            instance.x_offset = 0.0
            instance.y_offset = 0.0

        return instance
