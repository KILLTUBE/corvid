from typing import Dict, List, Union, Tuple
from mathutils import Vector
from Helpers.MathHelpers import VecFromStr, Vec2Str, VecFromList

class Displacement:
    __slots__ = ("power", "startPosition", "elevation", "numRows", "normals", "distances", "alphas")

    power: int
    startPosition: Vector
    elevation: float
    numRows: int
    normals: List[List[Vector]]
    distances: List[List[float]]
    alphas: List[List[int]]

    def __init__(self, data: Union[Dict[str, Union[dict, str]], None]) -> None:
        if data is None:
            self.power = self.startPosition = self.numRows = None
            self.elevation = 0
            self.normals = []
            self.distances = []
            self.alphas = []

        else:
            self.power = int(data["power"])
            self.startPosition = VecFromStr(data["startposition"][1:-1])
            self.elevation = float(data["elevation"])
            self.numRows = (2 ** self.power) + 1

            self.normals = []
            for row in data["normals"].values():
                normals = [float(i) for i in row.split()]
                self.normals.append([VecFromList(normals[i:i + 3]) for i in range(0, len(normals), 3)])

            self.distances = []
            for row in data["distances"].values():
                self.distances.append([float(val) for val in row.split()])
            
            self.alphas = []
            for row in data["alphas"].values():
                self.alphas.append([int(float(val)) for val in row.split()])

    def ToDict(self) -> dict:
        res = {
            "power": self.power,
            "startposition": f"[{self.startPosition}]",
            "elevation": self.elevation,
            "subdiv": 0,
            "normals": {},
            "distances": {},
            "alphas": {},
            "triangle_tags": {}
        }

        for i, row in enumerate(self.normals):
            res["normals"][f"row{i}"] = " ".join([Vec2Str(vec) for vec in row])

        for i, row in enumerate(self.distances):
            res["distances"][f"row{i}"] = " ".join([f"{dist:.6g}" for dist in row])

        for i, row in enumerate(self.alphas):
            res["alphas"][f"row{i}"] = " ".join([f"{alpha}" for alpha in row])

        return res
