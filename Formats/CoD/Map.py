from io import TextIOWrapper
from typing import List, Union
from Helpers.ListHelpers import Flatten
from Helpers.UtilFuncs import ParseQuotedKV
from Formats.BaseMap.Map import Map as BaseMap
from .Entity import Entity
from .Brush import Brush
from .Face import Face
from .Patch import Patch, PatchVert

class Map(BaseMap):
    __slots__ = ("flags",)

    flags: List['str']
    entities: List[Entity]

    def __init__(self) -> None:
        super().__init__()
        self.flags = []
        self.entities = []
    
    def __str__(self) -> str:
        res = "iwmap 4\n"

        for flag in self.flags:
            res += flag + "\n"
        
        self.entities = Flatten(self.entities)

        for i, entity in enumerate(self.entities):
            res += f"// entity {i}\n"
            res += str(entity)
        
        return res
    
    def Save(self, filePath: str):
        with open(filePath, "w") as file:
            file.truncate()
            file.write("iwmap 4\n")

            for flag in self.flags:
                file.write(flag + "\n")
            
            self.entities = Flatten(self.entities)

            for i, entity in enumerate(self.entities):
                file.write(f"// entity {i}\n")
                entity.Save(file)
    
    @staticmethod
    def Load(path: str, options: dict) -> 'Map':
        # modes
        NONE, ENTITY, BRUSH, PATCH = (0, 1, 2, 3)
        mode = NONE
        res = Map()

        with open(path, "r") as file:
            lines = file.readlines()

            if lines[0].strip() != "iwmap 4":
                print("Expeced \"iwmap 4\" in the first line of the map file. Exiting...")
                exit()
            
            i = 0

            while i < len(lines):
                line = lines[i].strip()

                if line == "iwmap 4" or line.startswith(("//", "guid", "decalLayerSort", "decalEditorSort")):
                    i += 1
                    continue
                
                elif line == "{":
                    if mode == NONE:
                        mode = ENTITY
                        res.entities.append(Entity())

                    elif mode == ENTITY:
                        if lines[i + 1].strip() in ("mesh", "curve"):
                            mode = PATCH

                        elif lines[i + 2].strip() in ("mesh", "curve"):
                            mode = PATCH

                        if mode == PATCH:
                            j = i + 1
                            _type = material = lmap = size = samplesize = smoothing = layer = patch = None
                            toolflags = contents = []
                            
                            while mode == PATCH:
                                _line = lines[j].strip()

                                if _line in ("mesh", "curve"):
                                    _type = _line

                                elif _line.startswith("toolFlags") and _line[-1] == ";":
                                    toolflags = _line[10:-1].split()

                                elif _line.startswith("contents") and _line[-1] == ";":
                                    contents = _line[9:-1].split()

                                elif _line.startswith("layer "):
                                    layer = _line[6:]

                                elif _line.startswith("lightmap_"):
                                    material = lines[j - 1].strip()
                                    lmap = _line

                                    if lines[j + 1].strip().startswith("smoothing"):
                                        smoothing = lines[j + 1].strip().split()[1]
                                        inf = lines[j + 2].strip().split()

                                    else:
                                        inf = lines[j + 1].strip().split()

                                    size, samplesize = (int(inf[0]), int(inf[1])), int(inf[2])
                                    res.entities[-1].geo.append(Patch(_type, toolflags, contents, material, lmap, size, samplesize, smoothing, layer))
                                    res.AddMaterial(material)

                                elif _line == "(":
                                    res.entities[-1].geo[-1].verts.append([])

                                elif _line.startswith("v "):
                                    res.entities[-1].geo[-1].verts[-1].append(PatchVert.FromStr(_line))

                                elif _line == ")":
                                    if len(res.entities[-1].geo[-1].verts[-1]) != size[1]:
                                        print("Not enough verts in patch on line" + j)

                                elif _line == "}":
                                    mode = ENTITY
                                    i = j + 2
                                    break

                                j += 1

                            continue

                        else:
                            mode = BRUSH
                            brush = Brush()
                            res.entities[-1].geo.append(brush)

                elif line == "}":
                    if mode == BRUSH:
                        mode = ENTITY

                    elif mode == ENTITY:
                        mode = NONE

                elif line.startswith('"'):
                    if mode == NONE:
                        res.flags.append(line)

                    elif mode == ENTITY:
                        key, value = ParseQuotedKV(line)
                        res.entities[-1][key] = value

                        if key == "model":
                            res.AddModel(value)

                elif line.startswith("("):
                    if mode == BRUSH:
                        face = Face.FromStr(line)
                        res.entities[-1].geo[-1].AddFace(face)
                        res.AddMaterial(face.material)
                
                elif line.startswith("contents") and line[-1] == ";":
                    if mode in  (BRUSH, PATCH):
                        res.entities[-1].geo[-1].contents = line[9:-1].split()
                
                elif line.startswith("layer"):
                    layer = line[6:]

                    if mode == ENTITY:
                        res.entities[-1].layer = layer

                    elif mode == BRUSH or mode == PATCH:
                        res.entities[-1].geo[-1].layer = layer
                else:
                    if line != "":
                        print("well: ", line)

                i += 1
            
        return res