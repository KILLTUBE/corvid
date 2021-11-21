from typing import Dict
from modules.Brush import Brush
from modules.Overlay import Overlay
from modules.SourceDir import SourceDir
from .Side import Side
from .MapReader import readMap
from .Vector2 import Vector2
from .Vector3 import Vector3
from .Gdt import Gdt
from os.path import basename, splitext
from os import makedirs
from tempfile import gettempdir
from .AssetExporter import *
from .AssetConverter import convertImages, convertModels
from shutil import rmtree

def convertSide(side: Side, matSize, origin=Vector3(0, 0, 0), scale=1):
    # skip invalid sides
    if len(side.points) < 3:
        print(f"Brush face {side.id} has less than 3 vertices. Skipping...")
        return ""

    res = f"// Side {side.id}\n"
    points = side.points

    material = newPath(side.material)

    # get uv points
    for point in side.points:
        side.uvs.append(side.getUV(point, matSize[material]))
    uvs: list[Vector2] = side.uvs

    if len(points) % 2 == 1:
        points.append(points[-1])
        uvs.append(uvs[-1])
    count = len(points)
    rows = int(count / 2)

    if side.material.lower().strip().startswith("liquids"):
        side.material = "clip_water"

    # material = "me_floorsmoothconcrete"
    
    res += (
        "{\n" +
        "mesh\n" +
        "{\n" +
        "" + material + "\n" +
        "lightmap_gray\n" +
        "" + str(rows) + " 2 " + str(side.lightmapScale) + " 8\n"
    )

    for i in range(rows):
        p1 = {
            "pos": str((points[i] - origin) * scale),
            "uv": str(uvs[i] * side.texSize),
            "lm": str(uvs[i] * side.lightmapScale)
        }
        p2 = {
            "pos": str((points[count - i - 1] - origin) * scale),
            "uv": str(uvs[count - i - 1] * side.texSize),
            "lm": str(uvs[count - i - 1] * side.lightmapScale)
        }
        res += (
            "(\n" +
            f'v {p1["pos"]} t {p1["uv"]} {p1["lm"]}\n' +
            f'v {p2["pos"]} t {p2["uv"]} {p2["lm"]}\n' +
            ")\n"
        )

    res += (
        "}\n" +
        "}\n"
    )
    return res

def getDispPoints(p1: Vector3, p2: Vector3, uv1: Vector2, uv2: Vector2, power: int):
    res = []
    rowCount = int(2 ** power) + 1
    for i in range(rowCount):
        res.append({
            "pos": p1.lerp(p2, 1 / (rowCount - 1) * i),
            "uv": uv1.lerp(uv2, 1 / (rowCount - 1) * i)
        })
    return res

