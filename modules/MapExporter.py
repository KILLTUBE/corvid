from modules.Brush import Brush
from modules.SourceDir import SourceDir
from .Side import Side
from .MapReader import readMap
from mathutils import Vector
from .Gdt import Gdt
from os.path import basename, splitext
from os import makedirs
from tempfile import gettempdir
from .AssetExporter import *
from .AssetConverter import convertImages, convertModels
from shutil import rmtree
from .Static import rgbToHex, Vector3FromStr, Vector2Str
from .CoDMap import *

sides = {}

def convertSide(side: Side, matSize: dict, origin=Vector((0, 0, 0)), scale=1):
    # skip invalid sides
    if len(side.points) < 3:
        print(f"Brush face {side.id} has less than 3 vertices. Skipping...")
        return ""

    sides[side.id] = side

    res = ""
    points = side.points
    
    # get uv points
    for point in side.points:
        side.uvs.append(side.getUV(point, matSize.get(basename(side.material), Vector((512, 512)))))
    uvs: list[Vector] = side.uvs

    if len(points) % 2 == 1:
        points.append(points[-1])
        uvs.append(uvs[-1])
    count = len(points)
    rows = int(count / 2)

    if side.material.lower().strip().startswith("liquids"):
        side.material = "clip_water"

    material = basename(side.material).lower().strip()
    material = material.replace("{", "_").replace("}", "_").replace("(", "_").replace(")", "_").replace(" ", "_")
    
    res += f"// Side {side.id}\n"
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
            "pos": (points[i] - origin) * scale,
            "uv": Vector((uvs[i].x * side.texSize.x, uvs[i].y * side.texSize.y)),
            "lm": uvs[i] * side.lightmapScale
        }
        p2 = {
            "pos": (points[count - i - 1] - origin) * scale,
            "uv": Vector((uvs[count - i - 1].x * side.texSize.x, uvs[count - i - 1].y * side.texSize.y)),
            "lm": uvs[count - i - 1] * side.lightmapScale
        }
        res += (
            "(\n" +
            f'v {Vector2Str(p1["pos"])} t {Vector2Str(p1["uv"])} {Vector2Str(p1["lm"])}\n' +
            f'v {Vector2Str(p2["pos"])} t {Vector2Str(p2["uv"])} {Vector2Str(p2["lm"])}\n' +
            ")\n"
        )

    res += (
        "}\n" +
        "}\n"
    )
    return res

def getDispPoints(p1: Vector, p2: Vector, uv1: Vector, uv2: Vector, power: int):
    res = []
    rowCount = int(2 ** power) + 1
    for i in range(rowCount):
        res.append({
            "pos": p1.lerp(p2, 1 / (rowCount - 1) * i),
            "uv": uv1.lerp(uv2, 1 / (rowCount - 1) * i)
        })
    return res

def convertDisplacement(side: Side, matSize: dict, origin=Vector((0, 0, 0)), scale=1):
    res = ""
    points = side.points
    # get uv points
    for point in side.points:
        side.uvs.append(side.getUV(point, matSize.get(basename(side.material), Vector((512, 512)))))
    
    if len(points) != 4:
        print(f"Displacement has {len(points)} points. Displacements can have 4 points only. Side id: {side.id}")
        for point in points:
            print(Vector2Str(point))
        return ""
    
    sides[side.id] = side

    uvs: list[Vector] = side.uvs
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

    material = basename(side.material).lower().strip()
    material = material.replace("{", "_").replace("}", "_").replace("(", "_").replace(")", "_").replace(" ", "_")

    res += f"// Side {side.id}\n"
    res += (
        "{\n" +
        "mesh\n" +
        "{\n" +
        "" + material + "\n" +
        "lightmap_gray\n"
        "" + str(len(rows[0])) + " " + str(len(rows[0])
                                              ) + " " + str(side.lightmapScale) + " 8\n"
    )

    for i in range(numVerts):
        row = rows[i]
        res += "(\n"
        for j in range(numVerts):
            if disp["row"][j]["alphas"][i] != 0 and alpha != True:
                alpha = True
            col = row[j]
            pos = (col["pos"] + Vector((0, 0, float(disp["elevation"]))) +
                   (disp["row"][j]["normals"][i] * disp["row"][j]["distances"][i]))
            uv = Vector(((col["uv"].x * side.texSize.x), (col["uv"].y * side.texSize.y)))
            lm = col["uv"] * (side.lightmapScale)
            pos = (pos - origin) * scale
            res += f"v {Vector2Str(pos)} t {Vector2Str(uv)} {Vector2Str(lm)}\n"
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
        "" + material + "_\n" +
        "lightmap_gray\n" +
        "" + str(len(rows[0])) + " " + str(len(rows[0])
                                              ) + " " + str(side.lightmapScale) + " 8\n"
    )

    for i in range(numVerts):
        row = rows[i]
        res += "(\n"
        for j in range(numVerts):
            col = row[j]
            pos = (col["pos"] + Vector((0, 0, float(disp["elevation"]))) +
                   (disp["row"][j]["normals"][i] * disp["row"][j]["distances"][i]))
            uv = Vector(((col["uv"].x * side.texSize.x), (col["uv"].y * side.texSize.y)))
            lm = col["uv"] * (side.lightmapScale)
            color = "255 255 255 0" if  disp["row"][j]["alphas"][i] == 0 else  "255 255 255 " + str(disp["row"][j]["alphas"][i])
            pos = (pos - origin) * scale
            res += f"v {Vector2Str(pos)} c {color} t {Vector2Str(uv)} {Vector2Str(lm)}\n"
        res += ")\n"
    res += ("}\n" +
            "}\n")

    return res

