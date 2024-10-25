from io import TextIOWrapper
from typing import Dict, List, Union
from glm import vec3, vec2
from modules.Static import flatten
from .Brush import Brush
from .Patch import Patch
from ..Static import Vec2Str

class Entity:
    properties: Dict[str, str]
    geo: List[Union[Brush, Patch]]
    layer: str

    def __init__(self, properties={}) -> None:
        self.properties = properties
        self.geo = []
        self.layer = None

    def __setitem__(self, __name: str, __value: str) -> None:
        self.properties[__name] = __value

    def __getitem__(self, __name: str) -> str:
        return self.properties[__name]

    def __delitem__(self, __name: str) -> None:
        del self.properties[__name]
    
    def __contains__(self, __name: str) -> bool:
        return __name in self.properties
    
    def __str__(self) -> str:
        res = "{\n"

        if self.layer is not None:
            res += f"layer {self.layer}\n"

        for key, value in self.properties.items():
            if isinstance(value, vec3) or isinstance(value, vec2):
                value = Vec2Str(value)
            res += f'"{key}" "{value}"\n'

        self.geo = flatten(self.geo)

        for i, geo in enumerate(self.geo):
            res += f"// brush {i}\n"
            if isinstance(geo, list):
                for _geo in geo:
                    res += str(_geo)
            else:
                res += str(geo)

        res += "}\n"

        return res

    def Save(self, file: TextIOWrapper):
        file.write("{\n")

        if self.layer is not None:
            file.write(f"layer {self.layer}\n")

        for key, value in self.properties.items():
            if isinstance(value, vec3) or isinstance(value, vec2):
                value = Vec2Str(value)
            file.write(f'"{key}" "{value}"\n')

        self.geo = flatten(self.geo)

        for i, geo in enumerate(self.geo):
            if geo is not None:
                file.write(f"// brush {i}\n")
                geo.Save(file)

        file.write("}\n")
