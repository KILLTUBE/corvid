from .Vector3 import Vector3
from .Vector2 import Vector2

class MapSide:
    def __init__(self,
        p1: Vector3,
        p2: Vector3,
        p3: Vector3,
        texture: str = "caulk",
        hScale: int = 128,
        vScale: int = 128,
        hShift: int = 0,
        vShift: int = 0,
        rotation: int = 0,
        lmapTexture: str = "lightmap_gray",
        lmapHScale: int = 16384,
        lmapVScale: int = 16384
    ):
        self.p1 = p1
        self.p2 = p2
        self.p3 = p3
        self.texture = texture
        self.hScale = hScale 
        self.vScale = vScale 
        self.hShift = hShift 
        self.vShift = vShift 
        self.rotation = rotation 
        self.lmapTexture = lmapTexture
        self.lmapHScale = lmapHScale
        self.lmapVScale = lmapVScale

    def __str__(self):
        return (
            f"( {self.p1} ) ( {self.p2} ) ( {self.p3} )"
            +f" {self.texture} {self.hShift} {self.vShift} {self.hScale} {self.vScale} {self.rotation}"
            +f" {self.lmapTexture} {self.lmapHScale} {self.lmapVScale} 0 0 0 0\n"
        )

class MapBrush:
    def __init__(self, id: int = 0):
        self.sides: list[MapSide] = []
        self.contents = ""
        self.id = id
    
    def __str__(self):
        if len(self.sides) == 0:
            return ""
        res = ""
        if id != 0:
            res += f"// Brush {self.id}\n"
        res += "{\n"
        if self.contents != "":
            res += f"contents {self.contents};\n"
        for side in self.sides:
            res += str(side)
        res += "}\n"
        return res

class MapVert:
    def __init__(self, pos: Vector3, uv: Vector2, lmapUv: Vector2, color=""):
        self.pos = pos
        self.uv = uv
        self.color = color
        self.lmapUv = lmapUv
    
    def __str__(self):
        if self.color == "":
            return f"v {self.pos} t {self.uv} {self.lmapUv}\n"
        else:
            return f"v {self.pos} c {self.color} t {self.uv} {self.lmapUv}\n"

class MapMesh:
    def __init__(self, texture: str, lmapTexture: str="lightmap_gray", lmapSize: int=16, rowCount: int=0, columnCount: int=0, id: int=0):
        self.texture = texture
        self.lmapTexture = lmapTexture
        self.lmapSize = lmapSize
        self.rowCount = rowCount
        self.columnCount = columnCount
        self.rows = [[None] * columnCount ] * rowCount
        self.id = id
    
    def addVert(self, row: int, column: int, vert: MapVert):
        self.rows[row][column] = vert
    
    def __str__(self):
        res = ""
        if self.id != 0:
            res += f"// Mesh {self.id}\n"
        res += (
            "{\n"
            + "mesh\n"
            + "{\n"
            + f"{self.texture}\n"
            + f"{self.lmapTexture}"
            + f"{self.rowCount} {self.columnCount} {self.lmapSize} 8\n"
        )

        for row in self.rows:
            res += "(\n"
            for vert in row:
                res += str(vert)
            res += ")\n"
        
        res += "}\n"
        res += "}\n"
        return res

class MapEntity:
    def __init__(self, id: int=0):
        self.__geo__ = []
        self.__id__ = id

    def addGeo(self, geo):
        self.__geo__.append(geo)

    def __str__(self):
        res = ""
        if self.__id__ != 0:
            res += f"// Entity {self.__id__}\n"
        res += "{\n"
        for key, value in vars(self).items():
            if key.startswith("__") and key.endswith("__"):
                continue
            res += f'"{key}" "{value}"\n'
        for geo in self.__geo__:
            res += str(geo)
        res += "}\n"
        return res