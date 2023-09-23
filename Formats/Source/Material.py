from typing import Dict
from .vdfutils import format_vdf, parse_vdf, fix_vmt_string

class Material:
    __slots__ = ("shader", "data")
    
    shader: str
    data: Dict[str, Dict[str, str]]

    def __init__(self, shader: str, data: dict={}):
        self.shader = shader
        self.data = data
    
    def __str__(self) -> str:
        res = {self.shader: {}}
        res[self.shader].update(self.data)

        return format_vdf(res)

    def __repr__(self) -> str:
        return f"<Material: [{self.shader}]{' [' + self['$basetexture'] + ']' if '$basetexture' in self.data else ''}>"

    def InheritFrom(self, base: 'Material'):
        self.data = self.data.update(base.data.copy())

    def __setitem__(self, __name: str, __value: str) -> None:
        self.data[__name] = __value

    def __getitem__(self, __name: str) -> str:
        return self.data[__name]

    def __delitem__(self, __name: str) -> None:
        del self.data[__name]
    
    def __contains__(self, __name: str) -> bool:
        return __name in self.data

    @staticmethod
    def FromStr(vmt: str):
        vmt = fix_vmt_string(vmt)
        data: dict = parse_vdf(vmt, True)
        shader = list(data)[0]
        return Material(shader, data[shader])
