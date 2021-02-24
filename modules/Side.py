from .Vector3 import Vector3
from .Vector2 import Vector2
from math import pow, sqrt
import re
import functools


def parseTriplets(tri: str):
    res = []
    tok = tri.split(" ")
    i = 0
    while i < len(tok):
        res.append(Vector3(tok[i], tok[i + 1], tok[i + 2]))
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

        self.p1: Vector3 = Vector3(p[1], p[2], p[3])
        self.p2: Vector3 = Vector3(p[6], p[7], p[8])
        self.p3: Vector3 = Vector3(p[11], p[12], p[13])

        self.material = data["material"].lower()

        u = re.split(r"[\[|\]| ]", data["uaxis"])
        v = re.split(r"[\[|\]| ]", data["vaxis"])
        self.uAxis: Vector3 = Vector3(u[1], u[2], u[3])
        self.vAxis: Vector3 = Vector3(v[1], v[2], v[3])
        self.uOffset: float = float(u[4])
        self.vOffset: float = float(v[4])
        self.uScale: float = float(u[6])
        self.vScale: float = float(v[6])

        self.texSize: Vector2 = Vector2(1024, 1024)
        self.lightmapScale: int = int(data["lightmapscale"])
        self.points: list[Vector3] = []
        self.uvs: list[Vector2] = []

        try:
            data["dispinfo"]
        except:
            self.hasDisp = False
        else:
            self.hasDisp = True
            self.dispinfo = self.processDisplacement(data["dispinfo"])

    def normal(self):
        ab: Vector3 = self.p2 - self.p1
        ac: Vector3 = self.p3 - self.p1
        return ab.cross(ac)

    def center(self):
        return (self.p1 + self.p2 + self.p3) / 3

    def distance(self):
        normal: Vector3 = self.normal()
        return ((self.p1.x * normal.x) + (self.p1.y * normal.y) + (self.p1.z * normal.z)) / sqrt(pow(normal.x, 2) + pow(normal.y, 2) + pow(normal.z, 2))

    def pointCenter(self):
        center = Vector3()
        for point in self.points:
            center = center + point
        return center / len(self.points)

    def sortVertices(self):
        # remove duplicate verts
        temp = {}
        for point in self.points:
            temp[str(point.round())] = point
        self.points = list(temp.values())
        center: Vector3 = self.pointCenter()
        normal: Vector3 = self.normal()

        def compare(a: Vector3, b: Vector3):
            ca = center - a
            cb = center - b
            caXcb = ca.cross(cb)
            if normal.dot(caXcb) > 0:
                return 1
            return -1

        self.points.sort(key=functools.cmp_to_key(compare))

    def __eq__(self, rhs: 'Side'):
        return self.p1 == rhs.p1 and self.p2 == rhs.p2 and self.p3 == rhs.p3

    def getUV(self, vertex: Vector3, texSize: Vector2 = Vector2(1024, 1024)):
        return Vector2(
            vertex.dot(self.uAxis) / (texSize.x * self.uScale) +
            (self.uOffset / texSize.x),
            vertex.dot(self.vAxis) / (texSize.y * self.vScale) +
            (self.vOffset / texSize.y)
        )

    def processDisplacement(self, data):
        result = {
            "power": int(data["power"]),
            "elevation": float(data["elevation"]),
            "subdiv": True if data["subdiv"] == "1" else False,
            "row": []
        }
        startpos = data["startposition"].replace(
            "[", "").replace("]", "").split(" ")
        result["startpos"] = Vector3(
            float(startpos[0]), float(startpos[1]), (startpos[2]))

        for i in range(int(pow(2, result["power"]) + 1)):
            result["row"].append({
                "normals": parseTriplets(data["normals"]["row" + str(i)]),
                "distances": parseSinglets(data["distances"]["row" + str(i)]),
                "alphas": parseSinglets(data["alphas"]["row" + str(i)])
            })
        return result
