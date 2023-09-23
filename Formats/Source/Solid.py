from typing import Dict, List, Union
from Formats.BaseMap.Brush import Brush

class Solid(Brush):
    __slots__ = ("id", "hasDisp", "isToolBrush")

    id: int
    hasDisp: bool
    isToolBrush: bool
    faces: List['Side']

    def __init__(self, data: Dict[str, str]=None) -> None:
        super().__init__()
        self.id = int(data["id"]) if data is not None and "id" in data else None
        self.hasDisp = False
        self.isToolBrush = True

        if data is not None and "side" in data:
            for side in data["side"]:
                self.AddFace(Side(side))

                if not side["material"].strip().lower().startswith("tools/"):
                    self.isToolBrush = False

                if "dispinfo" in side:
                    self.hasDisp = True

    def ToDict(self, id: int=None) -> dict:
        res: dict = {}

        if id is not None:
            res["id"] = id
        
        res["side"] = [side.ToDict() for side in self.faces]

        return res

from .Side import Side