def convertBrush(brush: Brush, world=True, BO3=False, mapName="", origin=Vector((0, 0, 0)), scale=1, matSizes={}, brushConversion=False):
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

    resBrush = "{\n"
    if not world:
        resBrush += "contents detail;\n"
    resPatch = ""

    for side in brush.sides:        
        if side.hasDisp:
            resPatch += convertDisplacement(side, matSizes, origin, scale)
            continue;
        
        if brush.hasDisp and not side.hasDisp:
            continue
        
        p1 = (side.p1 - origin) * scale
        p2 = (side.p2 - origin) * scale
        p3 = (side.p3 - origin) * scale
        resBrush += f"( {Vector2Str(p1) } ) ( {Vector2Str(p2) } ) ( {Vector2Str(p3) } ) "

        if side.material.startswith("tools"):
            mat = basename(side.material)
            if mat in tools:
                resBrush += tools[mat] + " 128 128 0 0 0 0 lightmap_gray 16384 16384 0 0 0 0\n"
                continue
            else:
                resBrush += "clip 128 128 0 0 0 0 lightmap_gray 16384 16384 0 0 0 0\n"
                continue

        elif side.material.startswith("liquid"):
                resBrush += "caulk 128 128 0 0 0 0 lightmap_gray 16384 16384 0 0 0 0\n"
                continue
        
        elif not brushConversion:
            resBrush += "caulk 128 128 0 0 0 0 lightmap_gray 16384 16384 0 0 0 0\n"
            resPatch += convertSide(side, matSizes, origin, scale)
        
        else:
            mat = basename(side.material)
            side.texSize = matSizes.get(basename(mat), Vector((512, 512)))
            tex = side.texCoords()
            if tex:
                resBrush += f"{mat} {tex}\n"
            else:
                resBrush += "caulk 128 128 0 0 0 0 lightmap_gray 16384 16384 0 0 0 0\n"
                resPatch += convertSide(side, matSizes, origin, scale)
        
    
    resBrush += "}\n"
    
    if brush.hasDisp:
        return resPatch

    return resBrush + resPatch

def convertLight(entity):
    res = MapEntity(entity["id"])
    if "_light" in entity:
        _color = entity["_light"].split(" ")
        if len(_color) == 3:
            _color.append(500)
    else:
        _color = [0, 0, 0, 500]
    # In Radiant, color value of light entities range between 0 and 1 whereas it varies between 0 and 255 in Source engine
    color = (Vector((float(_color[0]), float(_color[1]), float(_color[2]))) / 255)

    res.classname = "light"
    res.origin = entity["origin"]
    res._color = f"{color.x} {color.y} {color.z}"
    res.radius = _color[3]
    res.intensity = 1

    return res

