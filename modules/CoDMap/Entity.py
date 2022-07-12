from typing import Dict, List, Union
from .Brush import Brush
from .Patch import Patch

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
            res += f'"{key}" "{value}"\n'
        
        for i, geo in enumerate(self.geo):
            res += f"// brush {i}\n"
            if isinstance(geo, list):
                for _geo in geo:
                    res += str(_geo)
            else:
                res += str(geo)

        res += "}\n"

        return res