def convertDisplacement(side: Side, matSize, origin=Vector3(0, 0, 0), scale=1):
    res = f"// Side {side.id}\n"
    points = side.points
    material = newPath(side.material)
    
    # get uv points
    for point in side.points:
        side.uvs.append(side.getUV(point, matSize[material]))

    if len(points) != 4:
        print(f"Displacement has {len(points)}. Displacements can have 4 points only. Side id: {side.id}\n")
        for point in points:
            print(point)
        return ""
    
    uvs: list[Vector2] = side.uvs
    disp: dict = side.dispinfo
    power: int = int(disp["power"])
    numVerts: int = int(2 ** power) + 1
    s: int = 0
    for i in range(4):
        if points[i] == disp["startpos"]:
            s = i
            break

    a = points[s]
    b = points[(s + 1) % 4]
    c = points[(s + 2) % 4]
    d = points[(s + 3) % 4]

    UVa = uvs[s]
    UVb = uvs[(s + 1) % 4]
    UVc = uvs[(s + 2) % 4]
    UVd = uvs[(s + 3) % 4]

    ab = getDispPoints(a, b, UVa, UVb, power)
    dc = getDispPoints(d, c, UVd, UVc, power)

    rows = []
    for i in range(len(ab)):
        rows.append(
            getDispPoints(ab[i]["pos"], dc[i]["pos"], ab[i]["uv"], dc[i]["uv"], power))

    alpha = False

    # material = "me_floorsmoothconcrete"

    res += (
        "{\n" +
        "mesh\n" +
        "{\n" +
        "" + material + "\n" +
        "lightmap_gray\n"
        "" + str(len(rows[0])) + " " + str(len(rows[0])) + " " + str(side.lightmapScale) + " 8\n"
    )

    for i in range(numVerts):
        row = rows[i]
        res += "(\n"
        for j in range(numVerts):
            if disp["row"][j]["alphas"][i] != 0 and alpha != True:
                alpha = True
            col = row[j]
            pos = (col["pos"] + Vector3(0, 0, disp["elevation"]) +
                   (disp["row"][j]["normals"][i] * disp["row"][j]["distances"][i]))
            uv = (col["uv"] * side.texSize) * 1
            lm = col["uv"] * (side.lightmapScale)
            res += f"v {(pos - origin) * scale} t {uv} {lm}\n"
        res += ")\n"
    res += ("}\n" +
            "}\n")

    if not alpha:
        return res
    if material + "_" not in matSize:
        return res

    res += (
        "{\n" +
        "mesh\n" +
        "{\n" +
        "" + material + "~blend\n" +
        "lightmap_gray\n" +
        "" + str(len(rows[0])) + " " + str(len(rows[0])
                                              ) + " " + str(side.lightmapScale) + " 8\n"
    )

    for i in range(numVerts):
        row = rows[i]
        res += "(\n"
        for j in range(numVerts):
            col = row[j]
            pos = (col["pos"] + Vector3(0, 0, disp["elevation"]) +
                   (disp["row"][j]["normals"][i] * disp["row"][j]["distances"][i]))
            uv = (col["uv"] * side.texSize) * 1
            lm = col["uv"] * (side.lightmapScale)
            if disp["row"][j]["alphas"][i] == 0:
                res += f"v {(pos - origin) * scale} c 255 255 255 0 t {uv} {lm}\n"
            else:
                color = "255 255 255 " + str(disp["row"][j]["alphas"][i])
                res += f"v {(pos - origin) * scale} c {color} t {uv} {lm}\n"
        res += ")\n"
    res += ("}\n" +
            "}\n")

    return res

def convertBrush(brush: Brush, world=True, BO3=False, mapName="", origin=Vector3(0, 0, 0), scale=1, matSizes: dict={}, brushConversion=False, sideDict: dict={}):
    tools = {
        "toolsnodraw": "caulk",
        "toolsclip": "clip",
        "toolsplayerclip": "clip",
        "toolsinvisible": "clip",
        "toolsinvisibleladder": "clip",
        "toolsnpcclip": "clip",
        "toolsgrenadeclip": "clip_missile",
        "toolsareaportal": "portal_nodraw",
        "toolsblocklight": "shadowcaster",
        "toolshint": "hint",
        "toolsskip": "skip",
        "toolsskybox": "sky" if BO3 else f"{mapName}_sky"
    }

    resBrush = f"// Brush {brush.id}\n" 
    resBrush = "{\n"
    if not world:
        resBrush += "contents detail;\n"
    resPatch = ""

    for side in brush.sides:        
        if len(side.points) >= 3:
            sideDict[side.id] = side

        if side.hasDisp:
            resPatch += convertDisplacement(side, matSizes, origin, scale)
            continue
        
        if brush.hasDisp and not side.hasDisp:
            continue
        p1 = (side.p1 - origin) * scale
        p2 = (side.p2 - origin) * scale
        p3 = (side.p3 - origin) * scale
        resBrush += f"( {p1} ) ( {p2} ) ( {p3} ) "

        if side.material.startswith("tools"):
            mat = basename(side.material)
            if mat in tools:
                resBrush += tools[mat] + " 128 128 0 0 0 0 lightmap_gray 16384 16384 0 0 0 0\n"
                continue
            else:
                resBrush += "clip 128 128 0 0 0 0 lightmap_gray 16384 16384 0 0 0 0\n"
                continue

        elif side.material.startswith("liquid"):
                resBrush += "clip_water 128 128 0 0 0 0 lightmap_gray 16384 16384 0 0 0 0\n"
                continue
        
        elif not brushConversion:
            resBrush += "caulk 128 128 0 0 0 0 lightmap_gray 16384 16384 0 0 0 0\n"
            resPatch += convertSide(side, matSizes, origin, scale)
        
        else:
            mat = newPath(side.material)
            side.texSize = matSizes.get(mat, Vector2(512, 512))
            tex = side.getTexCoords()
            if tex is not None:
                resBrush += f"{mat} {tex}\n"
            else:
                resBrush += "caulk 128 128 0 0 0 0 lightmap_gray 16384 16384 0 0 0 0\n"
                resPatch += convertSide(side, matSizes, origin, scale)
    
    resBrush += "}\n"
    
    if brush.hasDisp:
        return resPatch

    return resBrush + resPatch

