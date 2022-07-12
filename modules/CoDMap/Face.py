from ..Vector3 import Vector3

class Face:
    # (p1) (p2) (p3) texture hScale vScale hShift vShift rotation 0 lmap lhScale lvScale lhShift lvShift lrot 0
    p1: Vector3
    p2: Vector3
    p3: Vector3
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
        res = f"( {self.p1} ) ( {self.p2} ) ( {self.p3} ) {self.texture} {self.hScale} {self.vScale} {self.hShift} {self.vShift} {self.rotation} 0 {self.lightmap} {self.lhScale} {self.lhScale} 0 0 0 0"
        
        if self.smoothing is not None:
            res += " smoothing " + self.smoothing
        
        return res + "\n"

    def __repr__(self) -> str:
        address = "%.2x" % id(self)
        return f"<Face ({self.p1} {self.p2} {self.p3}) object at {address}>"
