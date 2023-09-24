from copy import deepcopy
from math import cos, fabs, sin, degrees
from os import makedirs
from os.path import splitext
from posixpath import basename
from typing import Dict, List, Union
from mathutils import Vector
from Formats.BaseMap.Face import CoDUV
from Formats.Source.Map import Map as SourceMap, Solid, Side, Entity as SourceEntity
from .MaterialExporter import CreateMaterialGdt, ConvertTextures
from .ModelExporter import ConvertModels, CreateModelGdt
from Formats.CoD.Map import Map as CoDMap, Entity, Brush, Face, PatchVert, Patch
from Helpers.FileHelpers import NewPath, WriteFile
from Helpers.MathHelpers import Vec2Hex, Vec2Str, VecFromStr, VecUp, VecForward, VecRight, VecZero

def CalculateLightmapUV(side: Side, vertex: Vector) -> Vector:
        uv = VecZero(2)
        texSize = Vector((1024.0, 1024.0))
        n = side.GetNormal()

        du = fabs(n.dot(VecUp()))
        dr = fabs(n.dot(VecRight()))
        df = fabs(n.dot(VecForward()))

        if du >= dr and du >= df:
            uv = Vector((vertex.x, -vertex.y))
        elif dr >= du and dr >= df:
            uv = Vector((vertex.x, -vertex.z))
        elif df >= du and df >= dr:
            uv = Vector((vertex.y, -vertex.z))
        
        # we're gonna assume the rotation is 0
        rotated = VecZero(2)
        rotated.x = uv.x * cos(0) - uv.y * sin(0)
        rotated.y = uv.x * sin(0) + uv.y * cos(0)
        uv = rotated

        uv.x /= texSize.x
        uv.y /= texSize.y
        uv.x /= side.lightmapScale
        uv.y /= side.lightmapScale

        return uv * 1024

def ConvertSide(side: Side, options: dict) -> Patch | None:
    sideVerts, uvs = side.GetVerts(), side.GetUVs()

    if len(sideVerts) < 3:
        print(f"Brush face \"{side.id}\" has less than 3 vertices. Skipping...")
        return None

    if len(sideVerts) % 2 == 1:
        sideVerts.append(sideVerts[-1])
        uvs.append(uvs[-1])
    
    numVerts = len(sideVerts)
    rows = int(numVerts / 2)

    verts: List[List[PatchVert]] = []

    for i in range(rows):
        verts.append([
            PatchVert(sideVerts[i], uvs[i] * 1024, CalculateLightmapUV(side, sideVerts[i])),
            PatchVert(sideVerts[numVerts - i - 1], uvs[numVerts - i - 1] * 1024, CalculateLightmapUV(side, sideVerts[numVerts - i - 1])),
        ])
    
    return Patch("mesh", material=NewPath(side.material), size=(rows, 2), verts=verts)

def ConvertSolid(solid: Solid, options: dict, contents=None) -> Union[List[Union[Brush, Patch]], None]:
    res: List[Union[Brush, Patch]] = []

    toolTextures = {
        "toolsnodraw": "caulk", "toolsclip": "clip", "toolsplayerclip": "clip", "toolsinvisible": "clip",
        "toolsnpcclip": "clip","toolsgrenadeclip": "clip_missile",
        "toolsinvisibleladder": "ladder", "toolsareaportal": "portal_nodraw",
        "toolsblocklight": "shadowcaster", "toolshint": "hint", "toolsskip": "skip", "toolstrigger": "trigger",
    }

    faces = []

    for face in solid.faces:
        # The way skybox brushes are made in Source is not optimal for CoD, so we will skip the sky brushes
        if face.material == "tools/toolsskybox" and solid.isToolBrush:
            return None

        uvData = CoDUV()

        if options["ConvertBrushesAsPatches"]:
            material = toolTextures.get(basename(face.material), "caulk")
            uvData.xOffset = uvData.yOffset = 0
            uvData.xScale = uvData.yScale = 128
            uvData.rotation = 0
            uvData.lxScale = uvData.lyScale = 16384
        else:
            material = toolTextures.get(basename(face.material), NewPath(face.material))
            uvData.xOffset, uvData.yOffset = face.uvData.uOffset, face.uvData.vOffset
            uvData.xScale, uvData.yScale = face.uvData.uScale * 512, face.uvData.vScale * 512
            rot = degrees(face.uvData.uAxis.angle(face.uvData.vAxis))
            uvData.rotation = rot if rot != 90 else 0
            uvData.lxScale = uvData.lyScale = face.lightmapScale * 1024

        faces.append(Face(
            (face.p1, face.p2, face.p3), material, uvData, None
        ))

    brush = Brush(faces)

    if contents is not None:
        brush.contents.append(contents)

    if options["ConvertBrushesAsPatches"]:
        solid.CalculateUVs()

        for face in solid.faces:
            if not face.material.startswith("tools/"):
                if len(face.GetVerts()) < 3:
                    print(f"Brush face {face.id} has less than 3 vertices. Skipping...")
                    continue

                res.append(ConvertSide(face, options))

    res.append(brush)
    return res