def convertEntity(entity, id="", geo=""):
    res = f"// Entity {id}\n" if id != "" else ""
    res += "{\n"
    for key, value in entity.items():
        res += f'"{key}" "{value}"\n'
    if geo != "":
        res += geo
    res += "}\n"
    return res

def convertLight(entity):
    if "_light" in entity:
        _color = entity["_light"].split(" ")
        if len(_color) == 3:
            _color.append(500)
    else:
        _color = [0, 0, 0, 500]
    # In Radiant, color value of light entities range between 0 and 1 whereas it varies between 0 and 255 in Source engine
    color = (Vector3(_color[0], _color[1], _color[2]) / 255).round(3)
    return convertEntity({
        "classname": "light",
        "origin": entity["origin"],
        "_color": color,
        "radius": _color[3],
        "intensity": "1"
    }, entity["id"])

def convertSpotLight(entity, BO3=False):
    if "_light" in entity:
        _color = entity["_light"].split(" ")
        if len(_color) == 3:
            _color.append(500)
    else:
        _color = [0, 0, 0, 500]
    # In Radiant, color value of light entities range between 0 and 1 whereas it varies between 0 and 255 in Source engine
    color = (Vector3(_color[0], _color[1], _color[2]) / 255).round(3)
    _origin = entity["origin"].split(" ")
    origin = Vector3(_origin[0], _origin[1], _origin[2])
    if "_fifty_percent_distance" in entity and "_zero_percent_distance" not in entity:
        radius = int(entity["_fifty_percent_distance"])
    elif "_zero_percent_distance" in entity and "_fifty_percent_distance" not in entity:
        radius = int(entity["_zero_percent_distance"])
    elif "_fifty_percent_distance" in entity and "_zero_percent_distance" in entity:
        radius = (int(entity["_fifty_percent_distance"]) * 2 + int(entity["_zero_percent_distance"])) / 2
    else:
        radius = 250
    
    if not BO3:
        res = convertEntity({
            "classname": "light",
            "origin": entity["origin"],
            "_color": color,
            "radius": radius,
            "intensity": "1",
            "target": "spotlight_" + entity["id"],
            "fov_outer": entity["_cone"],
            "fov_inner": entity["_inner_cone"],
        }, entity["id"])
        res += convertEntity({
            "classname": "info_null",
            "origin": origin + Vector3(0, 0, -float(_color[3])),
            "targetname": "spotlight_" + entity["id"]
        })
    else:
        angles = Vector3.FromStr(entity["angles"])
        pitch = float(entity["pitch"])
        res = convertEntity({
            "classname": "light",
            "origin": entity["origin"],
            "_color": color,
            "PRIMARY_TYPE": "PRIMARY_SPOT",
            "angles": Vector3(angles.x, pitch, angles.z),
            "radius": radius,
            "fov_outer": entity["_cone"],
            "fov_inner": entity["_inner_cone"],
        }, entity["id"])
    return res

