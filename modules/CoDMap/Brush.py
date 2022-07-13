from io import TextIOWrapper
from typing import List
from .Face import Face

class Brush:
    faces: List[Face]
    contents: List[str]
    toolflags: List[str]
    layer: str
    filters: dict

    def __init__(self, faces=[], contents=[]) -> None:
        self.faces = faces
        self.contents = []
        self.toolflags = []
        self.layer = None

    def __str__(self) -> str:
        res = "{\n"

        if self.layer is not None:
            res += f"layer {self.layer}\n"

        if len(self.toolflags) > 0:
            res += "toolFlags " + " ".join(self.toolflags) + ";\n"

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
        file.write("{\n")

        if self.layer is not None:
            file.write(f"layer {self.layer}\n")

        if len(self.toolflags) > 0:
            file.write("toolFlags " + " ".join(self.toolflags) + ";\n")

        if len(self.contents) > 0:
            file.write("contents " + " ".join(self.contents) + ";\n")
            
        for face in self.faces:
            face.Save(file)

        file.write("}\n")
