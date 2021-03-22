from pprint import pprint
from .Side import Side
from .Brush import Brush
from vmf_tool.parser import parse
from os.path import basename, splitext
def readMap(vmf):
    mapData = parse(vmf)
    worldBrushes = []
    entityBrushes = []
    entities = []

    materials = []
    models = []
    modelTints = {}

    for solid in mapData.world.solids:
        sides = []
        for side in solid.sides:
            sides.append(Side(side))
            matName = side.material.lower()
            if matName not in materials and not matName.startswith("tools/") and not matName.startswith("liquids/"):
                materials.append(matName)
        worldBrushes.append(Brush(sides, "world", solid.id))
    

    for entity in mapData.entities:
        if entity.classname.startswith("prop"):
            entities.append(entity)
            if "model" not in entity:
                continue
            mdlName = entity.model.lower()
            if mdlName not in models:
                models.append(mdlName)
            # need to create duplicates of a model and its materails in order to apply tint
            if "rendercolor" in entity:
                if entity.rendercolor != "255 255 255":
                    mdlName = splitext(basename(mdlName))[0]
                    if mdlName not in modelTints:
                        modelTints[mdlName] = []
                    if entity.rendercolor not in modelTints[mdlName]:
                        modelTints[mdlName].append(entity.rendercolor)
        elif "solids" in entity:
            for solid in entity.solids:
                sides = []
                for side in solid.sides:
                    sides.append(Side(side))
                    matName = side.material.lower()
                    if matName not in materials and not matName.startswith("tools/") and not matName.startswith("liquids/"):
                        materials.append(matName)
                entityBrushes.append(Brush(sides, entity.classname, solid.id))
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
                entityBrushes.append(Brush(sides, entity.classname, solid.id))
        else:
            entities.append(entity)

    models = sorted(set(models))
    materials = sorted(set(materials))

    return {
        "worldBrushes": worldBrushes,
        "entityBrushes": entityBrushes,
        "entities": entities,
        "materials": materials,
        "models": models,
        "modelTints": modelTints,
        "sky": mapData.world.skyname.lower() if "skyname" in mapData.world else "sky"
    }
