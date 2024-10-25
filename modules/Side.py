# from .Vector3 import Vector3
# from .Vector2 import Vector2
# from mathutils import Vector, Matrix
from glm import vec2, vec3, cross, dot, normalize
from numpy.linalg import solve
from math import copysign, cos, degrees, pow, radians, sin, sqrt, fabs
from .Static import VecFromStr
from .AABB import AABB
import re
import functools

def parseTriplets(tri: str):
    res = []
    tok = [float(i) for i in tri.split()]
    i = 0
    while i < len(tok):
        res.append(vec3(tok[i], tok[i + 1], tok[i + 2]))
        i += 3
    return res

def parseSinglets(sin: str):
    res = []
    tok = sin.split(" ")
    for val in tok:
        res.append(float(val))
    return res

class Side:
    def __init__(self, data=None):
        self._center = None
        self._normal = None
        self.points: list[vec3] = []
        self.hasDisp = False

        if data is not None:
            self.id = data["id"]

            p = re.split(r"[(|)| ]", data["plane"])
            p = [float(i) if i != "" else 0 for i in p]

            self.p1: vec3 = vec3(p[1], p[2], p[3])
            self.p2: vec3 = vec3(p[6], p[7], p[8])
            self.p3: vec3 = vec3(p[11], p[12], p[13])

            self.material: str = data["material"].lower()

            u = re.split(r"[\[|\]| ]", data["uaxis"])
            u = [float(_u) if _u != "" else 0 for _u in u]
            v = re.split(r"[\[|\]| ]", data["vaxis"])
            v = [float(_v) if _v != "" else 0 for _v in v]

            self.uAxis: vec3 = vec3(u[1], u[2], u[3])
            self.vAxis: vec3 = vec3(v[1], v[2], v[3])
            self.uOffset: float = float(u[4])
            self.vOffset: float = float(v[4])
            self.uScale: float = float(u[6])
            self.vScale: float = float(v[6])

            self.texSize: vec2 = vec2(1024, 1024)
            self.lightmapScale: int = int(data["lightmapscale"])
            self.uvs: list[vec2] = []

            if "dispinfo" in data:
                self.hasDisp = True
                self.dispinfo = self.processDisplacement(data["dispinfo"])

        else:
            self.p1 = self.p2 = self.p3 = None
            self.material = "null"
            self.id = "null"
    
    @staticmethod
    def FromPoints(p1: vec3, p2: vec3, p3: vec3):
        res = Side()
        res.p1, res.p2, res.p3 = p1, p2, p3
        return res

    def normal(self):
        if self._normal is not None:
            return self._normal

        ab: vec3 = self.p2 - self.p1
        ac: vec3 = self.p3 - self.p1
        normal = cross(ab, ac)
        self._normal = normal
        return normal

    def center(self):
        return (self.p1 + self.p2 + self.p3) / 3

    def distance(self):
        normal: vec3 = self.normal()
        return ((self.p1.x * normal.x) + (self.p1.y * normal.y) + (self.p1.z * normal.z)) / sqrt(pow(normal.x, 2) + pow(normal.y, 2) + pow(normal.z, 2))

    def pointCenter(self):
        if self._center is not None:
            return self._center
        
        center = vec3()
        for point in self.points:
            center = center + point
        
        self._center = center / len(self.points)
        return self._center

    def sortVertices(self):
        # remove duplicate verts
        temp = []
        for point in self.points:
            if point not in temp:
                temp.append(point)
        self.points = temp
        center: vec3 = self.pointCenter()
        normal: vec3 = self.normal()

        def compare(a: vec3, b: vec3):
            ca = center - a
            cb = center - b
            caXcb = cross(ca, cb)
            if dot(normal, caXcb) > 0:
                return 1
            return -1

        self.points.sort(key=functools.cmp_to_key(compare))

    def __eq__(self, rhs: 'Side'):
        return self.p1 == rhs.p1 and self.p2 == rhs.p2 and self.p3 == rhs.p3

    def getUV(self, vertex: vec3, texSize: vec2 = vec2(1024, 1024)):
        if texSize.x == 0 or texSize.y == 0:
            texSize = vec2(1024, 1024)

        return vec2(
            dot(vertex, self.uAxis) / (texSize.x * self.uScale) +
            (self.uOffset / texSize.x),
            dot(vertex, self.vAxis) / (texSize.y * self.vScale) +
            (self.vOffset / texSize.y)
        )
    
    def getLmapUV(self, vertex: vec3):
        uv = vec2(0, 0)
        texSize = vec2(1024, 1024)
        n = normalize(self.normal())
        
        du = fabs(dot(n, vec3(0.0, 0.0, 1.0)))
        dr = fabs(dot(n, vec3(0.0, 1.0, 0.0)))
        df = fabs(dot(n, vec3(1.0, 0.0, 0.0)))

        if du >= dr and du >= df:
            uv = vec2(vertex.x, -vertex.y)
        elif dr >= du and dr >= df:
            uv = vec2(vertex.x, -vertex.z)
        elif df >= du and df >= dr:
            uv = vec2(vertex.y, -vertex.z)
        
        # we're gonna assume the rotation is 0
        rotated = vec2(0, 0)
        rotated.x = uv.x * cos(0) - uv.y * sin(0)
        rotated.y = uv.x * sin(0) + uv.y * cos(0)
        uv = rotated

        uv /= texSize
        uv /= self.lightmapScale

        return uv * 1024
    
    # based on https://github.com/GregLukosek/3DMath/blob/master/Math3D.cs#L242
    def getClosestPoint(self, point: vec3):
        normal = normalize(self.normal())
        distance = normal.dot(point - self.p1) * -1
        translationVector = normal * distance
        return point + translationVector
    
    # based on https://gdbooks.gitbooks.io/3dcollisions/content/Chapter2/static_aabb_plane.html
    def IsTouching(self, box: AABB) -> bool:
        normal = normalize(self.normal())
        radius = box.extents.x * abs(normal.x) + box.extents.y * abs(normal.y) + box.extents.z * abs(normal.z)
        distance = dot(normal, box.center) - self.distance()
        return abs(distance) <= radius

    # returns basic x/y scale/shift values from the VMF 
    # TODO: make it work again with the code based on https://github.com/c-d-a/io_export_qmap with GLM later
    def getTexCoords(self):
        return f"{self.uScale * self.texSize.x} {self.vScale * self.texSize.x} {self.uOffset} {self.vOffset} 0 0 lightmap_gray 16384 16384 0 0 0 0"

    def processDisplacement(self, data):
        result = {
            "power": int(data["power"]),
            "elevation": float(data["elevation"]),
            "subdiv": True if data["subdiv"] == "1" else False,
            "row": []
        }
        startpos = data["startposition"].replace("[", "").replace("]", "").split(" ")
        result["startpos"] = VecFromStr(data["startposition"], 3)

        for i in range(int(pow(2, result["power"]) + 1)):
            result["row"].append({
                "normals": parseTriplets(data["normals"]["row" + str(i)]),
                "distances": parseSinglets(data["distances"]["row" + str(i)]),
                "alphas": parseSinglets(data["alphas"]["row" + str(i)])
            })
        return result

    def __repr__(self) -> str:
        return f"<Side {self.id} ( {self.p1} ) ( {self.p2} ) ( {self.p3} ) {self.material}>"
