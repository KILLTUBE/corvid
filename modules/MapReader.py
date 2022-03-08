from pprint import pprint
from typing import List

from modules.Static import newPath
from .Side import Side
from .Brush import Brush
from vmf_tool.parser import parse
from os.path import basename, splitext
from .Vector3 import Vector3

def readMap(vmf):
    mapData = parse(vmf)
    worldBrushes: List[Brush] = []
    entityBrushes: List[Brush] = []
    entities = []

    skyBrushes: List[Brush] = []
    skyEntityBrushes: List[Brush] = []
    skyEntities = []

    skyBoxId = -1
    skyBoxScale = 16
    skyBoxOrigin = Vector3.FromStr("0 0 0")

    materials = []
    models = []
    modelTints = {}
    modelSkins = {}

    if "visgroups" in mapData:
        if "visgroup" in mapData.visgroups:
            if mapData.visgroups.visgroup.name == "3dskybox":
                skyBoxId = mapData.visgroups.visgroup.visgroupid
        if "visgroups" in mapData.visgroups:
            for visgroup in mapData.visgroups.visgroups:
                if visgroup.name == "3dskybox":
                    skyBoxId = visgroup.visgroupid

    for solid in mapData.world.solids:
        sides = []
        for side in solid.sides:
            sides.append(Side(side))
            matName = side.material.lower()
            if matName not in materials and not matName.startswith("tools/") and not matName.startswith("liquids/"):
                materials.append(matName)
        if "editor" in solid:
            if "visgroupid" in solid.editor and solid.editor.visgroupid == skyBoxId:
                skyBrushes.append(Brush(sides, "world", solid.id))
            else:
                worldBrushes.append(Brush(sides, "world", solid.id))
        else:
            worldBrushes.append(Brush(sides, "world", solid.id))
    

    for entity in mapData.entities:
        if entity.classname.startswith("prop"):
            if "editor" in entity:
                if "visgroupid" in entity.editor and entity.editor.visgroupid == skyBoxId:
                    skyEntities.append(entity)
                else:
                    entities.append(entity)
            else:
                entities.append(entity)
            if "model" not in entity:
                continue
            mdlName = entity.model.lower()
            if mdlName not in models:
                models.append(mdlName)
            # need to create duplicates of a model and its materails in order to apply tint
            if "rendercolor" in entity:
                if entity.rendercolor != "255 255 255":
                    mdlName = splitext(newPath(mdlName))[0]
                    if mdlName not in modelTints:
                        modelTints[mdlName] = []
                    if entity.rendercolor not in modelTints[mdlName]:
                        modelTints[mdlName].append(entity.rendercolor)
            # need to create duplicates of a model and its materails in order to use different skins
            if "skin" in entity:
                if entity.skin != "0":
                    skin = int(entity.skin)
                    mdlName = splitext(newPath(mdlName))[0]
                    if mdlName not in modelSkins:
                        modelSkins[mdlName] = []
                    if skin not in modelSkins[mdlName]:
                        modelSkins[mdlName].append(skin)

        elif entity["classname"] == "func_bomb_target":
            entities.append(entity)
        elif "solids" in entity:
            for solid in entity.solids:
                sides = []
                for side in solid.sides:
                    sides.append(Side(side))
                    matName = side.material.lower()
                    if matName not in materials and not matName.startswith("tools/") and not matName.startswith("liquids/"):
                        materials.append(matName)
                if "editor" in solid:
                    if "visgroupid" in solid.editor and solid.editor.visgroupid == skyBoxId:
                        skyEntityBrushes.append(Brush(sides, entity.classname, solid.id))
                    else:
                        entityBrushes.append(Brush(sides, entity.classname, solid.id, entity))
                else:
                    entityBrushes.append(Brush(sides, entity.classname, solid.id, entity))
        elif "solid" in entity:
            if isinstance(entity.solid, str):
                entities.append(entity)
            else:
                sides = []
                for side in entity.solid.sides:
                    sides.append(Side(side))
                    matName = side.material.lower()
                    if matName not in materials and not matName.startswith("tools/") and not matName.startswith("liquids/"):
                        materials.append(matName)
                if "editor" in solid:
                    if "visgroupid" in solid.editor and solid.editor.visgroupid == skyBoxId:
                        skyEntityBrushes.append(Brush(sides, entity.classname, solid.id))
                    else:
                        entityBrushes.append(Brush(sides, entity.classname, solid.id, entity))
                else:
                    entityBrushes.append(Brush(sides, entity.classname, solid.id, entity))
        elif entity.classname == "sky_camera":
            skyBoxOrigin = Vector3.FromStr(entity.origin)
            skyBoxScale = float(entity.scale)
        elif entity.classname == "info_overlay":
            matName = entity.material.lower()
            if matName not in materials:
                materials.append(matName)
            entities.append(entity)
        elif entity.classname == "infodecal":
            matName = entity.texture.lower()
            if matName not in materials:
                materials.append(matName)
            entities.append(entity)
        else:
            if "editor" in entity:
                if "visgroupid" in entity.editor and entity.editor.visgroupid == skyBoxId:
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
        
        "sky": mapData.world.skyname.lower() if "skyname" in mapData.world else "sky"
    }
