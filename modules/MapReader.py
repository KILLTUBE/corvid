from modules.Vector3 import Vector3FromStr
from pprint import pprint
from typing import Mapping
from .Side import Side
from .Brush import Brush
from vmf_tool.parser import parse
def readMap(vmf):
    mapData = parse(vmf)
    worldBrushes = []
    entityBrushes = []
    entities = []

    skyBoxBrushes = []
    skyBoxEntityBrushes = []
    skyBoxEntities = []

    skyBoxId = -1
    skyBoxOrigin = "0 0 0"
    skyBoxScale = 16

    materials = []
    models = []

    for visgroup in mapData.visgroups.visgroups:
        if visgroup.name == "3dskybox":
            skyBoxId = visgroup.visgroupid
            break

    for solid in mapData.world.solids:
        sides = []
        for side in solid.sides:
            sides.append(Side(side))
            matName = side.material.lower()
            if matName not in materials and not matName.startswith("tools/") and not matName.startswith("liquids/"):
                materials.append(matName)
        if "editor" in solid:
            if "visgroupid" in solid.editor and solid.editor.visgroupid == skyBoxId:
                skyBoxBrushes.append(Brush(sides, "world", solid.id))
            else:
                worldBrushes.append(Brush(sides, "world", solid.id))
    

    for entity in mapData.entities:
        if entity.classname.startswith("prop"):
            if "editor" in entity:
                if "visgroupid" in entity.editor and entity.editor.visgroupid == skyBoxId:
                    skyBoxEntities.append(entity)
                else:
                    entities.append(entity)
            else:
                entities.append(entity)
            if "model" not in entity:
                continue
            mdlName = entity.model.lower()
            if mdlName not in models:
                models.append(mdlName)
        elif "solids" in entity:
            for solid in entity.solids:
                sides = []
                for side in solid.sides:
                    sides.append(Side(side))
                    matName = side.material.lower()
                    if matName not in materials and not matName.startswith("tools/") and not matName.startswith("liquids/"):
                        materials.append(matName)
                if "editor" in entity:
                    if "visgroupid" in entity.editor and entity.editor.visgroupid == skyBoxId:
                        skyBoxEntityBrushes.append(Brush(sides, entity.classname, solid.id))
                    else:
                        entityBrushes.append(Brush(sides, entity.classname, solid.id))
                else:
                    entityBrushes.append(Brush(sides, entity.classname, solid.id))
        elif "solid" in entity:
            if isinstance(entity.solid, str):
                if "editor" in entity:
                    if "visgroupid" in entity.editor and entity.editor.visgroupid == skyBoxId:
                        skyBoxEntities.append(entity)
                    else:
                        entities.append(entity)
                else:
                    entities.append(entity)
            else:
                sides = []
                for side in entity.solid.sides:
                    sides.append(Side(side))
                    matName = side.material.lower()
                    if matName not in materials and not matName.startswith("tools/") and not matName.startswith("liquids/"):
                        materials.append(matName)
                if "editor" in entity:
                    if "visgroupid" in entity.editor and entity.editor.visgroupid == skyBoxId:
                        skyBoxBrushes.append(Brush(sides, entity.classname, solid.id))
                    else:
                        entityBrushes.append(Brush(sides, entity.classname, solid.id))
                else:
                    entityBrushes.append(Brush(sides, entity.classname, solid.id))
        else:
            if "editor" in entity:
                if "visgroupid" in entity.editor and entity.editor.visgroupid == skyBoxId:
                    skyBoxEntities.append(entity)
                    if entity.classname == "sky_camera":
                        skyBoxScale = entity.scale
                        skyBoxOrigin = Vector3FromStr(entity.origin)
                else:
                    entities.append(entity)
            else:
                entities.append(entity)

    models = sorted(set(models))
    materials = sorted(set(materials))

    print("Skybox id:", skyBoxId)
    print("Skybox scale:", skyBoxScale)
    print("Skybox origin:", skyBoxOrigin)

    return {
        "worldBrushes": worldBrushes,
        "entityBrushes": entityBrushes,
        "entities": entities,
        "skyBoxId": skyBoxId,
        "skyBoxScale": float(skyBoxScale),
        "skyBoxOrigin": skyBoxOrigin,
        "skyBoxBrushes": skyBoxBrushes,
        "skyBoxEntities": skyBoxEntities,
        "skyBoxEntityBrushes": skyBoxEntityBrushes,
        "materials": materials,
        "models": models,
        "skyName": mapData.world.skyname.lower() if "skyname" in mapData.world else "sky"
    }
