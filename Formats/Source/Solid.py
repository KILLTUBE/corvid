from typing import Dict, List
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
            for sideData in data["side"]:
                side = Side(sideData)
                self.AddFace(side)

                if not side.material.startswith("tools/"):
                    self.isToolBrush = False

                if side.dispInfo is not None:
                    self.hasDisp = True

    def ToDict(self, id: int=None) -> dict:
        res: dict = {}

        if id is not None:
            res["id"] = id

        res["side"] = [side.ToDict() for side in self.faces]

        return res

from .Side import Side
