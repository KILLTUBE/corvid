from modules.SourceDir import SourceDir
from .Side import Side
from .MapReader import readMap
from .Vector2 import Vector2
from .Vector3 import Vector3, Vector3FromStr
from .Gdt import Gdt
from os.path import basename, splitext
from os import makedirs
from tempfile import gettempdir
from .AssetExporter import *
from .AssetConverter import convertImages, convertModels
from shutil import rmtree
from .Static import deg2rad, rad2deg, rgbToHex
from .CoDMap import *

sides = {}

def convertSide(side: Side, matSize, origin=Vector3(0, 0, 0), scale=1):
    # skip invalid sides
    if len(side.points) < 3:
        print(f"Brush face {side.id} has less than 3 vertices. Skipping...")
        return ""

    res = ""
    points = side.points

    # get uv points
    for point in side.points:
        side.uvs.append(side.getUV(point, matSize[basename(side.material).strip()]))
    uvs: list[Vector2] = side.uvs

    if len(points) % 2 == 1:
        points.append(points[-1])
        uvs.append(uvs[-1])
    count = len(points)
    rows = int(count / 2)

    if side.material.lower().strip().startswith("liquids"):
        side.material = "clip_water"

    material = basename(side.material).lower().strip()
    material = material.replace("{", "_").replace("}", "_").replace("(", "_").replace(")", "_").replace(" ", "_")

    res = MapMesh(texture=material, lmapTexture="lightmap_gray", lmapSize=side.lightmapScale, rowCount=rows, columnCount=2)

    for i in range(rows):
        res.addVert(i, 0, MapVert(pos=(points[i] - origin) * scale, uv=uvs[i], lmapUv=uvs[i] * side.lightmapScale))
        res.addVert(i, 1, MapVert(pos=(points[count - i - 1] - origin) * scale, uv=uvs[count - i - 1], lmapUv=uvs[count - i - 1] * side.lightmapScale))
    
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
    res = ""
    points = side.points
    # get uv points
    for point in side.points:
        side.uvs.append(side.getUV(point, matSize[basename(side.material).strip()]))

    if len(points) != 4:
        print(f"Displacement has {len(points)}. Displacements can have 4 points only. Side id: {side.id}\n")
        for point in points:
            print(point)
        return ""
    
    sides[side.id] = side

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

    material = basename(side.material).lower().strip()
    material = material.replace("{", "_").replace("}", "_").replace("(", "_").replace(")", "_").replace(" ", "_")

    res = MapMesh(material, "lightmap_gray", side.lightmapScale, len(rows[0]), len(rows[0]))

    for i in range(numVerts):
        row = rows[i]
        for j in range(numVerts):
            if disp["row"][j]["alphas"][i] != 0 and alpha != True:
                alpha = True
            col = row[j]
            pos = (col["pos"] + Vector3(0, 0, disp["elevation"]) +
                   (disp["row"][j]["normals"][i] * disp["row"][j]["distances"][i]))
            uv = (col["uv"] * side.texSize) * 1
            lm = col["uv"] * (side.lightmapScale)
            res.addVert(i, j, MapVert((pos - origin) * scale, uv, lm))
    
    if not alpha:
        return str(res)
    if material + "_" not in matSize:
        return str(res)
    
    res2 = MapMesh(material + "_", "lightmap_gray", side.lightmapScale, len(rows[0]), len(rows[0]))
    for i in range(numVerts):
        row = rows[i]
        for j in range(numVerts):
            if disp["row"][j]["alphas"][i] != 0 and alpha != True:
                alpha = True
            col = row[j]
            pos = (col["pos"] + Vector3(0, 0, disp["elevation"]) +
                   (disp["row"][j]["normals"][i] * disp["row"][j]["distances"][i]))
            uv = (col["uv"] * side.texSize) * 1
            lm = col["uv"] * (side.lightmapScale)
            if disp["row"][j]["alphas"][i] == 0:
                res2.addVert(i, j, MapVert((pos - origin) * scale, uv, lm, "255 255 255 0"))
            else:
                res2.addVert(i, j, MapVert((pos - origin) * scale, uv, lm, "255 255 255 " + str(disp["row"][j]["alphas"][i])))
    
    return str(res) + str(res2)