def convertSpotLight(entity, BO3=False):
    if "_light" in entity:
        _color = entity["_light"].split(" ")
        if len(_color) == 3:
            _color.append(500)
    else:
        _color = [0, 0, 0, 500]
    # In Radiant, color value of light entities range between 0 and 1 whereas it varies between 0 and 255 in Source engine
    color = (Vector((float(_color[0]), float(_color[1]), float(_color[2]))) / 255)
    _origin = entity["origin"].split(" ")
    origin = Vector((float(_origin[0]), float(_origin[1]), float(_origin[2])))
    if "_fifty_percent_distance" in entity and "_zero_percent_distance" not in entity:
        radius = float(entity["_fifty_percent_distance"])
    elif "_zero_percent_distance" in entity and "_fifty_percent_distance" not in entity:
        radius = float(entity["_zero_percent_distance"])
    elif "_fifty_percent_distance" in entity and "_zero_percent_distance" in entity:
        radius = (float(entity["_fifty_percent_distance"]) * 2 + float(entity["_zero_percent_distance"])) / 2
    else:
        radius = 250
    
    if not BO3:
        res = MapEntity(entity["id"])
        res.classname = "light"
        res.origin = entity["origin"]
        res._color = f"{color.x} {color.y} {color.z}"
        res.radius = radius
        res.intensity = "1"
        res.target = "spotlight_" + entity["id"]
        res.fov_outer = entity["_cone"]
        res.fov_inner = entity["_inner_cone"]

        res2 = MapEntity()
        res2.classname = "info_null"
        _origin = origin + Vector((0, 0, -float(_color[3])))
        res2.origin = f"{_origin.x} {_origin.y} {origin.z}"
        res2.targetname = "spotlight_" + entity["id"]

        return str(res) + str(res2)
    else:
        angles = Vector3FromStr(entity["angles"])
        pitch = float(entity["pitch"])
        angles = f"{pitch} {angles.y} {angles.z}"
        res = MapEntity(entity["id"])
        res.classname = "light"
        res.origin = entity["origin"]
        res._color = f"{color.x} {color.y} {color.z}"
        res.PRIMARY_TYPE = "PRIMARY_SPOT"
        res.angles = angles
        res.radius = radius
        res.fov_outer = entity["_cone"]
        res.fov_inner = entity["_inner_cone"]

        return res

def convertRope(entity, skyOrigin=Vector((0, 0, 0)), scale=1):
    if entity["classname"] == "move_rope":
        origin = (Vector3FromStr(entity["origin"]) - skyOrigin) * scale
        res = MapEntity(entity["id"])
        res.classname = "rope"
        res.origin = f"{origin.x} {origin.y} {origin.z}"
        res.target = entity["NextKey"] if "NextKey" in entity else entity["id"]
        res.length_scale = float(entity["Slack"]) / 128
        res.width = float(entity["Width"]) * 3

        if "targetname" in entity:
            origin = (Vector3FromStr(entity["origin"]) - skyOrigin) * scale
            res2 = MapEntity()
            res2.classname = "info_null"
            res2.origin = f"{origin.x} {origin.y} {origin.z}"
            res2.targetname = entity["targetname"] if "targetname" in entity else entity["id"]

            return str(res) + str(res2)
        else:
            return str(res)
    else:
        origin = (Vector3FromStr(entity["origin"]) - skyOrigin) * scale
        res = MapEntity(entity["id"])
        res.classname = "info_null"
        res.origin = f"{origin.x} {origin.y} {origin.z}"
        res.targetname = entity["targetname"]

        if "NextKey" in entity:
            res2 = MapEntity()
            res2.classname = "rope"
            res2.origin = f"{origin.x} {origin.y} {origin.z}"
            res2.target = entity["NextKey"]
            res2.length_scale = float(entity["Slack"]) / 125
            res2.width = entity["width"] if "width" in entity else "1"
            
            return str(res) + str(res2)
        else:
            return str(res)

