from math import sin, cos, sqrt, tan

from typing import List

class Matrix4x4:
    values: List[float]

    def __init__(self, values: List[float]) -> None:
        if len(values) != 16:
            print("Matrix4x4 expects 16 values")
            exit()
        self.values = values
    
    def __getitem__(self, i: int):
        return self.values[i]
    
    def __setitem__(self, i: int, val: float):
        self.values[i] = val

    def __str__(self) -> str:
        res = ""
        for i in range(0, 16, 4):
            res += f"[ {self[i]} {self[i + 1]} {self[i + 2]} {self[i + 3]} ]\n"
        return res

    def __add__(self, rhs):
        return Matrix4x4([
            self[0] + rhs[0],  self[1] + rhs[1], self[2] + rhs[2], self[3] + rhs[3],
            self[4] + rhs[4],  self[5] + rhs[5], self[6] + rhs[6], self[7] + rhs[7],
            self[8] + rhs[8],  self[9] + rhs[9], self[10] + rhs[10], self[11] + rhs[11],
            self[12] + rhs[12],  self[13] + rhs[13], self[14] + rhs[14], self[15] + rhs[15]
        ])

    def __sub__(self, rhs):
        return Matrix4x4([
            self[0] - rhs[0],  self[1] - rhs[1], self[2] - rhs[2], self[3] - rhs[3],
            self[4] - rhs[4],  self[5] - rhs[5], self[6] - rhs[6], self[7] - rhs[7],
            self[8] - rhs[8],  self[9] - rhs[9], self[10] - rhs[10], self[11] - rhs[11],
            self[12] - rhs[12],  self[13] - rhs[13], self[14] - rhs[14], self[15] - rhs[15]
        ])
    
    def __mul__(self, rhs):
        return Matrix4x4([
            self[0] * rhs[0] + self[1] * rhs[4] + self[2] * rhs[8] + self[3] * rhs[12],
            self[0] * rhs[1] + self[1] * rhs[5] + self[2] * rhs[9] + self[3] * rhs[13],
            self[0] * rhs[2] + self[1] * rhs[6] + self[2] * rhs[10] + self[3] * rhs[14],
            self[0] * rhs[3] + self[1] * rhs[7] + self[2] * rhs[11] + self[3] * rhs[15],
            self[4] * rhs[0] + self[5] * rhs[4] + self[6] * rhs[8] + self[7] * rhs[12],
            self[4] * rhs[1] + self[5] * rhs[5] + self[6] * rhs[9] + self[7] * rhs[13],
            self[4] * rhs[2] + self[5] * rhs[6] + self[6] * rhs[10] + self[7] * rhs[14],
            self[4] * rhs[3] + self[5] * rhs[7] + self[6] * rhs[11] + self[7] * rhs[15],
            self[8] * rhs[0] + self[9] * rhs[4] + self[10] * rhs[8] + self[11] * rhs[12],
            self[8] * rhs[1] + self[9] * rhs[5] + self[10] * rhs[9] + self[11] * rhs[13],
            self[8] * rhs[2] + self[9] * rhs[6] + self[10] * rhs[10] + self[11] * rhs[14],
            self[8] * rhs[3] + self[9] * rhs[7] + self[10] * rhs[11] + self[11] * rhs[15],
            self[12] * rhs[0] + self[13] * rhs[4] + self[14] * rhs[8] + self[15] * rhs[12],
            self[12] * rhs[1] + self[13] * rhs[5] + self[14] * rhs[9] + self[15] * rhs[13],
            self[12] * rhs[2] + self[13] * rhs[6] + self[14] * rhs[10] + self[15] * rhs[14],
            self[12] * rhs[3] + self[13] * rhs[7] + self[14] * rhs[11] + self[15] * rhs[15]
        ])

    def Invert(self):
        res: 'Matrix4x4' = Matrix4x4.Identity()

        # Cache the matrix values (speed optimization)
        a00 = self[0], a01 = self[1], a02 = self[2], a03 = self[3]
        a10 = self[4], a11 = self[5], a12 = self[6], a13 = self[7]
        a20 = self[8], a21 = self[9], a22 = self[10], a23 = self[11]
        a30 = self[12], a31 = self[13], a32 = self[14], a33 = self[15]

        b00 = a00 * a11 - a01 * a10
        b01 = a00 * a12 - a02 * a10
        b02 = a00 * a13 - a03 * a10
        b03 = a01 * a12 - a02 * a11
        b04 = a01 * a13 - a03 * a11
        b05 = a02 * a13 - a03 * a12
        b06 = a20 * a31 - a21 * a30
        b07 = a20 * a32 - a22 * a30
        b08 = a20 * a33 - a23 * a30
        b09 = a21 * a32 - a22 * a31
        b10 = a21 * a33 - a23 * a31
        b11 = a22 * a33 - a23 * a32

        # Calculate the invert determinant (inlined to avoid double-caching)
        invDet = 1.0 / (b00 * b11 - b01 * b10 + b02 * b09 + b03 * b08 - b04 * b07 + b05 * b06)

        res[0] = (a11 * b11 - a12 * b10 + a13 * b09) * invDet
        res[1] = (-a01 * b11 + a02 * b10 - a03 * b09) * invDet
        res[2] = (a31 * b05 - a32 * b04 + a33 * b03) * invDet
        res[3] = (-a21 * b05 + a22 * b04 - a23 * b03) * invDet
        res[4] = (-a10 * b11 + a12 * b08 - a13 * b07) * invDet
        res[5] = (a00 * b11 - a02 * b08 + a03 * b07) * invDet
        res[6] = (-a30 * b05 + a32 * b02 - a33 * b01) * invDet
        res[7] = (a20 * b05 - a22 * b02 + a23 * b01) * invDet
        res[8] = (a10 * b10 - a11 * b08 + a13 * b06) * invDet
        res[9] = (-a00 * b10 + a01 * b08 - a03 * b06) * invDet
        res[10] = (a30 * b04 - a31 * b02 + a33 * b00) * invDet
        res[11] = (-a20 * b04 + a21 * b02 - a23 * b00) * invDet
        res[12] = (-a10 * b09 + a11 * b07 - a12 * b06) * invDet
        res[13] = (a00 * b09 - a01 * b07 + a02 * b06) * invDet
        res[14] = (-a30 * b03 + a31 * b01 - a32 * b00) * invDet
        res[15] = (a20 * b03 - a21 * b01 + a22 * b00) * invDet

        return res

    @staticmethod
    def Identity():
        return Matrix4x4([
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0
        ])

    @staticmethod
    def Zero():
        return Matrix4x4([0.0] * 16)
    
    @staticmethod
    def Rotation(axis: 'Vector3', angle: float):
        sqrlen = axis.sqrLen()

        if sqrlen != 1.0 and sqrlen != 0.0:
            axis *= 1.0 / sqrt(sqrlen)

        sinres = sin(angle)
        cosres = cos(angle)
        t = 1 - cosres

        return Matrix4x4([
            axis.x * axis.x * t + cosres,
            axis.y * axis.x * t + axis.z * sinres,
            axis.z * axis.x * t - axis.y * sinres,
            0.0,

            axis.x * axis.y * t - axis.z * sinres,
            axis.y * axis.y * t + cosres,
            axis.z * axis.y * t + axis.x * sinres,
            0.0,

            axis.x * axis.z * t + axis.y * sinres,
            axis.y * axis.z * t - axis.x * sinres,
            axis.z * axis.z * t + cosres,
            0.0,

            0.0,
            0.0,
            0.0,
            1.0,
        ])

    @staticmethod
    def RotateX(angle: float):
        res = Matrix4x4.Identity()

        cosres = cos(angle)
        sinres = sin(angle)

        res[5] = cosres
        res[6] = -sinres
        res[9] = sinres
        res[10] = cosres

        return res

    @staticmethod
    def RotateY(angle: float):
        res = Matrix4x4.Identity()

        cosres = cos(angle)
        sinres = sin(angle)

        res[0] = cosres
        res[2] = sinres
        res[8] = -sinres
        res[10] = cosres

        return res

    @staticmethod
    def RotateZ(angle: float):
        res = Matrix4x4.Identity()

        cosres = cos(angle)
        sinres = sin(angle)

        res[0] = cosres
        res[1] = -sinres
        res[4] = sinres
        res[5] = cosres

        return res
    
    @staticmethod
    def RotateXYZ(angles: 'Vector3'):
        res = Matrix4x4.Identity()

        cosz = cos(-angles.z)
        sinz = sin(-angles.z)
        cosy = cos(-angles.y)
        siny = sin(-angles.y)
        cosx = cos(-angles.x)
        sinx = sin(-angles.x)

        res[0] = cosz * cosy
        res[4] = (cosz * siny * sinx) - (sinz * cosx)
        res[8] = (cosz * siny * cosx) + (sinz * sinx)

        res[1] = sinz * cosy
        res[5] = (sinz * siny * sinx) + (cosz * cosx)
        res[9] = (sinz * siny * cosx) - (cosz * sinx)

        res[2] = -siny
        res[6] = cosy * sinx
        res[10] = cosy * cosx

        return res
    
    @staticmethod
    def Scale(scale: 'Vector3'):
        return Matrix4x4([
            scale.x, 0.0, 0.0, 0.0,
            0.0, scale.y, 0.0, 0.0,
            0.0, 0.0, scale.z, 0.0,
            0.0, 0.0, 0.0, 1.0
        ])