def ConvertDisplacements(solid: Solid, options: dict) -> List[Patch]:
    res = []
    solid.CalculateUVs()

    for side in solid.faces:
        if side.dispInfo is None:
            continue

        alpha = False
        size = (side.dispInfo.numRows, side.dispInfo.numRows)
        elevation = Vector((0, 0, side.dispInfo.elevation))
        rows = side.GetDispVerts()
        verts: List[List[PatchVert]] = []

        for i, row in enumerate(rows):
            verts.append([])

            for col in row:
                pos, uv, normal, distance, _alpha = col
                verts[i].append(PatchVert(pos + elevation + normal * distance, uv * 1024, CalculateLightmapUV(side, pos)))

                if _alpha != 0:
                    alpha = True

        patch = Patch("mesh", material=NewPath(side.material), size=size, sampleSize=side.lightmapScale, verts=verts)
        res.append(patch)

        if alpha:
            blend = deepcopy(patch)
            blend.material += "_blend"
            for i in range(side.dispInfo.numRows):
                for k in range(side.dispInfo.numRows):
                    blend.verts[i][k].color = (255, 255, 255, rows[i][k][4])
            
            res.append(blend)

    return res

def ConvertBombSite(entity: SourceEntity, options: dict) -> List[Entity]:
    res: List[Entity] = []
    bombsites = ["a", "b", "c", "d", "e", "f", "g"]

    # use the same uv data for all brush faces
    uvData = CoDUV()
    uvData.xOffset = uvData.yOffset = uvData.rotation = 0
    uvData.xScale = uvData.yScale = 128
    uvData.lxScale = uvData.lyScale = 16384

    # generate brushes from the entity and add it to all SD-related entities
    triggerBrushes: List[Brush] = []

    center = VecZero()

    for solid in entity.geo:
        # we need to calculate the vertices of each brush in order to calculate their centers 
        solid.CalculateVerts()

        for vert in solid.verts:
            center += vert
        
        center /= len(solid.verts)
        
        faces: List[Face] = []

        for side in solid.faces:
            faces.append(Face((side.p1, side.p2, side.p3), "trigger", uvData, None))

        triggerBrushes.append(Brush(faces))
    
    bombsite = "_"

    if "targetname" in entity:
        bombsite += entity["targetname"].lower()
    else:
        bombsite += bombsites[options["Bombsite"]]
        options["Bombsite"] += 1
    
    # create trigger entities
    res.append(Entity({
        "classname": "trigger_use_touch",
        "script_bombmode_original": "1",
        "target": "target" + bombsite,
        "script_gameobjectname": "bombzone",
        "targetname": "bombzone",
        "script_label": bombsite
    }))

    res[-1].geo.extend(triggerBrushes)

    res.append(Entity({
        "classname": "trigger_use_touch",
        "targetname": "targetname" + bombsite,
        "script_gameobjectname": "bombzone"
    }))

    res[-1].geo.extend(triggerBrushes)

    # add an invisible model
    res.append(Entity({
        "classname": "script_model",
        "target": "targetname" + bombsite,
        "targetname": "target" + bombsite,
        "spawnflags": "4",
        "script_gameobjectname": "bombzone",
        "script_exploder": "1",
        "origin": Vec2Str(center),
        "model": "xmodel/tag_origin" if options["TargetGame"] == "CoD2" else "tag_origin",
    }))

    res.append(Entity({
        "classname": "script_model",
        "model": "xmodel/tag_origin" if options["TargetGame"] == "CoD2" else "tag_origin",
        "origin": Vec2Str(center),
        "spawnflags": "4",
        "targetname": "exploder",
        "script_exploder": "1"
    }))

    return res