def convertRope(entity, skyOrigin=Vector3(0, 0, 0), scale=1, curve=False, ropeDict: dict={}):
    # sadly, cod 4 does not support rope entities, so we have to create curve patches for them instead
    if curve:
        if entity["classname"] == "move_rope":
            ropeDict["start"][entity["NextKey"] if "NextKey" in entity else entity["id"]] = {
                "origin": (Vector3.FromStr(entity["origin"]) - skyOrigin) * scale,
                "target": entity["NextKey"] if "NextKey" in entity else entity["id"],
                "slack": float(entity["Slack"]),
                "width": float(entity["Width"]),
                "id": entity["id"]
            }
            if "targetname" in entity:
                ropeDict["end"][entity["targetname"] if "targetname" in entity else entity["id"]] = {
                    "origin": (Vector3.FromStr(entity["origin"]) - skyOrigin) * scale,
                    "targetname": entity["targetname"] if "targetname" in entity else entity["id"],
                    "id": entity["id"]
                }
        else:
            ropeDict["end"][entity["targetname"]] = {
                "origin": (Vector3.FromStr(entity["origin"]) - skyOrigin) * scale,
                "targetname": entity["targetname"],
                "id": entity["id"]
            }
            if "NextKey" in entity:
                ropeDict["start"][entity["NextKey"]] = {
                    "origin": (Vector3.FromStr(entity["origin"]) - skyOrigin) * scale,
                    "target": entity["NextKey"],
                    "slack": float(entity["Slack"]),
                    "width": float(entity["Width"]),
                    "id": entity["id"]
                }
    else:
        res = ""
        if entity["classname"] == "move_rope":
            origin = (Vector3.FromStr(entity["origin"]) - skyOrigin) * scale
            res += convertEntity({
                "classname": "rope",
                "origin": origin,
                "target": entity["NextKey"] if "NextKey" in entity else entity["id"],
                "length_scale": float(entity["Slack"]) / 128,
                "width": float(entity["Width"]) * 3
            }, entity["id"])
            if "targetname" in entity:
                origin = (Vector3.FromStr(entity["origin"]) - skyOrigin) * scale
                res += convertEntity({
                    "classname": "info_null",
                    "origin": origin,
                    "targetname": entity["targetname"] if "targetname" in entity else entity["id"]
                }, entity["id"])
        else:
            origin = (Vector3.FromStr(entity["origin"]) - skyOrigin) * scale
            res += convertEntity({
                "classname": "info_null",
                "origin": origin,
                "targetname": entity["targetname"]
            }, entity["id"])
            if "NextKey" in entity:
                res += convertEntity({
                    "classname": "rope",
                    "origin": origin,
                    "target": entity["NextKey"],
                    "length_scale": float(entity["Slack"]) / 125,
                    "width": entity["width"] if "width" in entity else "1"
                }, entity["id"])
        return res

def convertRopeAsCurve(start: Vector3, end: Vector3, slack: float, width: float=1):
    mid: Vector3 = start.lerp(end, 0.5)
    mid.z -= slack

    normal = (start - mid).cross(end -mid).normalize()
    n = normal * width
    up = Vector3(0, 0, width)
    return (
        "{\n"
        + "curve\n"
        + "{\n"
        + "global_wires\n"
        + "lightmap_gray\n"
        + "5 3 16 8\n"
        + "(\n"
        + f"v {start} t 1 1\n"
        + f"v {mid} t 1 1\n"
        + f"v {end} t 1 1\n"
        + ")\n"
        + "(\n"
        + f"v {start + n} t 1 1\n"
        + f"v {mid + n} t 1 1\n"
        + f"v {end + n} t 1 1\n"
        + ")\n"
        + "(\n"
        + f"v {start + n} t 1 1\n"
        + f"v {mid + n} t 1 1\n"
        + f"v {end + n} t 1 1\n"
        + ")\n"
        + "(\n"
        + f"v {start - n + up} t 1 1\n"
        + f"v {mid - n + up} t 1 1\n"
        + f"v {end - n + up} t 1 1\n"
        + ")\n"
        + "(\n"
        + f"v {start} t 1 1\n"
        + f"v {mid} t 1 1\n"
        + f"v {end} t 1 1\n"
        + ")\n"
        + "}\n"
        + "}\n"
    )