def convertProp(entity, BO3=False, skyOrigin=Vector((0, 0, 0)), scale=1):
    origin = (Vector3FromStr(entity["origin"]) - skyOrigin) * scale
    modelScale = float(entity["uniformscale"] if "uniformscale" in entity else entity["modelscale"] if "modelscale" in entity else "1") * scale
    if "model" not in entity:
        res = MapEntity(entity["id"])
        res.classname = "info_null"
        res.original_classname = entity["classname"]
        res.origin = f"{origin.x} {origin.y} {origin.z}"
        return res

    modelName = "m_" + splitext(basename(entity["model"].lower()))[0]
    modelName = modelName.replace("{", "_").replace("}", "_").replace("(", "_").replace(")", "_").replace(" ", "_")

    if BO3 and "rendercolor" in entity:
        if entity["rendercolor"] != "255 255 255":
            modelName += "_" + rgbToHex(entity["rendercolor"])

    res = MapEntity(entity["id"])
    res.classname = "dyn_model" if entity["classname"].startswith("prop_physics") else "misc_model"
    res.model = modelName
    res.origin = f"{origin.x} {origin.y} {origin.z}"
    res.angles = entity["angles"]
    res.spawnflags = "16" if entity["classname"].startswith("prop_physics") else ""
    res.modelscale = modelScale
    return res

def convertCubemap(entity):
    res = MapEntity(entity["id"])
    res.classname = "reflection_probe"
    res.origin = entity["origin"]
    return res

def convertSpawner(entity):
    spawners = {
        "info_player_terrorist": "mp_tdm_spawn_axis_start",
        "info_armsrace_terrorist": "mp_tdm_spawn_axis_start",
        "info_player_counterterrorist": "mp_tdm_spawn_allies_start",
        "info_armsrace_counterterrorist": "mp_tdm_spawn_allies_start",
        "info_deathmatch_spawn": "mp_dm_spawn",
        "info_player_deathmatch": "mp_dm_spawn",
        "info_player_start": "info_player_start",
    }
    if entity["classname"] in spawners:
        classname = spawners[entity["classname"]]
    else:
        #print(f'Unknown spawner entity: {entity["classname"]}')
        return ""
    origin = Vector3FromStr(entity["origin"])
    origin.z += 32 # otherwise they go through the floor
    res = MapEntity(entity["id"])
    res.classname = classname
    res.origin = f"{origin.x} {origin.y} {origin.z}"
    res.angles = entity["angles"]

    if classname == "info_player_start":
        res2 = MapEntity()
        res2.classname = "mp_global_intermission"
        res2.origin = entity["origin"]
        return str(res) + str(res2)
    else:
        return res