def ConvertRopeAsEntity(entity: SourceEntity) -> List[Entity]:
    res: List[Entity] = []

    try:
        if entity["classname"] == "move_rope":
            origin = entity.GetVector("origin")
            res.append(Entity({
                "classname": "rope",
                "origin": origin,
                "target": entity["NextKey"] if "NextKey" in entity else entity["id"],
                "length_scale": entity.GetFloat("Slack") / 128,
                "width": entity.GetFloat("Width") * 3
            }))
            if "targetname" in entity:
                origin = entity.GetVector("origin")
                res.append(Entity({
                    "classname": "info_null",
                    "origin": origin,
                    "targetname": entity["targetname"] if "targetname" in entity else entity["id"]
                }))
        else:
            origin = entity.GetVector("origin")
            res.append(Entity({
                "classname": "info_null",
                "origin": origin,
                "targetname": entity["targetname"]
            }))
            if "NextKey" in entity:
                res.append(Entity({
                    "classname": "rope",
                    "origin": origin,
                    "target": entity["NextKey"],
                    "length_scale": entity.GetFloat("Slack") / 125,
                    "width": entity["width"] if "width" in entity else "1"
                }))
    except:
        pass

    return res

def ConvertRopeAsCurve(start: Vector, end: Vector, slack: float, width: float, options: dict) -> Patch:
    # calculate the direction and the forward vectors from start and end points
    dif = (end - start)

    if dif.Length() == 0:
        forward = VecZero()
    else:
        forward = dif.normalized()
    
    up = VecUp()
    right = forward.cross(up)
    left = right * -1

    # calculate the midpoint and where it will slack towards
    mid = (start + end) / 2
    mid.z -= slack * 0.75

    # calculate the thickness using the width
    width *= 0.5
    left *= width
    right *= width

    top = up * width
    bottom = top * -1
    topLeft = (top + left) / 2 + top
    bottomLeft = (bottom + left) / 2 - top
    topRight = (top + right) / 2 + top
    bottomRight = (bottom + right) / 2 - top

    material = {"WaW": "global_black", "CoD4": "credits_black", "CoD2": "egypt_metal_pipe2"}.get(options["TargetGame"])

    verts: List[List[PatchVert]] = [
        [
            PatchVert(start + bottom, Vector((0, 0)), Vector((1, 1))),
            PatchVert(mid + bottom, Vector((0, -84316)), Vector((1, 45))),
            PatchVert(end + bottom, Vector((0, -167833)), Vector((1, 89)))
        ],
        [
            PatchVert(start + bottomLeft, Vector((87, 0)), Vector((3, 1))),
            PatchVert(mid + bottomLeft, Vector((87, -84316)), Vector((3, 45))),
            PatchVert(end + bottomLeft, Vector((87, -167833)), Vector((3, 89)))
        ],
        [
            PatchVert(start + left, Vector((276, 0)), Vector((5, 1))),
            PatchVert(mid + left, Vector((276, -84316)), Vector((5, 45))),
            PatchVert(end + left, Vector((276, -167833)), Vector((5, 89)))
        ],
        [
            PatchVert(start + topLeft, Vector((465, 0)), Vector((7, 1))),
            PatchVert(mid + topLeft, Vector((465, -84316)), Vector((7, 45))),
            PatchVert(end + topLeft, Vector((465, -167833)), Vector((7, 89)))
        ],
        [
            PatchVert(start + top, Vector((552, 0)), Vector((9, 1))),
            PatchVert(mid + top, Vector((552, -84316)), Vector((9, 45))),
            PatchVert(end + top, Vector((552, -167833)), Vector((9, 89)))
        ],
        [
            PatchVert(start + topRight, Vector((639, 0)), Vector((9, 1))),
            PatchVert(mid + topRight, Vector((639, -84316)), Vector((9, 45))),
            PatchVert(end + topRight, Vector((639, -167833)), Vector((9, 89)))
        ],
        [
            PatchVert(start + right, Vector((828, 0)), Vector((11, 1))),
            PatchVert(mid + right, Vector((828, -84316)), Vector((11, 45))),
            PatchVert(end + right, Vector((828, -167833)), Vector((11, 89)))
        ],
        [
            PatchVert(start + bottomRight, Vector((1017, 0)), Vector((13, 1))),
            PatchVert(mid + bottomRight, Vector((1017, -84316)), Vector((13, 45))),
            PatchVert(end + bottomRight, Vector((1017, -167833)), Vector((13, 89)))
        ],
        [
            PatchVert(start + bottom, Vector((1104, 0)), Vector((15, 1))),
            PatchVert(mid + bottom, Vector((1104, -84316)), Vector((15, 45))),
            PatchVert(end + bottom, Vector((1104, -167833)), Vector((15, 89)))
        ],
    ]

    return Patch("curve", contents=["nonColliding"], material=material, size=(9, 3), verts=verts)

