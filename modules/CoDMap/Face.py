from io import TextIOWrapper
from glm import vec3, vec2
# from ..Vector3 import Vector3
from ..Static import Vec2Str

class Face:
    # (p1) (p2) (p3) texture hScale vScale hShift vShift rotation 0 lmap lhScale lvScale lhShift lvShift lrot 0
    p1: vec3
    p2: vec3
    p3: vec3
    texture: str
    hScale: float
    vScale: float
    hShift: float
    vShift: float
    rotation: float
    lightmap: str
    lhScale: float
    lvScale: float
    lhShift: float
    lvShift: float
    smoothing: str

    def __init__(self, p1, p2, p3, texture, hScale=128, vScale=128, hShift=0, vShift=0, rotation=0, lmap="lightmap_gray", lhScale=16384, lvScale=16384, lhShift=0, lvShift=0, smoothing=None) -> None:
        self.p1, self.p2, self.p3 = p1, p2, p3
        self.texture = texture
        self.hScale, self.vScale = hScale, vScale
        self.hShift, self.vShift = hShift, vShift
        self.rotation = rotation
        self.lightmap = lmap
        self.lhScale, self.lvScale = lhScale, lvScale
        self.lhShift, self.lvShift = lhShift, lvShift
        self.smoothing = smoothing

    def __str__(self) -> str:
        res = f"( {Vec2Str(self.p1)} ) ( {Vec2Str(self.p2)} ) ( {Vec2Str(self.p3)} ) {self.texture} {round(self.hScale)} {round(self.vScale)} {self.hShift:.5g} {self.vShift:.5g} {round(self.rotation)} 0 {self.lightmap} {self.lhScale} {self.lhScale} 0 0 0 0"
        
        if self.smoothing is not None:
            res += " smoothing " + self.smoothing

        return res

    def __repr__(self) -> str:
        address = "%.2x" % id(self)
        return f"<Face ({Vec2Str(self.p1)} {Vec2Str(self.p2)} {Vec2Str(self.p3)}) object at {address}>"
    
    def Save(self, file: TextIOWrapper):
        file.write(str(self) + "\n")

    def Fit(self, normal, vertices: list[vec3], uvs: list[vec2]):
        """ Fits the UV parameters from vertices, UVs, and face normal. """
        from ..UV import fit_uvs
        h, v, ho, vo, r = fit_uvs(vertices, uvs, normal)
        self.hScale = h
        self.vScale = v
        self.hShift = ho
        self.vShift = vo
        self.rotation = r
