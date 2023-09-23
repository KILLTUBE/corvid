from io import TextIOWrapper
from typing import List
from Formats.BaseMap.Brush import Brush as BaseBrush
from .Face import Face

class Brush(BaseBrush):
    __slots__ = ("contents", "toolFlags", "layer")

    faces: List[Face]
    contents: List[str]
    toolFlags: List[str]
    layer: str

    def __init__(self, faces: List[Face]=None, contents=[]) -> None:
        super().__init__()
    
        if faces is not None:
            self.faces = faces
    
        self.contents = []
        self.toolFlags = []
        self.layer = None

    def __str__(self) -> str:
        res = "{\n"

        if self.layer is not None:
            res += f"layer {self.layer}\n"

        if len(self.toolFlags) > 0:
            res += "toolFlags " + " ".join(self.toolFlags) + ";\n"

        if len(self.contents) > 0:
            res += "contents " + " ".join(self.contents) + ";\n"
            
        for face in self.faces:
            res += str(face)

        res += "}\n"

        return res

    def __repr__(self) -> str:
        address = "%.2x" % id(self)
        return f"<Brush object at {address}>"
    
    def Save(self, file: TextIOWrapper):
        if len(self.faces) == 0:
            return

        file.write("{\n")

        if self.layer is not None:
            file.write(f"layer {self.layer}\n")

        if len(self.toolFlags) > 0:
            file.write("toolFlags " + " ".join(self.toolFlags) + ";\n")

        if len(self.contents) > 0:
            file.write("contents " + " ".join(self.contents) + ";\n")
            
        for face in self.faces:
            face.Save(file)

        file.write("}\n")
