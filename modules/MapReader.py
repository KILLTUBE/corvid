from typing import Dict, List

from modules.Static import newPath, VecFromStr
from .Side import Side
from .Brush import Brush
from .vdfutils import parse_vdf
from os.path import splitext
from glm import vec3

def readMap(vmf):
    mapData = parse_vdf(vmf, allowRepeats=True)
    worldBrushes: List[Brush] = []
    entityBrushes: List[Brush] = []
    entities = []

    skyBrushes: List[Brush] = []
    skyEntityBrushes: List[Brush] = []
    skyEntities = []

    skyBoxId = -1
    skyBoxScale = 16
    skyBoxOrigin = vec3(0, 0, 0)

    materials = []
    models = []
    modelTints = {}
    modelSkins = {}
    skinTints: Dict[str, Dict[int, List[str]]] = {}

    if "visgroups" in mapData and "visgroup" in mapData["visgroups"]:
        for visgroup in (mapData["visgroups"]["visgroup"] if isinstance(mapData["visgroups"]["visgroup"], list) else [mapData["visgroups"]["visgroup"]]):
            if visgroup["name"] == "3dskybox":
                skyBoxId = visgroup["visgroupid"]
            if "visgroup" in visgroup:
                for nested in (visgroup["visgroup"] if isinstance(visgroup["visgroup"], list) else [visgroup["visgroup"]]):
                    if nested["name"] == "3dskybox":
                        skyBoxId = nested["visgroupid"]

    world = mapData["world"]

    if "solid" in world:
        for solid in (world["solid"] if isinstance(world["solid"], list) else [world["solid"]]):
            sides = []
            for side in (solid["side"] if isinstance(solid["side"], list) else [solid["side"]]):
                sides.append(Side(side))
                matName = side["material"].lower()
                if matName not in materials and not matName.startswith("tools/"):
                    materials.append(matName)
            if "editor" in solid:
                if "visgroupid" in solid["editor"] and solid["editor"]["visgroupid"] == skyBoxId:
                    skyBrushes.append(Brush(sides, "world", solid["id"]))
                else:
                    worldBrushes.append(Brush(sides, "world", solid["id"]))
            else:
                worldBrushes.append(Brush(sides, "world", solid["id"]))

    if "entity" not in mapData:
        mapData["entity"] = []

    for entity in (mapData["entity"] if isinstance(mapData["entity"], list) else [mapData["entity"]]):
        if entity["classname"].startswith("prop"):
            if "editor" in entity:
                if "visgroupid" in entity["editor"] and entity["editor"]["visgroupid"] == skyBoxId:
                    skyEntities.append(entity)
                else:
                    entities.append(entity)
            else:
                entities.append(entity)
            if "model" not in entity:
                continue
            mdlName = entity["model"].lower()
            if mdlName not in models:
                models.append(mdlName)

            # create duplicate models for models that have skins and color tints (and both)
            if "skin" in entity or "rendercolor" in entity:
                if "rendercolor" in entity and entity["rendercolor"] != "255 255 255" and "skin" in entity and entity["skin"] != "0":
                    mdlName = splitext(newPath(mdlName))[0]
                    skin = int(entity["skin"])
                    if mdlName not in skinTints:
                        skinTints[mdlName] = {}
                    if skin not in skinTints[mdlName]:
                        skinTints[mdlName][skin] = []
                    if entity["rendercolor"] not in skinTints[mdlName][skin]:
                        skinTints[mdlName][skin].append(entity["rendercolor"])
                elif "rendercolor" in entity and entity["rendercolor"] != "255 255 255":
                    mdlName = splitext(newPath(mdlName))[0]
                    if mdlName not in modelTints:
                        modelTints[mdlName] = []
                    if entity["rendercolor"] not in modelTints[mdlName]:
                        modelTints[mdlName].append(entity["rendercolor"])
                elif "skin" in entity and entity["skin"] != "0":
                    skin = int(entity["skin"])
                    mdlName = splitext(newPath(mdlName))[0]
                    if mdlName not in modelSkins:
                        modelSkins[mdlName] = []
                    if skin not in modelSkins[mdlName]:
                        modelSkins[mdlName].append(skin)

        elif entity["classname"] == "func_bomb_target":
            entities.append(entity)
        elif "solid" in entity:
            solidVal = entity["solid"]
            solids = solidVal if isinstance(solidVal, list) else [solidVal]
            # check if it's a string (some entities have "solid" as a plain key)
            if isinstance(solids[0], str):
                entities.append(entity)
            else:
                for solid in solids:
                    sides = []
                    for side in (solid["side"] if isinstance(solid["side"], list) else [solid["side"]]):
                        sides.append(Side(side))
                        matName = side["material"].lower()
                        if matName not in materials and not matName.startswith("tools/"):
                            materials.append(matName)
                    if "editor" in solid:
                        if "visgroupid" in solid["editor"] and solid["editor"]["visgroupid"] == skyBoxId:
                            skyEntityBrushes.append(Brush(sides, entity["classname"], solid["id"]))
                        else:
                            entityBrushes.append(Brush(sides, entity["classname"], solid["id"], entity))
                    else:
                        entityBrushes.append(Brush(sides, entity["classname"], solid["id"], entity))
        elif entity["classname"] == "sky_camera":
            skyBoxOrigin = VecFromStr(entity["origin"], 3)
            skyBoxScale = float(entity["scale"])
        elif entity["classname"] == "info_overlay":
            matName = entity["material"].lower()
            if matName not in materials:
                materials.append(matName)
            entities.append(entity)
        elif entity["classname"] == "infodecal":
            matName = entity["texture"].lower()
            if matName not in materials:
                materials.append(matName)
            entities.append(entity)
        else:
            if "editor" in entity:
                if "visgroupid" in entity["editor"] and entity["editor"]["visgroupid"] == skyBoxId:
                    skyEntities.append(entity)
                else:
                    entities.append(entity)
            else:
                entities.append(entity)

    models = sorted(set(models))
    materials = sorted(set(materials))

    if skyBoxId == -1:
        print("3d sky box not selected. It will be converted as a smaller version of itself...")

    return {
        "worldBrushes": worldBrushes,
        "entityBrushes": entityBrushes,
        "entities": entities,

        "skyBrushes": skyBrushes,
        "skyEntityBrushes": skyEntityBrushes,
        "skyEntities": skyEntities,
        "skyBoxId": skyBoxId,
        "skyBoxOrigin": skyBoxOrigin,
        "skyBoxScale": skyBoxScale,

        "materials": materials,
        "models": models,
        "modelTints": modelTints,
        "modelSkins": modelSkins,
        "skinTints": skinTints,

        "sky": world["skyname"].lower() if "skyname" in world else "sky"
    }