def convertBrush(brush, world=True, BO3=False, mapName="", origin=Vector3(0, 0, 0), scale=1):
    # BO3 doesn't need hint/skip brushes or portals for optimization
    if BO3:
        if brush.entity == "func_areaportal" or brush.entity == "func_areaportalwindow":
            return ""
        if brush.sides[0].material == "tools/toolshint" or brush.sides[0].material == "tools/toolsskip":
            return ""

    classnames = ["func_detail", "func_brush", "func_illusionary", "func_breakable", "func_breakable_surf", "func_door", "func_door_rotating",
                  "func_ladder", "func_door", "func_movelinear", "func_lod", "func_lookdoor", "func_physbox", "func_physbox_multiplayer",
                  "func_rotating", "func_tank", "func_tankairboatgun", "func_tankapcrocket", "func_tanklaser", "func_tankmortar",
                  "func_tankphyscannister", "func_tankpulselaser", "func_tankrocket", "func_tanktrain", "func_trackautochange", "func_trackchange",
                  "func_tracktrain", "func_traincontrols", "func_wall", "func_wall_toggle", "func_water_analog"]
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

    res = MapBrush()
    if not world:
        res.contents = "detail"
    else:
        pass  # do nothing. structural brushes and portals don't need to be specified like detail brushes

    material = ""

    for side in brush.sides:
        if side.material.startswith("tools"):
            mat = basename(side.material)
            if mat not in tools:
                return ""
            else:
                material = tools[mat]
        else:
            material = "caulk"
        res.sides.append(MapSide((side.p1 - origin) * scale, (side.p2 - origin) * scale, (side.p3 - origin) * scale, material))

    return res

def convertLight(entity):
    res = MapEntity(entity["id"])
    if "_light" in entity:
        _color = entity["_light"].split(" ")
        if len(_color) == 3:
            _color.append(500)
    else:
        _color = [0, 0, 0, 500]
    # In Radiant, color value of light entities range between 0 and 1 whereas it varies between 0 and 255 in Source engine
    color = (Vector3(_color[0], _color[1], _color[2]) / 255).round(3)

    res.classname = "light"
    res.origin = entity["origin"]
    res._color = color
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
        res = MapEntity(entity["id"])
        res.classname = "light"
        res.origin = entity["origin"]
        res._color = color
        res.radius = radius
        res.intensity = "1"
        res.target = "spotlight_" + entity["id"]
        res.fov_outer = entity["_cone"]
        res.fov_inner = entity["_inner_cone"]

        res2 = MapEntity()
        res2.classname = "info_null"
        res2.origin = origin + Vector3(0, 0, -float(_color[3]))
        res2.targetname = "spotlight_" + entity["id"]

        return str(res) + str(res2)
    else:
        angles = Vector3FromStr(entity["angles"])
        pitch = float(entity["pitch"])
        rot = Vector3(deg2rad(-90), 0, 0)
        new = rot.rotate(Vector3(
            deg2rad(angles.z),
            deg2rad(-pitch),
            deg2rad(angles.y)
        ))
        newAngles = Vector3(
            rad2deg(new.y),
            rad2deg(new.z),
            rad2deg(new.x)
        )
        res = MapEntity(entity["id"])
        res.classname = "light"
        res.origin = entity["origin"]
        res._color = color
        res.PRIMARY_TYPE = "PRIMARY_SPOT"
        res.angles = newAngles
        res.radius = radius
        res.fov_outer = entity["_cone"]
        res.fov_inner = entity["_inner_cone"]

        return res

def convertRope(entity, skyOrigin=Vector3(0, 0, 0), scale=1):
    if entity["classname"] == "move_rope":
        origin = (Vector3FromStr(entity["origin"]) - skyOrigin) * scale
        res = MapEntity(entity["id"])
        res.classname = "rope"
        res.origin = origin
        res.target = entity["NextKey"] if "NextKey" in entity else entity["id"]
        res.length_scale = float(entity["Slack"]) / 128
        res.width = float(entity["Width"]) * 3

        if "targetname" in entity:
            origin = (Vector3FromStr(entity["origin"]) - skyOrigin) * scale
            res2 = MapEntity()
            res2.classname = "info_null",
            res2.origin = origin,
            res2.targetname = entity["targetname"] if "targetname" in entity else entity["id"]

            return str(res) + str(res2)
        else:
            return str(res)
    else:
        origin = (Vector3FromStr(entity["origin"]) - skyOrigin) * scale
        res = MapEntity(entity["id"])
        res.classname = "info_null"
        res.origin = origin
        res.targetname = entity["targetname"]

        if "NextKey" in entity:
            res2 = MapEntity()
            res2.classname = "rope"
            res2.origin = origin
            res2.target = entity["NextKey"]
            res2.length_scale = float(entity["Slack"]) / 125
            res2.width = entity["width"] if "width" in entity else "1"
            
            return str(res) + str(res2)
        else:
            return str(res)

def convertProp(entity, BO3=False, skyOrigin=Vector3(0, 0, 0), scale=1):
    origin = (Vector3FromStr(entity["origin"]) - skyOrigin) * scale
    modelScale = float(entity["uniformscale"] if "uniformscale" in entity else entity["modelscale"] if "modelscale" in entity else "1") * scale
    if "model" not in entity:
        res = MapEntity(entity["id"])
        res.classname = "info_null"
        res.original_classname = entity["classname"]
        res.origin = origin
        return res

    modelName = "m_" + splitext(basename(entity["model"].lower()))[0]
    modelName = modelName.replace("{", "_").replace("}", "_").replace("(", "_").replace(")", "_").replace(" ", "_")

    if BO3 and "rendercolor" in entity:
        if entity["rendercolor"] != "255 255 255":
            modelName += "_" + rgbToHex(entity["rendercolor"])

    res = MapEntity(entity["id"])
    res.classname = "dyn_model" if entity["classname"].startswith("prop_physics") else "misc_model"
    res.model = modelName
    res.origin = origin
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
    res.origin = origin
    res.angles = entity["angles"]

    if classname == "info_player_start":
        res2 = MapEntity()
        res2.classname = "mp_global_intermission"
        res2.origin = entity["origin"]
        return str(res) + str(res2)
    else:
        return res