def exportMap(vmfString, vpkFiles=[], gameDirs=[], BO3=False, skipMats=False, skipModels=False, mapName="", brushConversion=False):
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
    mapEnts = []
    worldSpawn = MapEntity()
    worldSpawn.classname = "worldspawn"
    worldSpawnSettings = {}

    total = (
        len(mapData["worldBrushes"]) + len(mapData["entityBrushes"]) + len(mapData["entities"])
        + len(mapData["skyBrushes"]) + len(mapData["skyEntityBrushes"]) + len(mapData["skyEntities"])
    )
    i = 0

    # convert world geo & entities
    for brush in mapData["worldBrushes"]:
        print(f"{i}|{total}|done", end="")
        i += 1
        worldSpawn.addGeo(convertBrush(brush, True, BO3, mapName, matSizes=matSizes, brushConversion=brushConversion))

    for brush in mapData["entityBrushes"]:
        print(f"{i}|{total}|done", end="")
        i += 1
        worldSpawn.addGeo(convertBrush(brush, False, BO3, mapName, matSizes=matSizes, brushConversion=brushConversion))

    for entity in mapData["entities"]:
        print(f"{i}|{total}|done", end="")
        i += 1
        if entity["classname"].startswith("prop_"):
            mapEnts.append(convertProp(entity, BO3))
        elif entity["classname"] == "light":
            mapEnts.append(convertLight(entity))
        elif entity["classname"] == "light_spot":
            mapEnts.append(convertSpotLight(entity, BO3))
        elif entity["classname"] == "move_rope" or entity["classname"] == "keyframe_rope":
            mapEnts.append(convertRope(entity))
        elif entity["classname"] == "env_cubemap":
            mapEnts.append(convertCubemap(entity))
        elif entity["classname"].startswith("info_player") or entity["classname"].endswith("_spawn"):
            mapEnts.append(convertSpawner(entity))
        elif entity["classname"] == "light_environment":
            sundirection = Vector3FromStr(entity["angles"])
            sundirection.x = float(entity["pitch"])
            worldSpawnSettings["sundirection"] = f"{sundirection.x} {sundirection.y} {sundirection.z}"
            worldSpawnSettings["sunglight"] = "1",
            worldSpawnSettings["sundiffusecolor"] = "0.75 0.82 0.85",
            worldSpawnSettings["diffusefraction"] = ".2",
            worldSpawnSettings["ambient"] = ".116",
            worldSpawnSettings["reflection_ignore_portals"] = "1",
            if "ambient" in entity:
                _ambient = (Vector3FromStr(entity["_ambient"] if "_ambient" in entity else entity["ambient"]) / 255)
                worldSpawnSettings["_color"] = f"{_ambient.x} {_ambient.y} {_ambient.z}",
            if "_light" in entity:
                _suncolor = (Vector3FromStr(entity["_light"]) / 255)
                worldSpawnSettings["suncolor"] = f"{_suncolor.x} {_suncolor.y} {_suncolor.z}",

    # convert 3d skybox geo & entities
    for brush in mapData["skyBrushes"]:
        print(f"{i}|{total}|done", end="")
        i += 1
        worldSpawn.addGeo(convertBrush(brush, True, BO3, mapName, mapData["skyBoxOrigin"], mapData["skyBoxScale"], matSizes, brushConversion=brushConversion))

    for brush in mapData["skyEntityBrushes"]:
        print(f"{i}|{total}|done", end="")
        i += 1
        worldSpawn.addGeo(convertBrush(brush, False, BO3, mapName, mapData["skyBoxOrigin"], mapData["skyBoxScale"], matSizes, brushConversion=brushConversion))

    for entity in mapData["skyEntities"]:
        print(f"{i}|{total}|done", end="")
        i += 1
        if entity["classname"].startswith("prop_"):
            mapEnts.append(convertProp(entity, BO3, mapData["skyBoxOrigin"], mapData["skyBoxScale"]))
        elif entity["classname"] == "move_rope" or entity["classname"] == "keyframe_rope":
            mapEnts.append(convertRope(entity, mapData["skyBoxOrigin"], mapData["skyBoxScale"]))
    
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

    res = "iwmap 4\n"

    if BO3:
        worldSpawn.lightingquality = "1024"
        worldSpawn.samplescale = "1"
        worldSpawn.skyboxmodel = f"{mapName}_ssi"
        worldSpawn.ssi = "default_day"
        worldSpawn.wsi = "default_day"
        worldSpawn.fsi = "default"
        worldSpawn.gravity = "800"
        worldSpawn.lodbias = "default"
        worldSpawn.lutmaterial = "luts_t7_default"
        worldSpawn.numOmniShadowSlices = "24"
        worldSpawn.numSpotShadowSlices = "64"
        worldSpawn.sky_intensity_factor0 = "1"
        worldSpawn.sky_intensity_factor1 = "1"
        worldSpawn.state_alias_1 = "State 1"
        worldSpawn.state_alias_2 = "State 2"
        worldSpawn.state_alias_3 = "State 3"
        worldSpawn.state_alias_4 = "State 4"
        res += (
                '"script_startingnumber" 0\n'
                + '"000_Global" flags expanded  active\n'
                + '"000_Global/No Comp" flags hidden ignore \n'
                + '"The Map" flags expanded \n'
        )
    else:
        try: # just skip if a map doesn't have GI settings
            _sundirection = Vector3FromStr(worldSpawnSettings["sundirection"])
            _sundirection.y -= 180
            worldSpawn.sundirection = f"{Vector2Str(_sundirection)}"
            worldSpawn.sunglight = worldSpawnSettings["sunglight"]
            worldSpawn.sundiffusecolor = worldSpawnSettings["sundiffusecolor"]
            worldSpawn.diffusefraction = worldSpawnSettings["diffusefraction"]
            worldSpawn.ambient = worldSpawnSettings["ambient"]
            worldSpawn.reflection_ignore_portals = worldSpawnSettings["reflection_ignore_portals"]
            if "_color" in worldSpawnSettings:
                worldSpawn._color = worldSpawnSettings["_color"]
            if "suncolor" in worldSpawnSettings:
                worldSpawn.suncolor = worldSpawnSettings["suncolor"]
        except:
            pass

    res += str(worldSpawn)

    for ent in mapEnts:
        res += str(ent)

    return res
