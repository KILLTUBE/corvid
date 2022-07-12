from copy import copy
from typing import List, Union
from modules.Brush import Brush
from .Entity import Entity
from .Face import Face
from .Patch import Patch

class Map:
    flags: List['str']
    entities: List[Entity]

    def __init__(self) -> None:
        self.flags = []
        self.entities = []
    
    def Filter(self, filters: dict):
        newlist: List[Entity] = []
        for entity in self.entities:
            if entity["classname"] in filters["bad_entities"]:
                continue
            elif entity["classname"] == "misc_prefab" and entity["model"] in filters["bad_prefabs"]:
                continue
            elif entity["classname"] in filters["filtered_entities"]:
                newkv = {}

                for key, value in entity.properties.items():
                    if key in ("classname", "origin", "angles", "spawnflags"):
                        newkv[key] = value
                    elif key in filters["filtered_entities"][entity["classname"]]["allowed_keys"]:
                        newkv[key] = value

                entity.properties = newkv

            newgeo: List[Union[Patch, Brush]] = []

            for geo in entity.geo:
                if isinstance(geo, Brush):
                    brush = copy(geo)

                    for content in geo.contents:
                        if content not in filters["allowed_content"]:
                            brush.contents.remove(content)

                    for flag in geo.toolflags:
                        if flag not in filters["allowed_toolflags"]:
                            brush.toolflags.remove(flag)
                    
                    for face in brush.faces:
                        if face.texture in filters["textures"]["replace"]:
                            face.texture = filters["textures"]["replace"][face.texture]
                        elif face.texture in filters["textures"]["delete"]:
                            face.texture = "case"
                    
                    newgeo.append(brush)

                elif isinstance(geo, Patch):
                    patch = copy(geo)

                    for content in geo.contents:
                        if content not in filters["allowed_content"]:
                            patch.contents.remove(content)

                    for flag in geo.toolflags:
                        if flag not in filters["allowed_toolflags"]:
                            patch.toolflags.remove(flag)
                    
                    if patch.texture in filters["textures"]["replace"]:
                        patch.texture = filters["textures"]["replace"][patch.texture]
                    elif patch.texture in filters["textures"]["delete"] or patch.texture.endswith(tuple(filters["textures"]["delete_endswith"])):
                        continue
                    elif patch.texture in filters["textures"]["delete"] or patch.texture.startswith(tuple(filters["textures"]["delete_startswith"])):
                        continue
                    elif filters["removeblendpatches"] and patch.blend:
                        continue
                    elif filters["moveblendpatches"] and patch.blend:
                        patch.Nudge(filters["blendpatchesdist"])

                    if filters["resetlightmaps"] and not filters["removelightmaps"]:
                        patch.ResetLightmap(1)                                      

                    if filters["removelightmaps"]:
                        patch.nolightmap = True

                    if patch.size[0] > filters["maxpatchsize"] or patch.size[1] > filters["maxpatchsize"]:
                        sliced = patch.Slice(filters["maxpatchsize"])
                        
                        for newpatch in sliced:
                            newgeo.append(newpatch)
                    
                    else:
                        newgeo.append(patch)
                
                else:
                    print("Invalid geo.", type(geo), "is not a valid geo type.")
                    exit()

            entity.geo = newgeo
            newlist.append(entity)
        
        self.entities = newlist
    
    def Save(self, filename):
        with open(filename, "w") as file:
            file.write("iwmap 4\n")

            for flag in self.flags:
                file.write(flag + "\n")

            for i, entity in enumerate(self.entities):
                file.write(f"// Entity {i}\n")
                file.write(str(entity))
    
    def __str__(self) -> str:
        res = "iwmap 4\n"

        for flag in self.flags:
            res += flag + "\n"
        
        for i, entity in enumerate(self.entities):
            res += f"// entity {i}\n"
            res += str(entity)
        
        return res
    