def exportMap(vmfString, vpkFiles=[], gameDirs=[], BO3=False, skipMats=False, skipModels=False, mapName=""):
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
        if not brush.hasDisp:
            worldSpawn.addGeo(convertBrush(brush, True, BO3, mapName))
        for side in brush.sides:
            if side.material.startswith("tools") or side.material.startswith("liquids"):
                continue
            if side.hasDisp:
                worldSpawn.addGeo(convertDisplacement(side, matSizes))
            if brush.hasDisp:
                continue
            worldSpawn.addGeo(convertSide(side, matSizes))

    for brush in mapData["entityBrushes"]:
        print(f"{i}|{total}|done", end="")
        i += 1
        if not brush.hasDisp:
            worldSpawn.addGeo(convertBrush(brush, False, BO3, mapName))
        for side in brush.sides:
            if side.material.startswith("tools") or side.material.startswith("liquids"):
                continue
            if side.hasDisp:
                worldSpawn.addGeo(convertDisplacement(side, matSizes))
            if brush.hasDisp:
                continue
            worldSpawn.addGeo(convertSide(side, matSizes))

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
            sundirection.x = float(entity["pitch"]) * -1
            worldSpawnSettings["sundirection"] = sundirection
            worldSpawnSettings["sunglight"] = "1",
            worldSpawnSettings["sundiffusecolor"] = "0.75 0.82 0.85",
            worldSpawnSettings["diffusefraction"] = ".2",
            worldSpawnSettings["ambient"] = ".116",
            worldSpawnSettings["reflection_ignore_portals"] = "1",
            if "ambient" in entity:
                worldSpawnSettings["_color"] = (Vector3FromStr(entity["_ambient"] if "_ambient" in entity else entity["ambient"]) / 255).round(3).__str__(),
            if "_light" in entity:
                worldSpawnSettings["suncolor"] = (Vector3FromStr(entity["_light"]) / 255).round(3).__str__(),

    # convert 3d skybox geo & entities
    for brush in mapData["skyBrushes"]:
        print(f"{i}|{total}|done", end="")
        i += 1
        if not brush.hasDisp:
            worldSpawn.addGeo(convertBrush(brush, True, BO3, mapName, mapData["skyBoxOrigin"], mapData["skyBoxScale"]))
        for side in brush.sides:
            if side.material.startswith("tools") or side.material.startswith("liquids"):
                continue
            if side.hasDisp:
                worldSpawn.addGeo(convertDisplacement(side, matSizes, mapData["skyBoxOrigin"], mapData["skyBoxScale"]))
            if brush.hasDisp:
                continue
            worldSpawn.addGeo(convertSide(side, matSizes, mapData["skyBoxOrigin"], mapData["skyBoxScale"]))

    for brush in mapData["skyEntityBrushes"]:
        print(f"{i}|{total}|done", end="")
        i += 1
        if not brush.hasDisp:
            worldSpawn.addGeo(convertBrush(brush, False, BO3, mapName, mapData["skyBoxOrigin"], mapData["skyBoxScale"]))
        for side in brush.sides:
            if side.material.startswith("tools") or side.material.startswith("liquids"):
                continue
            if side.hasDisp:
                worldSpawn.addGeo(convertDisplacement(side, matSizes, mapData["skyBoxOrigin"], mapData["skyBoxScale"]))
            if brush.hasDisp:
                continue
            worldSpawn.addGeo(convertSide(side, matSizes, mapData["skyBoxOrigin"], mapData["skyBoxScale"]))

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

    res = "iwmap4\n"

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
        worldSpawn.sundirection = worldSpawnSettings["sundirection"]
        worldSpawn.sunglight = worldSpawnSettings["sunglight"]
        worldSpawn.sundiffusecolor = worldSpawnSettings["sundiffusecolor"]
        worldSpawn.diffusefraction = worldSpawnSettings["diffusefraction"]
        worldSpawn.ambient = worldSpawnSettings["ambient"]
        worldSpawn.reflection_ignore_portals = worldSpawnSettings["reflection_ignore_portals"]
        if "_color" in worldSpawnSettings:
            worldSpawn._color = worldSpawnSettings["_color"]
        if "suncolor" in worldSpawnSettings:
            worldSpawn.suncolor = worldSpawnSettings["suncolor"]

    res += str(worldSpawn)

    for ent in mapEnts:
        res += str(ent)

    return res