def ConvertProp(entity: SourceEntity, options: dict) -> Entity:
    model = "m_" + splitext(NewPath(entity["model"]))[0]

    if "skin" in entity and entity["skin"] != "0":
        model += "_skin" + entity["skin"]

    if options["TargetGame"] == "BO3" and entity["rendercolor"] != "255 255 255":
        model += "_" + Vec2Hex(entity.GetVector("rendercolor"))
    
    if options["TargetGame"] == "CoD2":
        model = f"xmodel/{model}"
        classname = "misc_model"
    else:
        if entity["classname"].startswith("prop_phys"):
            classname = "dyn_model"
        else:
            classname = "misc_model"

    if "uniformscale" in entity:
        scale = entity["uniformscale"]
    elif "modelscale" in entity:
        scale = entity["modelscale"]
    else:
        scale = 1

    return Entity({
        "classname": classname,
        "origin": entity["origin"],
        "angles": entity["angles"] if "angles" in entity else "",
        "model": model,
        "spawnflags": "16" if classname == "dyn_model" else "",
        "modelscale": scale
    })

def ConvertLight(entity: SourceEntity, options: dict) -> Entity:
    _color = [255, 255, 255, 500] # in case the entity does not have any color information

    if "_light" in entity:
        _color = entity.GetVector("_light", 4)
        if _color.z == 0 and _color.w == 0:
            _color = Vector((255, 255, 255, 500))

        if color.w == 0:
            color.w = 500
        
        # In CoD, RGB values range between 0 and 1 whereas they range between 0 and 255 in Source
        color = _color.xyz / 255

        return Entity({
            "classname": "light",
            "origin": entity["origin"],
            "_color": Vec2Str(color),
            "radius": max(_color[3], 250), # in case the radius value is too low
            "intensity": 1
        })

def ConvertSpawner(entity: SourceEntity, options: dict) -> Union[List[Entity], None]:
    classnames = {
        "info_player_terrorist": "mp_tdm_spawn_axis_start",
        "info_player_counterterrorist": "mp_tdm_spawn_allies_start",
        "info_deathmatch_spawn": "mp_dm_spawn",
        "info_player_deathmatch": "mp_dm_spawn",
        "info_player_start": "info_player_start",
        "info_player_allies": "mp_tdm_spawn_allies_start",
        "info_player_axis": "mp_tdm_spawn_axis_start"
    }

    if entity["classname"] in classnames:
        classname = classnames[entity["classname"]]
    else:
        return None

    res: List[Entity] = []
    origin = entity.GetVector("origin")
    origin.z += 32

    res.append(Entity({
        "classname": classname,
        "origin": origin,
        "angles": entity["angles"]
    }))

    if classname == "info_player_start":
        res.append(Entity({
            "classname": "mp_global_intermission",
            "origin": origin
        }))
    
        res.append(Entity({
            "classname": "mp_tdm_spawn",
            "origin": origin
        }))

    # make sure to add spawners for sd too
    if classname == "mp_tdm_spawn_axis_start" or classname == "mp_tdm_spawn_allies_start":
        res.append(Entity({
            "classname": "mp_sd_spawn_attacker" if classname == "mp_tdm_spawn_axis_start" else "mp_sd_spawn_defender",
            "origin": origin,
            "angles": entity["angles"]
        }))
    
    return res

