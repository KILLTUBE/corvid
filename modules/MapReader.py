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

    materials = []
    models = []

    for solid in mapData.world.solids:
        sides = []
        for side in solid.sides:
            sides.append(Side(side))
            matName = side.material.lower()
            if matName not in materials and not matName.startswith("tools/") and not matName.startswith("liquids/"):
                materials.append(matName)
        worldBrushes.append(Brush(sides))
    

    for entity in mapData.entities:
        if entity.classname.startswith("prop"):
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
                entityBrushes.append(Brush(sides))
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
                entityBrushes.append(Brush(sides))
        else:
            entities.append(entity)
    
    models = sorted(set(models))
    materials = sorted(set(materials))

    return {
        "worldBrushes": worldBrushes,
        "entityBrushes": entityBrushes,
        "entities": entities,
        "materials": materials,
        "models": models
    }