def convertProp(entity, BO3=False, skyOrigin=Vector3(0, 0, 0), scale=1):
    origin = (Vector3.FromStr(entity["origin"]) - skyOrigin) * scale
    modelScale = float(entity["uniformscale"] if "uniformscale" in entity else entity["modelscale"] if "modelscale" in entity else "1") * scale
    if "model" not in entity:
        return convertEntity({
            "classname": "info_null",
            "original_classname": entity["classname"],
            "origin": origin
        }, entity["id"])

    modelName = "m_" + splitext(newPath(entity["model"]))[0]

    if BO3 and "rendercolor" in entity:
        if entity["rendercolor"] != "255 255 255":
            modelName += "_" + Vector3.FromStr(entity["rendercolor"]).toHex()

    return convertEntity({
        "classname": "dyn_model" if entity["classname"].startswith("prop_physics") else "misc_model",
        "model": modelName,
        "origin": origin,
        "angles": entity["angles"],
        "spawnflags": "16" if entity["classname"].startswith("prop_physics") else "",
        "modelscale": modelScale
    }, entity["id"])

def convertCubemap(entity):
    return convertEntity({
        "classname": "reflection_probe",
        "origin": entity["origin"]
    }, entity["id"])

def convertSpawner(entity):
    spawners = {
        "info_player_terrorist": "mp_tdm_spawn_axis_start",
        "info_player_counterterrorist": "mp_tdm_spawn_allies_start",
        "info_deathmatch_spawn": "mp_dm_spawn",
        "info_player_deathmatch": "mp_dm_spawn",
        "info_player_start": "info_player_start",
    }
    if entity["classname"] in spawners:
        classname = spawners[entity["classname"]]
    else:
        #print(f'Unknown spawner entity: {entity["classname"]}')
        return ""
    origin = Vector3.FromStr(entity["origin"])
    origin.z += 32 # otherwise they go through the floor
    res = convertEntity({
        "classname": classname,
        "origin": origin,
        "angles": entity["angles"]
    }, entity["id"])

    if classname == "info_player_start":
        res += convertEntity({
            "classname": "mp_global_intermission",
            "origin": entity["origin"]
        }, entity["id"])

    return res