def UpdateAABB(verts: List[Vector], _min: Vector, _max: Vector):
    for vert in verts:
        _min.x = min(_min.x, vert.x)
        _min.y = min(_min.y, vert.y)
        _min.z = min(_min.z, vert.z)
        _max.x = max(_max.x, vert.x)
        _max.y = max(_max.y, vert.y)
        _max.z = max(_max.z, vert.z)

def CreateVolume(Min: Vector, Max: Vector, material: str, hollow: bool=False, caulked: bool=True) -> List['Brush']:
    top1 = Max # top corners
    top2 = Vector((Max.x, Min.y, Max.z))
    top3 = Vector((Min.x, Max.y, Max.z))
    top4 = Vector((Min.x, Min.y, Max.z))
    bot1 = Min # bottom corners
    bot2 = Vector((Min.x, Max.y, Min.z))
    bot3 = Vector((Max.x, Min.y, Min.z))
    bot4 = Vector((Max.x, Max.y, Min.z))

    uvData = CoDUV()
    uvData.xOffset, uvData.yOffset, uvData.xScale, uvData.yScale, uvData.rotation = 0, 0, 128, 128, 0
    uvData.lxScale, uvData.lyScale = 16384, 16384

    res: List[Brush] = []

    if hollow:
        up, right, forward = VecUp() * 64, VecRight() * 64, VecForward() * 64
        outer = "caulk" if caulked else material

        # top brush
        res.append(Brush([
            Face((top1 + up, top2 + up, top3 + up), outer, uvData, None), # outer
            Face((top3, top2, top1), material, uvData, None), # inner
            Face((top3, top4, bot1), outer, uvData, None), # outer
            Face((bot4, top2, top1), outer, uvData, None), # outer
            Face((top1, top3, bot2), outer, uvData, None), # outer
            Face((top4, top2, bot3), outer, uvData, None), # outer
        ]))
        
        # bottom
        res.append(Brush([
            Face((bot1, bot2, bot3), material, uvData, None), # inner
            Face((bot3 - up, bot2 - up, bot1 - up), outer, uvData, None), # outer
            Face((top3, top4, bot1), outer, uvData, None), # outer
            Face((bot4, top2, top1), outer, uvData, None), # outer
            Face((top1, top3, bot2), outer, uvData, None), # outer
            Face((top4, top2, bot3), outer, uvData, None), # outer
        ]))

        # back
        res.append(Brush([
            Face((top1, top2, top3), outer, uvData, None), # outer
            Face((bot3, bot2, bot1), outer, uvData, None), # outer
            Face((bot1, top4, top3), material, uvData, None), # inner
            Face((top3 - forward, top4 - forward, bot1 - forward), outer, uvData, None), # outer
            Face((top1, top3, bot2), outer, uvData, None), # outer
            Face((top4, top2, bot3), outer, uvData, None), # outer
        ]))

        # front
        res.append(Brush([
            Face((top1, top2, top3), outer, uvData, None), # outer
            Face((bot3, bot2, bot1), outer, uvData, None), # outer
            Face((bot4 + forward, top2 + forward, top1 + forward), outer, uvData, None), # outer
            Face((top1, top2, bot4), material, uvData, None), # inner
            Face((top1, top3, bot2), outer, uvData, None), # outer
            Face((top4, top2, bot3), outer, uvData, None), # outer
        ]))

        # left
        res.append(Brush([
            Face((top1, top2, top3), outer, uvData, None), # outer
            Face((bot3, bot2, bot1), outer, uvData, None), # outer
            Face((top3, top4, bot1), outer, uvData, None), # outer
            Face((bot4, top2, top1), outer, uvData, None), # outer
            Face((top1 + right, top3 + right, bot2 + right), outer, uvData, None), # outer
            Face((bot2, top3, top1), material, uvData, None), # inner
        ]))

        # right
        res.append(Brush([
            Face((top1, top2, top3), outer, uvData, None), # outer
            Face((bot3, bot2, bot1), outer, uvData, None), # outer
            Face((top3, top4, bot1), outer, uvData, None), # outer
            Face((bot4, top2, top1), outer, uvData, None), # outer
            Face((bot3, top2, top4), material, uvData, None), # inner
            Face((top4 - right, top2 - right, bot3 - right), outer, uvData, None), # outer
        ]))

    else:
        res.append(Brush([
            Face((top1, top2, top3), material, uvData, None), # top
            Face((bot3, bot2, bot1), material, uvData, None), # bottom
            Face((top3, top4, bot1), material, uvData, None), # back
            Face((bot4, top2, top1), material, uvData, None), # front
            Face((top1, top3, bot2), material, uvData, None), # left
            Face((top4, top2, bot3), material, uvData, None) # right
        ]))

    return res

