from typing import List
from Formats.BaseMap.Entity import Entity as BaseEntity
from .Solid import Solid

class Entity(BaseEntity):
    __slots__ = ("id")
    geo: List[Solid]

    def __init__(self, entity: dict) -> None:
        super().__init__()

        if "solid" in entity and isinstance(entity["solid"], (list, dict)):
            solids = [entity.pop("solid")] if "side" in entity["solid"] else entity.pop("solid")

            for solid in solids:
                self.geo.append(Solid(solid))

        self.__properties__.update(entity)

    def ToDict(self):
        res = self.__properties__.copy()

        if len(self.geo) > 0:
            res["solid"] = []
            for geo in self.geo:
                res["solid"].append(geo.ToDict())

        return res