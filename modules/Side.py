from mathutils import Vector, Matrix
from numpy.linalg import solve
from math import pow, sqrt, degrees
import re
import functools
from .Static import Vector2Str
from os.path import basename

def parseTriplets(tri: str):
    res = []
    tok = tri.split(" ")
    i = 0
    while i < len(tok):
        res.append(Vector((float(tok[i]), float(tok[i + 1]), float(tok[i + 2]))))
        i += 3
    return res


def parseSinglets(sin: str):
    res = []
    tok = sin.split(" ")
    for val in tok:
        res.append(float(val))
    return res


class Side:
    def __init__(self, data):
        self.id = data["id"]

        p = re.split(r"[(|)| ]", data["plane"])

        self.p1: Vector = Vector((float(p[1]), float(p[2]), float(p[3])))
        self.p2: Vector = Vector((float(p[6]), float(p[7]), float(p[8])))
        self.p3: Vector = Vector((float(p[11]), float(p[12]), float(p[13])))

        self.material: str = data["material"].lower().strip()

        u = re.split(r"[\[|\]| ]", data["uaxis"])
        v = re.split(r"[\[|\]| ]", data["vaxis"])
        self.uAxis: Vector = Vector((float(u[1]), float(u[2]), float(u[3])))
        self.vAxis: Vector = Vector((float(v[1]), float(v[2]), float(v[3])))
        self.uOffset: float = float(u[4])
        self.vOffset: float = float(v[4])
        self.uScale: float = float(u[6])
        self.vScale: float = float(v[6])

        self.texSize: Vector = Vector((1024, 1024))
        self.lightmapScale: int = int(data["lightmapscale"])
        self.points: list[Vector] = []
        self.uvs: list[Vector] = []

        try:
            data["dispinfo"]
        except:
            self.hasDisp = False
        else:
            self.hasDisp = True
            self.dispinfo = self.processDisplacement(data["dispinfo"])

    def normal(self):
        ab: Vector = self.p2 - self.p1
        ac: Vector = self.p3 - self.p1
        return ab.cross(ac)

    def center(self):
        return (self.p1 + self.p2 + self.p3) / 3

    def distance(self):
        normal: Vector = self.normal()
        return ((self.p1.x * normal.x) + (self.p1.y * normal.y) + (self.p1.z * normal.z)) / sqrt(pow(normal.x, 2) + pow(normal.y, 2) + pow(normal.z, 2))

    def pointCenter(self):
        center = Vector()
        for point in self.points:
            center = center + point
        return center / len(self.points)

    def sortVertices(self):
        # remove duplicate verts. looks like checking the point list manually doesn't always give perfect results.
        temp = {}
        for point in self.points:
            temp[f"{round(point.x)} {round(point.y)} {round(point.z)}"] = point
        self.points = list(temp.values()) 

        center: Vector = self.pointCenter()
        normal: Vector = self.normal()

        def compare(a: Vector, b: Vector):
            ca: Vector = center - a
            cb: Vector = center - b
            caXcb = ca.cross(cb)
            if normal.dot(caXcb) > 0:
                return 1
            return -1

        self.points.sort(key=functools.cmp_to_key(compare))

    def __eq__(self, rhs: 'Side'):
        return self.p1 == rhs.p1 and self.p2 == rhs.p2 and self.p3 == rhs.p3

    def getUV(self, vertex: Vector, texSize: Vector = Vector((1024, 1024))):
        if texSize.x == 0 or texSize.y == 0:
            texSize = Vector((1024, 1024))

        return Vector((
            vertex.dot(self.uAxis) / (texSize.x * self.uScale) +
            (self.uOffset / texSize.x),
            vertex.dot(self.vAxis) / (texSize.y * self.vScale) +
            (self.vOffset / texSize.y)
        ))

    def processDisplacement(self, data):
        result = {
            "power": int(data["power"]),
            "elevation": float(data["elevation"]),
            "subdiv": True if data["subdiv"] == "1" else False,
            "row": []
        }
        startpos = data["startposition"].replace(
            "[", "").replace("]", "").split(" ")
        result["startpos"] = Vector((
            float(startpos[0]), float(startpos[1]), float(startpos[2])
        ))

        for i in range(int(pow(2, result["power"]) + 1)):
            result["row"].append({
                "normals": parseTriplets(data["normals"]["row" + str(i)]),
                "distances": parseSinglets(data["distances"]["row" + str(i)]),
                "alphas": parseSinglets(data["alphas"]["row" + str(i)])
            })
        return result
    
    def hasPoint(self, point: Vector):
        for p in self.points:
            if p == point:
                return True
        return False
    
    def texCoords(self):
        # based on https://github.com/c-d-a/io_export_qmap/blob/master/io_export_qmap.py#L190
        # first two vertices in 3d space 
        world01 = self.points[1] - self.points[0]
        world02 = self.points[2] - self.points[0]

        maxNormal = max(abs(round(crd, 5)) for crd in self.normal())

        # 01 and 02 projected along the closest axis
        for i in [2, 0, 1]:
            if round(abs(self.normal()[i]), 5) == maxNormal:
                axis = i
                break
        
        # 01 and 02 in UV space (scaled to texture size)
        world01_2d = Vector((world01[:axis] + world01[(axis+1):]))
        world02_2d = Vector((world02[:axis] + world02[(axis+1):]))

        # get uv points
        for point in self.points:
            self.uvs.append(self.getUV(point, self.texSize))

        tex01 = self.uvs[1] - self.uvs[0]
        tex02 = self.uvs[2] - self.uvs[0]
        tex01.x *= self.texSize.x
        tex02.x *= self.texSize.x
        tex01.y *= self.texSize.y
        tex02.y *= self.texSize.y

        # Find affine transformation between 2D and UV
        texCoordsVec = Vector((tex01.x, tex01.y, tex02.x, tex02.y))
        world2DMatrix = Matrix((
            (world01_2d.x, world01_2d.y, 0, 0),
            (0, 0, world01_2d.x, world01_2d.y),
            (world02_2d.x, world02_2d.y, 0, 0),
            (0, 0, world02_2d.x, world02_2d.y)
        ))

        try:
            mCoeffs = solve(world2DMatrix, texCoordsVec)
        except:
            return False
        
        # Build the transformation matrix and decompose it
        tformMtx = Matrix((
            (mCoeffs[0], mCoeffs[1], 0),
            (mCoeffs[2], mCoeffs[3], 0),
            (0, 0, 1)
        ))
        t0 = Vector((self.uvs[0].x * self.texSize.x, self.uvs[0].y * self.texSize.y)).to_3d()
        v0 = Vector((self.points[0][:axis] + self.points[0][(axis+1):])).to_3d()

        offset = t0 - ( tformMtx @ v0 )
        rotation = degrees(tformMtx.inverted_safe().to_euler().z)
        scale = tformMtx.inverted_safe().to_scale() # always positive

        # Compare normals between UV and projection to get the scale sign
        tn = tex01.to_3d().cross(tex02.to_3d())
        vn = world01_2d.to_3d().cross(world02_2d.to_3d())
        if tn.dot(vn) < 0: scale.x *= -1

        return (
            f"{scale.x * self.texSize.x:.5g} {scale.y * self.texSize.y * -1:.5g} {offset.x:.5g} {offset.y:.5g} {rotation:.5g}"
            + f" 0 lightmap_gray {1024 * self.lightmapScale} {1024 * self.lightmapScale} 0 0 0 0"
        )