class Matrix3x3:
    values: List[float]

    def __init__(self, values: List[float]) -> None:
        if len(values) != 9:
            print("Matrix3x3 expects 9 values")

        self.values = values

    def __getitem__(self, i: int):
        return self.values[i]
    
    def __setitem__(self, i: int, val: float):
        self.values[i] = val

    def __str__(self) -> str:
        res = ""
        for i in range(0, 9, 3):
            res += f"[ {self[i]} {self[i + 1]} {self[i + 2]} ]\n"
        return res

    def __add__(self, rhs):
        return Matrix3x3([
            self[0] + rhs[0],  self[1] + rhs[1], self[2] + rhs[2],
            self[3] + rhs[3],  self[4] + rhs[4], self[5] + rhs[5],
            self[6] + rhs[6],  self[7] + rhs[7], self[8] + rhs[8]
        ])

    def __sub__(self, rhs):
        return Matrix3x3([
            self[0] + rhs[0],  self[1] + rhs[1], self[2] + rhs[2],
            self[3] + rhs[3],  self[4] + rhs[4], self[5] + rhs[5],
            self[6] + rhs[6],  self[7] + rhs[7], self[8] + rhs[8]
        ])
    
    def __mul__(self, rhs):
        return Matrix3x3([
            self[0] * rhs[0] + self[1] * rhs[3] + self[2] * rhs[6],
            self[0] * rhs[1] + self[1] * rhs[4] + self[2] * rhs[7],
            self[0] * rhs[2] + self[1] * rhs[5] + self[2] * rhs[8],
            self[3] * rhs[0] + self[4] * rhs[3] + self[5] * rhs[6],
            self[3] * rhs[1] + self[4] * rhs[4] + self[5] * rhs[7],
            self[3] * rhs[2] + self[4] * rhs[5] + self[5] * rhs[8],
            self[6] * rhs[0] + self[7] * rhs[3] + self[8] * rhs[6],
            self[6] * rhs[1] + self[7] * rhs[4] + self[8] * rhs[7],
            self[6] * rhs[2] + self[7] * rhs[5] + self[8] * rhs[8],
        ])
    
    def Invert(self):
        det = self[0] * self[4] * self[8] + self[1] * self[5] * self[6] + self[2] * self[3] * self[7] - self[0] * self[5] * self[7] - self[1] * self[3] * self[8] - self[2] * self[4] * self[6]

        if det == 0:
            print("Cannot calculate invert a matrix when the determinant is 0")
            exit()

        detInv = 1.0 / det

        return Matrix3x3([
            self[4] * self[8] - self[5] * self[7],
            -( self[1] * self[8] - self[2] * self[7] ),
            self[1] * self[5] - self[2] * self[4],
            -( self[3] * self[8] - self[5] * self[6] ),
            self[0] * self[8] - self[2] * self[6],
            -( self[0] * self[5] - self[2] * self[3] ),
            self[3] * self[7] - self[4] * self[6],
            -( self[0] * self[7] - self[1] * self[6] ),
            self[0] * self[4] - self[1] * self[3]
        ])

    @staticmethod
    def Identity():
        return Matrix3x3([
            1.0, 0.0, 0.0,
            0.0, 1.0, 0.0,
            0.0, 0.0, 1.0
        ])

from .Vector3 import Vector3