def exportMap(vmfString, vpkFiles=[], gameDirs=[], BO3=False, skipMats=False, skipModels=False, mapName="", brushConversion=False, ropeCurve=False):
    # create temporary directories to extract assets
    copyDir = gettempdir() + "/corvid"
    try:
        rmtree(copyDir)
    except:
        pass
    try:
        makedirs(f"{copyDir}/mdl")
        makedirs(f"{copyDir}/mat")
        makedirs(f"{copyDir}/mdlMats")
        makedirs(f"{copyDir}/matTex")
        makedirs(f"{copyDir}/mdlTex")
        if not BO3:
            makedirs(f"{copyDir}/converted/bin")
        makedirs(f"{copyDir}/converted/model_export/corvid")
        makedirs(f"{copyDir}/converted/source_data")
        makedirs(f"{copyDir}/converted/texture_assets/corvid")
    except:
        pass

    mapData = readMap(vmfString)

    # load &/ define the paks and folders where the assets will be grabbed from
    gamePath = SourceDir()
    for vpkFile in vpkFiles:
        print(f"Mounting {vpkFile}...")
        gamePath.add(vpkFile)
    for dir in gameDirs:
        print(f"Mounting {dir}...")
        gamePath.add(dir)

    # extract world materials and textures
    # can't skip exporting these becasue the textures (or the base textures of those materaials) are needed to get the UV of brush faces
    print("Loading materials...")
    materials = copyMaterials(mapData["materials"], gamePath)
    print("Loading texture data...")
    matData = copyTextures(materials, gamePath)
    matSizes = matData["sizes"]

    # extract models, model materials and textures
    if not skipModels:
        print("Extracting models...")
        copyModels(mapData["models"], gamePath)
        print("Loading model materials...")
        mdlMaterials = copyModelMaterials(mapData["models"], gamePath, mapData["modelTints"], BO3)
        mdlMatData = copyTextures(mdlMaterials, gamePath, True)

    # create GDT files
    gdtFile = Gdt()
    batFile = ""
    if not skipMats or not skipModels:
        print("Generating GDT file...")
    if not skipMats:
        worldMats = createMaterialGdt(matData["vmts"], BO3)
        gdtFile += worldMats
    if not BO3 and not skipMats:
        batFile += worldMats.toBat()
    if not skipModels:
        modelMats = createMaterialGdt(mdlMatData["vmts"], BO3)
        gdtFile += modelMats
    if not BO3 and not skipModels:
        batFile += modelMats.toBat()
    if not skipModels:
        models = createModelGdt(mapData["models"], BO3, mapData["modelTints"])
        gdtFile += models
    if not BO3 and not skipModels:
        batFile += models.toBat()
    # create GDT files for images for Bo3
    if BO3:
        if not skipMats:
            gdtFile += createImageGdt(matData)
        if not skipModels:
            gdtFile += createImageGdt(mdlMatData)

    # convert the textures
    if not skipMats:
        print("Converting textures...")
        convertImages(matData, "matTex", "texture_assets/corvid", "tif" if BO3 else "tga")
        if not skipModels:
            convertImages(mdlMatData, "mdlTex", "texture_assets/corvid", "tif" if BO3 else "tga")

    # convert the models
    if not skipModels:
        print("Converting models...")
        convertModels(mapData["models"], mapData["modelTints"], BO3)

    # generate map geometry
    print("Generating .map file...")
    mapGeo = ""
    mapEnts = ""
    worldSpawnSettings = {}

    # store brush sides in a dictionary for info_overlay entities
    sideDict: Dict[str, Side] = {}
    overlays = []

    # store rope entity info in a dictionary to convert them as curve patches if needed
    ropeDict: Dict[str, dict] = {
        "start": {},
        "end": {}
    }

    total = (
        len(mapData["worldBrushes"]) + len(mapData["entityBrushes"]) + len(mapData["entities"])
        + len(mapData["skyBrushes"]) + len(mapData["skyEntityBrushes"]) + len(mapData["skyEntities"])
    )
    i = 0

    # convert world geo & entities
    for brush in mapData["worldBrushes"]:
        print(f"{i}|{total}|done", end="")
        i += 1
        mapGeo += convertBrush(brush, True, BO3, mapName, matSizes=matSizes, brushConversion=brushConversion, sideDict=sideDict)

    for brush in mapData["entityBrushes"]:
        print(f"{i}|{total}|done", end="")
        i += 1
        mapGeo += convertBrush(brush, False, BO3, mapName, matSizes=matSizes, sideDict=sideDict)

    for entity in mapData["entities"]:
        print(f"{i}|{total}|done", end="")
        i += 1
        if entity["classname"].startswith("prop_"):
            mapEnts += convertProp(entity, BO3)
        elif entity["classname"] == "light":
            mapEnts += convertLight(entity)
        elif entity["classname"] == "light_spot":
            mapEnts += convertSpotLight(entity, BO3)
        elif entity["classname"] == "move_rope" or entity["classname"] == "keyframe_rope":
            if ropeCurve:
                convertRope(entity, curve=True, ropeDict=ropeDict)
            else:
                mapEnts += convertRope(entity)
        elif entity["classname"] == "env_cubemap":
            mapEnts += convertCubemap(entity)
        elif entity["classname"].startswith("info_player") or entity["classname"].endswith("_spawn"):
            mapEnts += convertSpawner(entity)
        elif entity["classname"] == "info_overlay":
            if entity["sides"] != "":
                overlays.append(entity)
        elif entity["classname"] == "light_environment":
            sundirection = Vector3.FromStr(entity["angles"])
            sundirection.x = float(entity["pitch"]) * -1
            worldSpawnSettings["sundirection"] = sundirection
            worldSpawnSettings["sunglight"] = "1",
            worldSpawnSettings["sundiffusecolor"] = "0.75 0.82 0.85",
            worldSpawnSettings["diffusefraction"] = ".2",
            worldSpawnSettings["ambient"] = ".116",
            worldSpawnSettings["reflection_ignore_portals"] = "1",
            if "ambient" in entity:
                worldSpawnSettings["_color"] = (Vector3.FromStr(entity["_ambient"] if "_ambient" in entity else entity["ambient"]) / 255).round(3),
            if "_light" in entity:
                worldSpawnSettings["suncolor"] = (Vector3.FromStr(entity["_light"]) / 255).round(3),
            

    # convert 3d skybox geo & entities
    for brush in mapData["skyBrushes"]:
        print(f"{i}|{total}|done", end="")
        i += 1
        mapGeo += convertBrush(brush, True, BO3, mapName, origin=mapData["skyBoxOrigin"], scale=mapData["skyBoxScale"], sideDict=sideDict)

    for brush in mapData["skyEntityBrushes"]:
        print(f"{i}|{total}|done", end="")
        i += 1
        mapGeo += convertBrush(brush, False, BO3, mapName, origin=mapData["skyBoxOrigin"], scale=mapData["skyBoxScale"], sideDict=sideDict)

    for entity in mapData["skyEntities"]:
        print(f"{i}|{total}|done", end="")
        i += 1
        if entity["classname"].startswith("prop_"):
            mapEnts += convertProp(entity, BO3, mapData["skyBoxOrigin"], mapData["skyBoxScale"])
        elif entity["classname"] == "move_rope" or entity["classname"] == "keyframe_rope":
            if ropeCurve:
                convertRope(entity, skyOrigin=mapData["skyBoxOrigin"], scale=mapData["skyBoxScale"], curve=True, ropeDict=ropeDict)
            else:
                mapEnts += convertRope(entity, skyOrigin=mapData["skyBoxOrigin"], scale=mapData["skyBoxScale"])
    
    # convert ropes to curve patches for cod 4
    if ropeCurve:
        for val in ropeDict["start"].values(): 
            mapGeo += convertRopeAsCurve(
                val["origin"],
                ropeDict["end"][val["target"]]["origin"],
                val["slack"],
                val["width"]
            )

    # convert overlays
    for overlay in overlays:
        decal = Overlay(overlay, sideDict, matSizes)
        if decal is not None:
            mapGeo += str(decal)
        del decal

    # convert the skybox textures
    if not skipMats and mapData["sky"] != "sky":
        skyData = exportSkybox(mapData["sky"], mapName, worldSpawnSettings, gamePath, BO3)
        gdtFile += skyData
        if not BO3:
            batFile += skyData.toBat()

    # write the gdt & bat files
    open(f"{copyDir}/converted/source_data/_{mapName}.gdt", "w").write(gdtFile.toStr())
    if not BO3:
        open(f"{copyDir}/converted/bin/_convert_{mapName}_assets.bat", "w").write(gdtFile.toBat())

    if BO3:
        res = (
                "iwmap 4\n"
                + '"script_startingnumber" 0\n'
                + '"000_Global" flags expanded  active\n'
                + '"000_Global/No Comp" flags hidden ignore \n'
                + '"The Map" flags expanded \n'
                + convertEntity({
                    "classname": "worldspawn",
                    "lightingquality": "1024",
                    "samplescale": "1",
                    "skyboxmodel": f"{mapName}_ssi",
                    "ssi": "default_day",
                    "wsi": "default_day",
                    "fsi": "default",
                    "gravity": "800",
                    "lodbias": "default",
                    "lutmaterial": "luts_t7_default",
                    "numOmniShadowSlices": "24",
                    "numSpotShadowSlices": "64",
                    "sky_intensity_factor0": "1",
                    "sky_intensity_factor1": "1",
                    "state_alias_1": "State 1",
                    "state_alias_2": "State 2",
                    "state_alias_3": "State 3",
                    "state_alias_4": "State 4"
                },
                id="",
                geo=mapGeo)
                + mapEnts
        )

    else:
        worldSpawnSettings["classname"] = "worldspawn"
        res = (
            "iwmap 4\n"
            + convertEntity(
                worldSpawnSettings,
                id="0",
                geo=mapGeo
            )
            + mapEnts
        )

    return res
