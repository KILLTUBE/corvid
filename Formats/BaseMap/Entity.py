from typing import Any, List, Dict
from .Brush import Brush
from mathutils import Vector

class Entity:
    """ Base class that has all the properties and methods used by a map entity. """
    __slots__ = ("__properties__", "geo")
    __properties__: Dict[str, str]
    geo: List[Brush]

    def __init__(self) -> None:
        self.__properties__ = {}
        self.geo = []

    def __setitem__(self, key: str, __value: str) -> None:
        self.__properties__[key] = __value

    def __getitem__(self, key: str) -> str | None:
        return self.__properties__.get(key)

    def __delitem__(self, key: str) -> None:
        del self.__properties__[key]
    
    def __contains__(self, key: str) -> bool:
        return key in self.__properties__

    def __str__(self) -> str:
        raise NotImplementedError()

    def GetInt(self, key: str) -> int:
        return int(self[key]) if key in self else 0

    def GetFloat(self, key: str) -> float:
        return float(self[key]) if key in self else 0

    def GetVector(self, key: str, size: int=3) -> Vector | None:
        if key not in self:
            return None

        tok = self[key].split()

        if len(tok) < size:
            tok.extend([0] * (size - len(tok)))

        return Vector([float(i) for i in tok[0:size]])