def ExportMap(source: SourceMap, options: dict) -> CoDMap:
    # create necessary folders in temp
    exportPath = options["ExportPath"] + "/" + options["MapName"] + "_" + options["TargetGame"]

    makedirs(f"{exportPath}/map_source", exist_ok=True)
    makedirs(f"{exportPath}/model_export/Corvid", exist_ok=True)
    makedirs(f"{exportPath}/source_data", exist_ok=True)
    makedirs(f"{exportPath}/texture_assets/Corvid", exist_ok=True)

    if options["TargetGame"] != "BO3":
        makedirs(f"{exportPath}/bin", exist_ok=True)
    
    if not options["SkipAssets"]:
        # convert assets
        print("Converting textures...")
        ConvertTextures(source.textureData, exportPath)
        ConvertTextures(source.modelTextureData, exportPath)

        print("Converting models...")
        ConvertModels(source.modelData, exportPath)

        # create gdt
        print("Creating GDT...")
        materialGDT = CreateMaterialGdt({**source.materialData, **source.modelMaterialData}, options)
        modelGDT = CreateModelGdt(source.modelData, source.modelTints, source.modelSkins, True if options["TargetGame"] == "BO3" else False)
        gdt = materialGDT.Combine(modelGDT)
        WriteFile(f"{exportPath}/source_data/_{options['MapName']}.gdt", str(gdt))
    
        if options["TargetGame"] != "BO3":
            WriteFile(f"{exportPath}/bin/_{options['MapName']}.bat", str(gdt.ToBat(options["MapName"])))

    # start generating map geo
    print("Generating map data...")
    res = CoDMap()

    world = Entity({
        "classname": "worldspawn"
    })

    sunSettings = {}

    AABBmin, AABBmax = VecZero(), VecZero() # furthest corners of the map

    # store rope entities in a dictionary using their targetnames
    ropeTargetNames: Dict[str, SourceEntity] = {}
    ropeTargets: Dict[str, SourceEntity] = {}
    # store brush faces, decal and overlay entities to take care of them later
    sides: Dict[int, Side] = {}
    decals: List[SourceEntity] = []
    overlays: List[SourceEntity] = []

    for solid in source.world:
        solid.CalculateVerts()
        UpdateAABB(solid.verts, AABBmin, AABBmax)

        if solid.hasDisp and not solid.isToolBrush:
            world.geo.extend(ConvertDisplacements(solid, options))

        else:
            brush = ConvertSolid(solid, options)

            if brush is not None:
                world.geo.extend(brush)

        # keep brush faces in a dictionary to apply decals later
        for side in solid.faces:
            if not side.material.startswith("tools/"):
                sides[side.id] = side

    # add converted geo to the worldspawn entity
    res.entities.append(world)

    # some entities are not needed at all
    disallowedEntities = ["func_occluder"]

    for entity in source.entities:
        # reflection probes
        if options["TargetGame"] not in ["CoD2", "BO3"] and entity["classname"] == "env_cubemap":
            res.entities.append(Entity({
                "classname": "reflecttion_probe",
                "origin": entity["origin"]
            }))
        
        # model entities
        elif entity["classname"].startswith("prop_") or "model" in entity and entity["model"].endswith(".mdl"):
            res.entities.append(ConvertProp(entity, options))

        elif entity["classname"].startswith("info_player") or entity["classname"].endswith("_spawn"):
            spawners = ConvertSpawner(entity, options)
            if spawners is not None:
                res.entities.extend(spawners)

        elif entity["classname"] in ["move_rope", "keyframe_rope"]:
            if options["TargetGame"] == "BO3":
                res.entities.extend(ConvertRopeAsEntity(entity))
            else:
                if "targetname" in entity:
                    ropeTargetNames[entity["targetname"]] = entity
                if "NextKey" in entity:
                    ropeTargets[entity["NextKey"]] = entity
            
        
        # keep decals and overlays in lists and apply them later
        elif entity["classname"] == "infodecal":
            overlays.append(entity)
    
        elif entity["classname"] == "info_overlay":
            decals.append(entity)
        
        # sun light setings
        elif entity["classname"] == "light_environment":
            sundirection = entity.GetVector("angles")
            sundirection.x = entity.GetFloat("pitch")
            sundirection.y = sundirection.y - 180 if sundirection.y >= 180 else sundirection.y + 180
            sunSettings["direction"] = sundirection
            if "ambient" in entity:
                sunSettings["ambientColor"] = VecFromStr(entity["_ambient"] if "_ambient" in entity else entity["ambient"]) / 255
            if "_light" in entity:
                sunSettings["sunColor"] = entity.GetVector("_light") / 255
        
        elif entity["classname"] in ["func_detail", "func_detail_blocker", "func_wall", "func_wall_toggle"]:
            for solid in entity.geo:
                solid.CalculateVerts()
                UpdateAABB(solid.verts, AABBmin, AABBmax)
                geo = ConvertSolid(solid, options, "detail")
                if geo is not None:
                    world.geo.extend(geo)
            
        # brushes with no collision
        elif entity["classname"] == "func_illusionary":
            for solid in entity.geo:
                solid.CalculateVerts()
                UpdateAABB(solid.verts, AABBmin, AABBmax)
                geo = ConvertSolid(solid, options, "nonColliding")
                if geo is not None:
                    world.geo.extend(geo)
        
        # this entity is very similar to the script_brushmodel entity in CoD. however, I do not know much about its use,
        # so it's better to convert them as detail brushes if at least one of their faces has a normal material
        elif entity["classname"] == "func_brush":
            for solid in entity.geo:
                solid.CalculateVerts()
                UpdateAABB(solid.verts, AABBmin, AABBmax)
                if not solid.isToolBrush:
                    geo  = ConvertSolid(solid, options, "detail")
                    if geo is not None:
                        world.geo.extend(geo)
        
        # these brush entities don't need special treatment
        elif entity["classname"] == ["func_areaportal", "func_areaportalwindow", "func_ladder"]:
            for solid in entity.geo:
                world.geo.extend(ConvertSolid(solid, options))

        # convert bomb sites from Counter-Strike to make them work with SD gamemode
        elif entity["classname"] == "func_bomb_target":
            res.entities.extend(ConvertBombSite(entity, options))

        # if it's an entity brush with a normal material on at least one of its faces, we probably need it
        elif len(entity.geo) != 0 and entity["classname"] not in disallowedEntities:
            for solid in entity.geo:
                if not solid.isToolBrush:
                    solid.CalculateVerts()
                    UpdateAABB(solid.verts, AABBmin, AABBmax)
                    geo = ConvertSolid(solid, options, "detail")
                    world.geo.extend(geo)
    
    # create curve patches from the rope entities for older CoD games
    if options["TargetGame"] != "BO3":
        for targetname, entity in ropeTargetNames.items():
            if targetname in ropeTargets:
                start, end = entity.GetVector("origin"), ropeTargets[targetname].GetVector("origin")
                width, slack = ropeTargets[targetname].GetFloat("Width"), ropeTargets[targetname].GetFloat("Slack")
                world.geo.append(ConvertRopeAsCurve(start, end, slack, width, options))

    # create sky brushes and other necessary volumes
    world.geo.extend(CreateVolume(AABBmin, AABBmax, "sky" if options["TargetGame"] == "BO3" else "ar_monastery_d_sky", True))

    print("Writing map file...")

    res.Save(f"{exportPath}/map_source/{options['MapName']}.map")

    print(f"\"{options['MapName']}.map\" has successfully been written in {exportPath}/map_source")
