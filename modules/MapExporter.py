from io import TextIOWrapper
from math import sin, cos, acos, atan2, log2, radians, degrees, inf
from typing import Dict, List, Union
from modules.Brush import Brush
from modules.SourceDir import SourceDir
from modules.AABB import AABB
from .Side import Side
from .MapReader import readMap
from glm import vec2, vec3, lerp, distance, normalize, cross, dot, min, max, length
from .Static import VecFromStr, Vec2Str, Vec2Hex
from .Gdt import Gdt
from os.path import basename, splitext
from .AssetExporter import *
from .AssetConverter import convertImages, convertModels
from .Overlay import Overlay
from .Decal import Decal
from .Progress import Progress
import modules.CoDMap.CoDMap as cod

UP, RIGHT, FORWARD = vec3(0.0, 0.0, 1.0), vec3(0.0, 1.0, 0.0), vec3(1.0, 0.0, 0.0)

def convertSide(side: Side, matSize, origin=vec3(0, 0, 0), scale=1):
    # skip invalid sides
    if len(side.points) < 3:
        print(f"Brush face {side.id} has less than 3 vertices. Skipping...")
        return None
    
    points = side.points

    material = newPath(side.material)

    #get uv points
    if material not in matSize:
        matSize[material] = vec2(512, 512)
    
    # get the uv of each point
    for point in side.points:
        side.uvs.append(side.getUV(point, matSize[material]))
    uvs: list[vec2] = side.uvs

    if len(points) % 2 == 1:
        points.append(points[-1])
        uvs.append(uvs[-1])
    count = len(points)
    rows = int(count / 2)

    res = cod.Patch(type="mesh", texture=material, size=(rows, 2))
    
    for i in range(rows):
        res.verts.append([])
        res.verts[-1].append(
            cod.PatchVert((points[i] - origin) * scale, uvs[i] * side.texSize, side.getLmapUV(points[i]))
        )
        res.verts[-1].append(
            cod.PatchVert((points[count - i - 1] - origin) * scale, uvs[count - i - 1] * side.texSize, side.getLmapUV(points[count - i - 1]))
        )
    
    return res


def getDispPoints(p1: vec3, p2: vec3, uv1: vec2, uv2: vec2, power: int):
    res = []
    rowCount = int(2 ** power) + 1
    for i in range(rowCount):
        res.append((
            lerp(p1, p2, 1 / (rowCount - 1) * i), # pos
            lerp(uv1, uv2, 1 / (rowCount - 1) * i), # uv
        ))
    return res

def convertDisplacement(side: Side, matSize, origin=vec3(0, 0, 0), scale=1, game="WaW"):
    points = side.points
    material = newPath(side.material)
    
    if material not in matSize:
        matSize[material] = vec2(512, 512)

    # get the uv of each point
    for point in side.points:
        side.uvs.append(side.getUV(point, matSize[material]))

    uvs: List[vec2] = side.uvs

    if len(points) != 4:
        print(f"Displacement has {len(points)} points. Displacements can have 4 points only. Side id: {side.id}\n")
        for point in points:
            print(point)
        return None
    
    disp: dict = side.dispinfo
    power: int = int(disp["power"])
    numVerts: int = int(2 ** power) + 1
    s: int = 0

    for i in range(4):
        if distance(points[i], disp["startpos"]) <= 1:
            s = i

    a, UVa = points[s], uvs[s]
    b, UVb = points[(s + 1) % 4], uvs[(s + 1) % 4]
    c, UVc = points[(s + 2) % 4], uvs[(s + 2) % 4]
    d, UVd = points[(s + 3) % 4], uvs[(s + 3) % 4]

    ab = getDispPoints(a, b, UVa, UVb, power)
    dc = getDispPoints(d, c, UVd, UVc, power)

    rows = []
    for i in range(len(ab)):
        rows.append(
            getDispPoints(ab[i][0], dc[i][0], ab[i][1], dc[i][1], power))

    alpha = False

    res = cod.Patch(texture=material, size=(len(rows[0]), len(rows[0])))

    for i in range(numVerts):
        row = rows[i]
        res.verts.append([])

        for j in range(numVerts):
            if disp["row"][j]["alphas"][i] != 0 and alpha != True:
                    alpha = True
            
            pos, uv = row[j]

            res.verts[-1].append(
                cod.PatchVert(
                    ((pos + vec3(0, 0, disp["elevation"]) + (disp["row"][j]["normals"][i] * disp["row"][j]["distances"][i])) - origin) * scale,
                    (uv * side.texSize) * 1,
                    side.getLmapUV(pos)
                )
            )
    
    if (game == "CoD4" or game == "CoD2") and numVerts == 17:
        res = res.Slice(9)

    if not alpha or material + "_blend" not in matSize:
        return res

    offset = vec3(0, 0, 0)
    if game == "WaW":
        offset = normalize(side.normal()) * 0.5
    
    res2 = cod.Patch(texture=material + "_blend", size=(len(rows[0]), len(rows[0])))

    for i in range(numVerts):
        row = rows[i]
        res2.verts.append([])

        for j in range(numVerts):
            pos, uv = row[j]

            res2.verts[-1].append(
                cod.PatchVert(
                    (((pos + vec3(0, 0, disp["elevation"]) + (disp["row"][j]["normals"][i] * disp["row"][j]["distances"][i])) - origin) * scale) - offset,
                    (uv * side.texSize) * 1,
                    side.getLmapUV(pos),
                    (255, 255, 255, disp["row"][j]["alphas"][i])
                )
            )
    
    if (game == "CoD4" or game == "CoD2") and numVerts == 17:
        res2 = res2.Slice(9)
    
    return [res, res2]


def convertBrush(brush: Brush, world=True, game="WaW", mapName="", origin=vec3(0, 0, 0), scale=1, matSizes: dict=None, brushConversion=False, sideDict: dict=None, AABBmin: vec3=vec3(0, 0, 0), AABBmax: vec3=vec3(0, 0, 0)):
    if matSizes is None:
        matSizes = {}
    if sideDict is None:
        sideDict = {}
    tools = {
        "toolsnodraw": "caulk",
        "toolsclip": "clip", "toolsplayerclip": "clip", "toolsinvisible": "clip", "toolsnpcclip": "clip", "toolsgrenadeclip": "clip_missile",
        "toolsinvisibleladder": "ladder", "toolsareaportal": "portal_nodraw",
        "toolsblocklight": "shadowcaster", "toolshint": "hint", "toolsskip": "skip", "toolstrigger": "trigger",
    }

    if game == "BO3" and brush.entity == "func_areaportal":
        return None
    elif brush.entity == "func_brush":
        if "targetname" in brush.entData and brush.entData["targetname"].startswith("retake"):
            return None
    elif brush.entity == "func_dustmotes" or brush.entity == "func_buyzone" or brush.entity.startswith("trigger"):
        return None
    elif brush.sides[0].material == "tools/toolstrigger":
        return None

    faces: List[cod.Face] = []
    
    resPatch: List[cod.Patch] = []

    for side in brush.sides:
        material = "caulk"

        if side.material == "tools/toolsskybox":
                return None
        
        if game == "BO3":
            if side.material in ["tools/toolsareaportal", "tools/toolshint", "tools/toolsskip"]:
                return None

        for point in side.points.copy():
            point = (point - origin) * scale
            AABBmax.x, AABBmax.y, AABBmax.z = max(AABBmax, point)
            AABBmin.x, AABBmin.y, AABBmin.z = min(AABBmin, point)

        if len(side.points) >= 3:
            sideDict[side.id] = side
        
        if side.hasDisp:
            resPatch.append(convertDisplacement(side, matSizes, origin, scale, game))
            continue
        
        if brush.hasDisp and not side.hasDisp:
            continue

        p1 = (side.p1 - origin) * scale
        p2 = (side.p2 - origin) * scale
        p3 = (side.p3 - origin) * scale

        if side.material.startswith("tools"):
            mat = basename(side.material.replace("\\", "/"))
            if mat in tools:
                material = tools[mat]
            else:
                material = "clip"

        elif side.material.startswith("liquid"):
                material = "clip_water"
        
        elif brushConversion:
            material = newPath(side.material)
        
        else:
            material = newPath(side.material)
            if material not in matSizes:
                matSizes[material] = vec2(512, 512)
            
            # Fit UVs to get proper CoD brush UV parameters
            verts = side.points
            uvs = [side.getUV(p, matSizes[material]) for p in verts]
            
            face = cod.Face(p1, p2, p3, material)
            face.Fit(side.normal(), verts, uvs)
            faces.append(face)
            continue

        faces.append(cod.Face(p1, p2, p3, material))

    if brush.hasDisp:
        return resPatch

    return [cod.Brush(faces), resPatch]
    
def _parse_light_color(entity):
    """Parse Source _light value into (color vec3 0-1, brightness float)."""
    if "_light" in entity:
        parts = [i for i in entity["_light"].split(" ") if i != ""]
        _color = [float(i) for i in parts]
        if len(_color) >= 4:
            return vec3(_color[0], _color[1], _color[2]) / 255, _color[3]
        elif len(_color) == 3:
            return vec3(_color[0], _color[1], _color[2]) / 255, 300
    return vec3(1, 1, 1), 300

def _parse_light_radius(entity, brightness=300):
    """Convert Source light falloff parameters to a CoD radius."""
    if "_fifty_percent_distance" in entity and float(entity["_fifty_percent_distance"]) > 0:
        fifty = float(entity["_fifty_percent_distance"])
        if "_zero_percent_distance" in entity and float(entity["_zero_percent_distance"]) > 0:
            return float(entity["_zero_percent_distance"])
        return fifty * 2
    if "_zero_percent_distance" in entity and float(entity["_zero_percent_distance"]) > 0:
        return float(entity["_zero_percent_distance"])
    # no explicit falloff distance, estimate from brightness
    # Source brightness roughly correlates with how far light reaches
    return max(brightness, 100)

def _parse_light_intensity(brightness):
    """Convert Source brightness to CoD intensity (0-1 range where 1 is fullbright)."""
    # Source brightness of 300 is a typical indoor light
    # Scale so 300 maps to roughly 1.0
    return min(brightness / 300, 1)

def convertLight(entity, scale=1.0):
    color, brightness = _parse_light_color(entity)
    radius = _parse_light_radius(entity, brightness)
    intensity = _parse_light_intensity(brightness)

    return cod.Entity({
        "classname": "light",
        "origin": VecFromStr(entity["origin"], 3) * scale,
        "_color": color,
        "radius": radius,
        "intensity": intensity
    })

def convertSpotLight(entity, game="WaW", scale=1.0):
    color, brightness = _parse_light_color(entity)
    origin = VecFromStr(entity["origin"], 3)
    radius = _parse_light_radius(entity, brightness)
    intensity = _parse_light_intensity(brightness)

    # Source _cone and _inner_cone are half-angles from center
    # CoD fov_outer is total angle ("90 would go +/-45 degrees")
    # So Source half-angle needs to be doubled for CoD
    cone = float(entity.get("_cone", "45"))
    inner_cone = float(entity.get("_inner_cone", "30"))
    fov_outer = cone * 2
    fov_inner = inner_cone * 2

    angles = VecFromStr(entity["angles"], 3)
    pitch = float(entity.get("pitch", entity["angles"].split(" ")[0]))
    yaw = angles.y

    # calculate spotlight direction vector from Source angles
    pitch_rad = radians(pitch)
    yaw_rad = radians(yaw)

    direction = vec3(
        cos(pitch_rad) * cos(yaw_rad),
        cos(pitch_rad) * sin(yaw_rad),
        sin(pitch_rad)
    )

    res = []

    if game != "BO3":
        res.append(cod.Entity({
            "classname": "light",
            "origin": origin * scale,
            "_color": color,
            "radius": radius,
            "intensity": intensity,
            "target": "spotlight_" + entity["id"],
            "fov_outer": fov_outer,
            "fov_inner": fov_inner,
        }))

        res.append(cod.Entity({
            "classname": "info_null",
            "origin": (origin + direction * 50) * scale,
            "targetname": "spotlight_" + entity["id"]
        }))

    else:
        # BO3 spot light default direction is -Z (downward)
        # Rotation order: pitch (around Y), then yaw (around Z)
        dz = max(-1.0, min(1.0, -direction.z))
        bo3_pitch = degrees(acos(dz))
        bo3_yaw = degrees(atan2(-direction.y, -direction.x))

        # Source brightness to BO3 stops (logarithmic scale, 300 brightness ≈ 11 stops)
        stops = log2(max(brightness, 1) / 300) + 11

        res = cod.Entity({
            "classname": "light",
            "origin": origin * scale,
            "_color": color,
            "PRIMARY_TYPE": "PRIMARY_SPOT",
            "angles": vec3(bo3_pitch, bo3_yaw, 0),
            "radius": radius,
            "stops": round(stops, 2),
            "fov_outer": fov_outer,
            "spawnflags": "84",
        })

    return res

def convertRope(entity, skyOrigin=vec3(0, 0, 0), scale=1, curve=False, ropeDict: dict=None):
    if ropeDict is None:
        ropeDict = {}
    # sadly, cod 4 does not support rope entities, so we have to create curve patches for them instead
    if curve:
        origin = (VecFromStr(entity["origin"], 3) - skyOrigin) * scale
        slack = float(entity.get("Slack", "128"))
        width = float(entity.get("Width", "1"))

        if "NextKey" in entity:
            ropeDict["start"][entity["NextKey"]] = {
                "origin": origin,
                "target": entity["NextKey"],
                "slack": slack,
                "width": width,
                "id": entity["id"]
            }
        if "targetname" in entity:
            ropeDict["end"][entity["targetname"]] = {
                "origin": origin,
                "targetname": entity["targetname"],
                "id": entity["id"]
            }
    else:
        res = []
        origin = (VecFromStr(entity["origin"], 3) - skyOrigin) * scale
        slack = float(entity.get("Slack", "128"))
        width = float(entity.get("Width", "1"))

        if "targetname" in entity:
            res.append(cod.Entity({
                "classname": "info_null",
                "origin": origin,
                "targetname": entity["targetname"]
            }))
        if "NextKey" in entity:
            res.append(cod.Entity({
                "classname": "rope",
                "origin": origin,
                "target": entity["NextKey"],
                "length_scale": slack / 128,
                "width": width * 3
            }))
        return res

def convertRopeAsCurve(start: vec3, end: vec3, slack: float, width: float=1, game="WaW"):
    mid: vec3 = lerp(start, end, 0.5)
    mid.z -= slack * 0.75

    # calculate the forward, right and up vectors perpendicular to the rope direction
    dif = end - start
    if length(dif) == 0:
        forward = vec3(1, 0, 0)
    else:
        forward = normalize(dif)

    # pick a reference vector that isn't parallel to forward
    ref = vec3(1, 0, 0) if abs(dot(forward, UP)) > 0.9 else UP
    right = normalize(cross(forward, ref))
    up = normalize(cross(right, forward))
    left = right * -1

    # multiply each value with the half of the width value to get proper thickness
    width *= 0.5
    up *= width
    left *= width
    right *= width
    top = up
    bottom = up * -1
    topLeft = left + up
    bottomLeft = left - up
    topRight = right + up
    bottomRight = right - up

    mats = {"WaW": "global_wires", "CoD4": "credits_black", "CoD2": "egypt_metal_pipe2"}
    mat = mats[game]
    
    res = cod.Patch(type="curve", contents=["nonColliding"], texture=mat, size=(9, 3))

    res.verts.append([
        cod.PatchVert(start + bottom, vec2(0, 0), vec2(1, 1)),
        cod.PatchVert(mid + bottom, vec2(0, -84316), vec2(1, 45)),
        cod.PatchVert(end + bottom, vec2(0, -167833), vec2(1, 89))
    ])
    res.verts.append([
        cod.PatchVert(start + bottomLeft, vec2(87, 0), vec2(3, 1)),
        cod.PatchVert(mid + bottomLeft, vec2(87, -84316), vec2(3, 45)),
        cod.PatchVert(end + bottomLeft, vec2(87, -167833), vec2(3, 89))
    ])
    res.verts.append([
        cod.PatchVert(start + left, vec2(276, 0), vec2(5, 1)),
        cod.PatchVert(mid + left, vec2(276, -84316), vec2(5, 45)),
        cod.PatchVert(end + left, vec2(276, -167833), vec2(5, 89))
    ])
    res.verts.append([
        cod.PatchVert(start + topLeft, vec2(465, 0), vec2(7, 1)),
        cod.PatchVert(mid + topLeft, vec2(465, -84316), vec2(7, 45)),
        cod.PatchVert(end + topLeft, vec2(465, -167833), vec2(7, 89))
    ])
    res.verts.append([
        cod.PatchVert(start + top, vec2(552, 0), vec2(9, 1)),
        cod.PatchVert(mid + top, vec2(552, -84316), vec2(9, 45)),
        cod.PatchVert(end + top, vec2(552, -167833), vec2(9, 89))
    ])
    res.verts.append([
        cod.PatchVert(start + topRight, vec2(639, 0), vec2(9, 1)),
        cod.PatchVert(mid + topRight, vec2(639, -84316), vec2(9, 45)),
        cod.PatchVert(end + topRight, vec2(639, -167833), vec2(9, 89))
    ])
    res.verts.append([
        cod.PatchVert(start + right, vec2(828, 0), vec2(11, 1)),
        cod.PatchVert(mid + right, vec2(828, -84316), vec2(11, 45)),
        cod.PatchVert(end + right, vec2(828, -167833), vec2(11, 89))
    ])
    res.verts.append([
        cod.PatchVert(start + bottomRight, vec2(1017, 0), vec2(13, 1)),
        cod.PatchVert(mid + bottomRight, vec2(1017, -84316), vec2(13, 45)),
        cod.PatchVert(end + bottomRight, vec2(1017, -167833), vec2(13, 89))
    ])
    res.verts.append([
        cod.PatchVert(start + bottom, vec2(1104, 0), vec2(15, 1)),
        cod.PatchVert(mid + bottom, vec2(1104, -84316), vec2(15, 45)),
        cod.PatchVert(end + bottom, vec2(1104, -167833), vec2(15, 89))
    ])

    return res

def convertProp(entity, game="WaW", skyOrigin=vec3(0, 0, 0), scale=1, mdlScale=1):
    origin = (VecFromStr(entity["origin"], 3) - skyOrigin) * scale
    modelScale = float(entity["uniformscale"] if "uniformscale" in entity else entity["modelscale"] if "modelscale" in entity else "1") * mdlScale

    if "model" not in entity:
        return cod.Entity({
            "classname": "info_null",
            "original_classname": entity["classname"],
            "origin": origin
        })

    modelName = "m_" + splitext(newPath(entity["model"]))[0]

    if "skin" in entity and entity["skin"] != "0":
            modelName += f'_skin{entity["skin"]}'

    if game == "BO3" and "rendercolor" in entity:
        if entity["rendercolor"] != "255 255 255":
            modelName += "_" + Vec2Hex(VecFromStr(entity["rendercolor"], 3))

    if game == "CoD2":
        modelName = "xmodel/" + modelName

    return cod.Entity({
        "classname": "dyn_model" if entity["classname"].startswith("prop_physics") and game != "CoD2" else "misc_model",
        "model": modelName,
        "origin": origin,
        "angles": entity["angles"],
        "spawnflags": "16" if entity["classname"].startswith("prop_physics") else "",
        "modelscale": modelScale
    })

def convertCubemap(entity, scale=1.0):
    return cod.Entity({
        "classname": "reflection_probe",
        "origin": VecFromStr(entity["origin"], 3) * scale
    })

def convertSpawner(entity, scale=1.0):
    origin = VecFromStr(entity["origin"], 3) * scale
    origin.z += 32

    spawners = {
        "info_player_terrorist": "mp_tdm_spawn_axis_start",
        "info_player_counterterrorist": "mp_tdm_spawn_allies_start",
        "info_deathmatch_spawn": "mp_dm_spawn",
        "info_player_deathmatch": "mp_dm_spawn",
        "info_player_start": "info_player_start",
        "info_player_allies": "mp_tdm_spawn_allies_start",
        "info_player_axis": "mp_tdm_spawn_axis_start"
    }

    if entity["classname"] in spawners:
        classname = spawners[entity["classname"]]
    else:
        return None

    res = []

    res.append(cod.Entity({
        "classname": classname,
        "origin": origin,
        "angles": entity["angles"]
    }))

    if classname == "info_player_start":
        res.append(cod.Entity({
            "classname": "mp_global_intermission",
            "origin": origin
        }))

        res.append(cod.Entity({
            "classname": "mp_tdm_spawn",
            "origin": origin
        }))
    
    # make sure to add spawners for sd too
    if classname == "mp_tdm_spawn_axis_start" or classname == "mp_tdm_spawn_allies_start":
        res.append(cod.Entity({
            "classname": "mp_sd_spawn_attacker" if classname == "mp_tdm_spawn_axis_start" else "mp_sd_spawn_defender",
            "origin": origin,
            "angles": entity["angles"]
        }))

    return res

def convertBombsite(entity, scale=1, game="WaW", site=""):
    solidVal = entity["solid"]
    solids = solidVal if isinstance(solidVal, list) else [solidVal]
    brushes: List[Brush] = []

    # calculate the geo of the trigger(s)
    for solid in solids:
        sideVal = solid["side"]
        sideList = sideVal if isinstance(sideVal, list) else [sideVal]
        sides: List[Side] = []
        for side in sideList:
            sides.append(Side(side))
        brushes.append(Brush(sides))

    # build CoD trigger brushes directly
    triggerBrushes = []
    for brush in brushes:
        faces = [cod.Face(side.p1 * scale, side.p2 * scale, side.p3 * scale, "trigger") for side in brush.sides]
        triggerBrushes.append(cod.Brush(faces))

    # get the center of the trigger(s) to decide where to place the bomb model
    center = vec3(0, 0, 0)
    lowest = None
    for brush in brushes:
        for side in brush.sides:
            if lowest is None:
                lowest = side.center().z
            else:
                lowest = min(lowest, side.center().z)
            center = center + side.center()

    center = center / sum([len(brush.sides) for brush in brushes])
    if lowest is not None:
        center.z = lowest # make sure the model is always at the bottom of the trigger
    bombsite = "_" + (entity["targetname"][0].lower() if "targetname" in entity else site)

    res: List[cod.Entity] = []

    res.append(cod.Entity({
        "classname": "trigger_use_touch",
        "script_bombmode_original": "1",
        "target": "target" + bombsite,
        "script_gameobjectname": "bombzone",
        "targetname": "bombzone",
        "script_label": bombsite
    }))
    res[-1].geo.append(triggerBrushes)

    res.append(cod.Entity({
        "targetname": "targetname" + bombsite,
        "classname": "trigger_use_touch",
        "script_gameobjectname": "bombzone"
    }))
    res[-1].geo.append(triggerBrushes)

    res.append(cod.Entity({
        "target": "targetname" + bombsite,
        "targetname": "target" + bombsite,
        "spawnflags": "4",
        "script_gameobjectname": "bombzone",
        "script_exploder": "1",
        "origin": center * scale,
        "model": "xmodel/tag_origin" if game=="CoD2" else "tag_origin",
        "classname": "script_model"
    }))

    res.append(cod.Entity({
        "classname": "script_model",
        "model": "xmodel/tag_origin" if game=="CoD2" else "tag_origin",
        "origin": center * scale,
        "spawnflags": "4",
        "targetname": "exploder",
        "script_exploder": "1"
    }))

    return res

def createVolume(AABBmin: vec3, AABBmax: vec3, texture="caulk", hollow=False, caulked=False) -> Union[cod.Brush, List[cod.Brush]]:
    top1 = vec3(AABBmax) # top points
    top2 = vec3(AABBmax.x, AABBmin.y, AABBmax.z)
    top3 = vec3(AABBmin.x, AABBmax.y, AABBmax.z)
    top4 = vec3(AABBmin.x, AABBmin.y, AABBmax.z)
    bot1 = vec3(AABBmin) # bottom points
    bot2 = vec3(AABBmin.x, AABBmax.y, AABBmin.z)
    bot3 = vec3(AABBmax.x, AABBmin.y, AABBmin.z)
    bot4 = vec3(AABBmax.x, AABBmax.y, AABBmin.z)

    if hollow:
        res: List[cod.Brush] = []
        up, right, forward = UP * 64, RIGHT * 64, FORWARD * 64
        outer = "caulk" if caulked else texture

        # top brush
        res.append(cod.Brush([
            cod.Face(top1 + up, top2 + up, top3 + up, outer), # outer
            cod.Face(top3, top2, top1, texture), # inner
            cod.Face(top3, top4, bot1, outer), # outer
            cod.Face(bot4, top2, top1, outer), # outer
            cod.Face(top1, top3, bot2, outer), # outer
            cod.Face(top4, top2, bot3, outer), # outer
        ]))

        # bottom
        res.append(cod.Brush([
            cod.Face(bot1, bot2, bot3, texture), # inner
            cod.Face(bot3 - up, bot2 - up, bot1 - up, outer), # outer
            cod.Face(top3, top4, bot1, outer), # outer
            cod.Face(bot4, top2, top1, outer), # outer
            cod.Face(top1, top3, bot2, outer), # outer
            cod.Face(top4, top2, bot3, outer), # outer
        ]))

        # back
        res.append(cod.Brush([
            cod.Face(top1, top2, top3, outer), # outer
            cod.Face(bot3, bot2, bot1, outer), # outer
            cod.Face(bot1, top4, top3, texture), # inner
            cod.Face(top3 - forward, top4 - forward, bot1 - forward, outer), # outer
            cod.Face(top1, top3, bot2, outer), # outer
            cod.Face(top4, top2, bot3, outer), # outer
        ]))

        # front
        res.append(cod.Brush([
            cod.Face(top1, top2, top3, outer), # outer
            cod.Face(bot3, bot2, bot1, outer), # outer
            cod.Face(bot4 + forward, top2 + forward, top1 + forward, outer), # outer
            cod.Face(top1, top2, bot4, texture), # inner
            cod.Face(top1, top3, bot2, outer), # outer
            cod.Face(top4, top2, bot3, outer), # outer
        ]))

        # left
        res.append(cod.Brush([
            cod.Face(top1, top2, top3, outer), # outer
            cod.Face(bot3, bot2, bot1, outer), # outer
            cod.Face(top3, top4, bot1, outer), # outer
            cod.Face(bot4, top2, top1, outer), # outer
            cod.Face(top1 + right, top3 + right, bot2 + right, outer), # outer
            cod.Face(bot2, top3, top1, texture), # inner
        ]))

        # right
        res.append(cod.Brush([
            cod.Face(top1, top2, top3, outer), # outer
            cod.Face(bot3, bot2, bot1, outer), # outer
            cod.Face(top3, top4, bot1, outer), # outer
            cod.Face(bot4, top2, top1, outer), # outer
            cod.Face(bot3, top2, top4, texture), # inner
            cod.Face(top4 - right, top2 - right, bot3 - right, outer), # outer
        ]))

        return res

    return cod.Brush([
        cod.Face(top1, top2, top3, texture), # top
        cod.Face(bot3, bot2, bot1, texture), # bottom
        cod.Face(top3, top4, bot1, texture), # back
        cod.Face(bot4, top2, top1, texture), # front
        cod.Face(top1, top3, bot2, texture), # left
        cod.Face(top4, top2, bot3, texture) # right
    ])

# in CoD, it is better to seal the whole map in 6 skybox brushes
# in Source however, there are always too many skybox brushes, which is not ideal for CoD
# this function basically takes the two far ends of the map and then uses those positions to create 6 skybox brushes with them
def createSkyBrushes(AABBmin: vec3, AABBmax: vec3, mapName="", game="WaW"):
    if AABBmin == AABBmax:
        return None, None
    
    # move the points further to avoid collision with map geo
    AABBmax = AABBmax + vec3(250, 250, 500)
    AABBmin = AABBmin + vec3(-250, -250, -100)

    sky = createVolume(AABBmin, AABBmax, "sky" if game == "BO3" else mapName + "_sky", True, True if game != "BO3" else False)

    # create sun, fps and umbra volumes for BO3 
    vol: List[cod.Entity] = []
    if game == "BO3":
        vol.append(cod.Entity({
            "classname": "volume_sun",
            "ssi": f"{mapName}_ssi",
            "grid_density": "32",
            "shadowBiasScale": "1",
            "shadowSplitDistance": "2000",
            "ssi1": f"{mapName}_ssi",
            "streamLighting": "1"
        }))
        vol[-1].geo.append(createVolume(AABBmin, AABBmax, "sun_volume"))

        vol.append(cod.Entity({
            "classname": "umbra_volume",
        }))
        vol[-1].geo.append(createVolume(AABBmin, AABBmax, "umbra_volume"))

    return sky, vol

def exportMap(
        vmfString, vpkFiles=[], gameDirs=[], game="WaW",
        skipMats=False, skipModels=False, mapName="",
        brushConversion=False, scale=1.0, file: TextIOWrapper=None,
        outputDir="", progress: Progress=None
    ):
    if progress is None:
        progress = Progress()
    outDir = outputDir

    mapData = readMap(vmfString)

    # load &/ define the paks and folders where the assets will be grabbed from
    gamePath = SourceDir()
    for vpkFile in vpkFiles:
        progress.log(f"Mounting {vpkFile}...")
        gamePath.add(vpkFile)
    for dir in gameDirs:
        progress.log(f"Mounting {dir}...")
        gamePath.add(dir)

    # load world materials and textures into memory
    progress.log("Loading materials...")
    progress.overall(1, 13)
    materials, vmtCache = loadMaterials(mapData["materials"], gamePath, progress)
    progress.log("Loading texture data...")
    progress.overall(2, 13)
    matData = loadTextures(materials, vmtCache, gamePath, progress=progress)
    matSizes = matData["sizes"]

    # load models, model materials and textures into memory
    modelData = {}
    if not skipModels:
        progress.log("Loading models...")
        progress.overall(3, 13)
        modelData = loadModels(mapData["models"], gamePath, progress)
        progress.log("Loading model materials...")
        progress.overall(4, 13)
        mdlMaterials, mdlVmtCache = loadModelMaterials(mapData["models"], modelData, gamePath, mapData["modelTints"], mapData["modelSkins"], mapData["skinTints"], game, progress)
        mdlMatData = loadTextures(mdlMaterials, mdlVmtCache, gamePath, True, progress=progress)

    # collect overlay/decal material names for GDT tagging
    overlayMats = set()
    for entity in mapData["entities"]:
        if entity["classname"] == "info_overlay" and "material" in entity:
            overlayMats.add(newPath(entity["material"].lower()))
        elif entity["classname"] == "infodecal" and "texture" in entity:
            overlayMats.add(newPath(entity["texture"].lower()))

    # resolve overlay material names to their texture file names
    overlayTextures = set()
    for matName in overlayMats:
        if matName in matData["vmts"]:
            shader = list(matData["vmts"][matName])[0]
            mat = matData["vmts"][matName][shader]
            if "$basetexture" in mat:
                overlayTextures.add(newPath(mat["$basetexture"].strip(), shorten=True))

    # create GDT files
    gdtFile = Gdt()

    # CoD 2 needs different arguments for converter, so we need to make the GDT class we're converting for CoD 2
    if game == "CoD2":
        gdtFile.CoD2 = True
        gdtFile.name = mapName

    batFile = ""
    if not skipMats or not skipModels:
        progress.log("Generating GDT file...")
        progress.overall(5, 13)
    if not skipMats:
        allColorMaps = set(matData["colorMaps"] + matData["colorMapsAlpha"])
        worldMats = createMaterialGdt(matData["vmts"], game, set(matData["vtfData"].keys()), overlayMats=overlayMats, colorMaps=allColorMaps, progress=progress)
        gdtFile += worldMats
    if game != "BO3" and not skipMats:
        batFile += worldMats.toBat()
    if not skipModels:
        allMdlColorMaps = set(mdlMatData["colorMaps"] + mdlMatData["colorMapsAlpha"])
        modelMats = createMaterialGdt(mdlMatData["vmts"], game, set(mdlMatData["vtfData"].keys()), colorMaps=allMdlColorMaps, progress=progress)
        gdtFile += modelMats
    if game != "BO3" and not skipModels:
        batFile += modelMats.toBat()
    if not skipModels:
        models = createModelGdt(mapData["models"], game, mapData["modelTints"], mapData["modelSkins"], mapData["skinTints"], progress=progress)
        gdtFile += models
    if game != "BO3" and not skipModels:
        batFile += models.toBat()
    # create GDT files for images for Bo3
    if game == "BO3":
        if not skipMats:
            gdtFile += createImageGdt(matData, progress)
        if not skipModels:
            gdtFile += createImageGdt(mdlMatData, progress)

    # convert the textures
    if not skipMats:
        progress.log("Converting textures...")
        progress.overall(6, 13)
        convertImages(matData, f"{outDir}/texture_assets/corvid", "tif" if game == "BO3" else "tga", overlayTextures, progress)
        if not skipModels:
            convertImages(mdlMatData, f"{outDir}/texture_assets/corvid", "tif" if game == "BO3" else "tga", progress=progress)

    # convert the models
    if not skipModels:
        progress.log("Converting models...")
        progress.overall(7, 13)
        materialNames = set(mdlMaterials)
        convertModels(mapData["models"], modelData, mapData["modelTints"], mapData["modelSkins"], mapData["skinTints"], materialNames, game, scale, outDir, progress)

    # generate map geometry
    progress.log("Generating .map file...")
    progress.overall(8, 13)
    res = cod.Map()
    world = cod.Entity({
        "classname": "worldspawn"
    })
    res.entities.append(world)

    worldSpawnSettings = {}

    # store the furthest points for each axis to calculate the bounding box of the whole map
    AABBmin = vec3(0, 0, 0)
    AABBmax = vec3(0, 0, 0)

    # store brush sides in a dictionary for info_overlay entities
    sideDict: Dict[str, Side] = {}
    
    # store overlay entities to convert after all brush sides are collected
    overlays: List[dict] = []

    # store decal entities to convert after all brushes are collected
    decals: List[dict] = []

    # keep track of plain brushes that will be checked for decal collision later
    brushDict: Dict[str, Brush] = {}

    # store rope entity info in a dictionary to convert them as curve patches if needed
    ropeDict: Dict[str, dict] = {
        "start": {},
        "end": {}
    }

    lenWorld = len(mapData["worldBrushes"])
    lenEntBrushes = len(mapData["entityBrushes"])
    lenEnts = len(mapData["entities"])
    lenSky = len(mapData["skyBrushes"])
    lenSkyEntBrushes = len(mapData["skyEntityBrushes"])
    lenSkyEnts = len(mapData["skyEntities"])
    total = (lenWorld + lenEntBrushes + lenEnts + lenSky + lenSkyEntBrushes + lenSkyEnts)

    bombsites = ["a", "b", "c", "d", "e", "f", "g"] # let's just make sure in case the maps has lots of bomb sites
    currentBombsite = 0 

    # convert world geo & entities
    for i, brush in enumerate(mapData["worldBrushes"]):
        progress.current(i + 1, total)
        geo = convertBrush(brush, True, game, mapName, matSizes=matSizes, brushConversion=brushConversion, sideDict=sideDict, scale=scale, AABBmin=AABBmin, AABBmax=AABBmax)
        if geo is not None:
            world.geo.append(geo)

        if not brush.isToolBrush and not brush.hasDisp:
            brushDict[brush.id] = brush

    for i, brush in enumerate(mapData["entityBrushes"], lenWorld):
        progress.current(i + 1, total)
        geo = convertBrush(brush, False, game, mapName, matSizes=matSizes, sideDict=sideDict, scale=scale, AABBmin=AABBmin, AABBmax=AABBmax)
        if geo is not None:
            world.geo.append(geo)
        
        if not brush.isToolBrush and not brush.hasDisp:
            brushDict[brush.id] = brush

    entities: Dict[str, str] = mapData["entities"]
    for i, entity in enumerate(entities, lenWorld + lenEntBrushes):
        if "origin" in entity:
            origin = VecFromStr(entity["origin"], 3) * scale
            AABBmax.x, AABBmax.y, AABBmax.z = max(AABBmax, origin)
            AABBmin.x, AABBmin.y, AABBmin.z = min(AABBmin, origin)

        try:
            progress.current(i + 1, total)

            if entity["classname"].startswith("prop_"):
                res.entities.append(convertProp(entity, game, scale=scale))
            elif entity["classname"] == "light":
                res.entities.append(convertLight(entity, scale=scale))
            elif entity["classname"] == "light_spot":
                res.entities.append(convertSpotLight(entity, game, scale=scale))
            elif entity["classname"] == "move_rope" or entity["classname"] == "keyframe_rope":
                if game == "CoD4" or game == "CoD2":
                    convertRope(entity, curve=True, ropeDict=ropeDict, scale=scale)
                else:
                    res.entities.append(convertRope(entity))
            elif entity["classname"] == "env_cubemap":
                if game == "CoD2" or game == "BO3":
                    continue
                res.entities.append(convertCubemap(entity, scale=scale))
            elif entity["classname"].startswith("info_player") or entity["classname"].endswith("_spawn"):
                res.entities.append(convertSpawner(entity, scale=scale))
            elif entity["classname"] == "info_overlay":
                if entity["sides"] != "":
                    overlays.append(entity)
            elif entity["classname"] == "infodecal":
                decals.append(entity)
            elif entity["classname"] == "func_bomb_target":
                res.entities.append(convertBombsite(entity, scale=scale, game=game, site=bombsites[currentBombsite]))
                currentBombsite += 1
            elif entity["classname"] == "light_environment":
                # sun direction
                # Source pitch override is counter-clockwise (-90 = down)
                # Source angles pitch is clockwise (+90 = down)
                # CoD sundirection pitch: negative = downward (0 to -90)
                angles = VecFromStr(entity["angles"], 3)
                if "pitch" in entity:
                    # pitch key is already counter-clockwise (negative = down), same as CoD
                    source_pitch = float(entity["pitch"])
                else:
                    # angles pitch is clockwise (positive = down), negate to counter-clockwise
                    source_pitch = -angles.x
                source_yaw = angles.y

                # store raw Source angles for BO3 SSI conversion
                if game == "BO3":
                    worldSpawnSettings["source_sun_pitch"] = source_pitch
                    worldSpawnSettings["source_sun_yaw"] = source_yaw

                # flip yaw by 180 to match CoD sun direction convention
                yaw = source_yaw - 180 if source_yaw >= 180 else source_yaw + 180
                worldSpawnSettings["sundirection"] = vec3(source_pitch, yaw, 0)

                # sun color and brightness from _light (R G B brightness)
                # Source _light intensity I spans ~2 (deep night) to ~1500 (saturated day).
                # Stock CoD4/WaW sunlight spans 0.25 – 3.0 (median ~1.3). sqrt(I/100)
                # fits that range: I=100→1.0, I=400→2.0, I=900→3.0.
                if "_light" in entity:
                    light_parts = [float(v) for v in entity["_light"].split() if v != ""]
                    sun_color = vec3(light_parts[0], light_parts[1], light_parts[2]) / 255
                    source_intensity = light_parts[3] if len(light_parts) > 3 else 400
                    if game == "BO3":
                        worldSpawnSettings["source_sun_intensity"] = source_intensity
                    sun_brightness = (max(source_intensity, 0.0) / 100) ** 0.5
                    worldSpawnSettings["suncolor"] = sun_color
                    worldSpawnSettings["sunlight"] = round(max(0.25, min(3.0, sun_brightness)), 3)
                else:
                    worldSpawnSettings["suncolor"] = vec3(1, 1, 1)
                    worldSpawnSettings["sunlight"] = 1.5

                # ambient light from _ambient (R G B brightness)
                # Stock CoD4/WaW ambient sits in 0.0 – 0.35 with median ~0.2.
                ambient_key = "_ambient" if "_ambient" in entity else "ambient" if "ambient" in entity else None
                if ambient_key:
                    ambient_parts = [float(v) for v in entity[ambient_key].split() if v != ""]
                    ambient_color = vec3(ambient_parts[0], ambient_parts[1], ambient_parts[2]) / 255
                    ambient_brightness = ambient_parts[3] / 500 if len(ambient_parts) > 3 else 0.2
                    worldSpawnSettings["_color"] = ambient_color
                    worldSpawnSettings["ambient"] = round(max(0.1, min(0.35, ambient_brightness)), 3)
                else:
                    worldSpawnSettings["ambient"] = 0.2

                # diffuse settings derived from ambient
                worldSpawnSettings["sundiffusecolor"] = worldSpawnSettings.get("_color", vec3(0.75, 0.82, 0.85))
                worldSpawnSettings["diffusefraction"] = 0.3
                if game == "CoD4":
                    worldSpawnSettings["reflection_ignore_portals"] = "1"
        except Exception as e:
            progress.log(f"Could not convert the entity '{entity['classname']}' with the ID {entity['id']}. Skipping...")
            progress.log(f"Exception message:\n{e}")
            pass
            
    # convert 3d skybox geo & entities
    for i, brush in enumerate(mapData["skyBrushes"], lenWorld + lenEntBrushes + lenEnts):
        progress.current(i + 1, total)
        geo = convertBrush(brush, True, game, mapName, origin=mapData["skyBoxOrigin"], scale=scale * mapData["skyBoxScale"], sideDict=sideDict, AABBmin=AABBmin, AABBmax=AABBmax)
        if geo is not None:
            world.geo.append(geo)

    for i, brush in enumerate(mapData["skyEntityBrushes"], lenWorld + lenEntBrushes + lenEnts + lenSky):
        progress.current(i + 1, total)
        geo = convertBrush(brush, False, game, mapName, origin=mapData["skyBoxOrigin"], scale=scale * mapData["skyBoxScale"], sideDict=sideDict, AABBmin=AABBmin, AABBmax=AABBmax)
        if geo is not None:
            world.geo.append(geo)

    for i, entity in enumerate(mapData["skyEntities"], lenWorld + lenEntBrushes + lenEnts + lenSky + lenSkyEntBrushes):
        progress.current(i + 1, total)

        origin = (VecFromStr(entity["origin"], 3) - mapData["skyBoxOrigin"]) * mapData["skyBoxScale"] * scale
        AABBmax.x, AABBmax.y, AABBmax.z = max(AABBmax, origin)
        AABBmin.x, AABBmin.y, AABBmin.z = min(AABBmin, origin)

        if entity["classname"].startswith("prop_"):
            res.entities.append(convertProp(entity, game, mapData["skyBoxOrigin"], mdlScale=mapData["skyBoxScale"], scale=scale * mapData["skyBoxScale"]))
        elif entity["classname"] == "move_rope" or entity["classname"] == "keyframe_rope":
            if game == "CoD4":
                convertRope(entity, skyOrigin=mapData["skyBoxOrigin"], scale=scale * mapData["skyBoxScale"], curve=True, ropeDict=ropeDict)
            else:
                res.entities.append(convertRope(entity, skyOrigin=mapData["skyBoxOrigin"], scale=scale * mapData["skyBoxScale"]))

    # convert ropes to curve patches for cod 4
    if game == "CoD4" or game == "CoD2":
        for val in ropeDict["start"].values(): 
            if val["target"] in ropeDict["end"]:
                world.geo.append(convertRopeAsCurve(
                    val["origin"],
                    ropeDict["end"][val["target"]]["origin"],
                    val["slack"],
                    val["width"],
                    game
                ))

    # create sky brushes and other necessary stuff
    skyBrushes, volumes = createSkyBrushes(AABBmin, AABBmax, mapName, game)
    if skyBrushes is not None:
        world.geo.append(skyBrushes)
    if volumes is not None:
        res.entities.append(volumes)

    # convert overlays and decals with overlap-based z-offsets
    # track placed decals per face: list of (origin, half_w, half_h, offset)
    faceDecals: Dict[str, list] = {}

    def getOverlapOffset(sideIds, origin, half_w, half_h):
        """Find the next offset based on overlapping decals on the same faces."""
        maxOffset = 0
        for sid in sideIds:
            for o_origin, o_hw, o_hh, o_offset in faceDecals.get(sid, []):
                # check if close enough to overlap — use max of both half-extents
                overlap_dist = max(half_w + o_hw, half_h + o_hh)
                if distance(origin, o_origin) < overlap_dist:
                    maxOffset = max(maxOffset, o_offset + 1)
        for sid in sideIds:
            if sid not in faceDecals:
                faceDecals[sid] = []
            faceDecals[sid].append((origin, half_w, half_h, maxOffset))
        return maxOffset

    total = len(overlays)
    if total > 0:
        progress.log("Converting overlays...")
        progress.overall(9, 13)
    for i, overlay in enumerate(overlays):
        progress.current(i + 1, total)
        try:
            obj = Overlay(overlay, sideDict, matSizes, scale=scale)
            zOffset = 0.0
            if not obj.empty:
                origin = vec3(float(obj.BasisOrigin[0]), float(obj.BasisOrigin[1]), float(obj.BasisOrigin[2]))
                hw = float(distance(vec3(float(obj.uv_points[0][0]), float(obj.uv_points[0][1]), float(obj.uv_points[0][2])),
                                     vec3(float(obj.uv_points[3][0]), float(obj.uv_points[3][1]), float(obj.uv_points[3][2])))) / 2
                hh = float(distance(vec3(float(obj.uv_points[0][0]), float(obj.uv_points[0][1]), float(obj.uv_points[0][2])),
                                     vec3(float(obj.uv_points[1][0]), float(obj.uv_points[1][1]), float(obj.uv_points[1][2])))) / 2
                sideIds = [s.id for s in obj.sides]
                zOffset = getOverlapOffset(sideIds, origin, hw, hh) * 0.125
            maxPatchSize = 9 if (game == "CoD4" or game == "CoD2") else 30
            patches = obj.to_patches(zOffset=zOffset, maxPatchSize=maxPatchSize)
            for patch in patches:
                world.geo.append(patch)
        except Exception as e:
            pass

    # convert decals — sort by entity id so overlapping decals layer consistently
    decals.sort(key=lambda e: int(e.get("id", 0)))
    total = len(decals)
    if total > 0:
        progress.log("Converting decals...")
        progress.overall(10, 13)
    for i, entity in enumerate(decals):
        progress.current(i + 1, total)
        try:
            decal = Decal(entity, brushDict, matSizes, matData["vmts"], scale=scale)
            sideIds = [side.id for side, _ in decal.faces]
            zOffset = getOverlapOffset(sideIds, decal.origin, decal.half_w, decal.half_h) * 0.125
            patches = decal.to_patches(zOffset=zOffset)
            for patch in patches:
                world.geo.append(patch)
        except Exception as e:
            progress.log(f"Failed to convert decal {entity['id'] if 'id' in entity else '?'}: {e}")

    # add corners for minimap and create a minimap material in gdt
    if game != "CoD2":
        minimapData, x, y, br_x, br_y = exportMinimap(mapName, gamePath, game, outDir)
        if minimapData is not None:
            if not skipMats:
                gdtFile += minimapData

            # make the z axis of minimap_corner entities the average of min.z/max.z
            z = (AABBmin.z + AABBmax.z) / 2

            # top left
            tl = vec3(x, y, z) * scale
            # bottom right
            br = vec3(br_x, br_y, z) * scale

            res.entities.append(cod.Entity({
                "classname": "script_origin",
                "origin": f"{Vec2Str(tl)}",
                "targetname": "minimap_corner",
                "_color": "1.0 0.6470588 0.0"
            }))

            res.entities.append(cod.Entity({
                "classname": "script_origin",
                "origin": f"{Vec2Str(br)}",
                "targetname": "minimap_corner",
                "_color": "1.0 0.6470588 0.0"
            }))

    # convert the skybox textures
    if not skipMats and mapData["sky"] != "sky":
        skyData = exportSkybox(mapData["sky"], mapName, worldSpawnSettings, gamePath, game, outDir)
        gdtFile += skyData
        if game != "BO3":
            batFile += skyData.toBat()


    # write the gdt & bat files
    progress.log("Moving all converted assets to output directory...")
    progress.overall(11, 13)
    with open(f"{outDir}/source_data/_{mapName}.gdt", "w") as f:
        f.write(gdtFile.toStr())
    if game != "BO3":
        with open(f"{outDir}/bin/_convert_{mapName}_assets.bat", "w", encoding="utf-8") as f:
            f.write(gdtFile.toBat())

    if game == "BO3":
        res.flags.append('"script_startingnumber" 0\n')
        res.flags.append('"000_Global" flags expanded  active\n')
        res.flags.append('"000_Global/No Comp" flags hidden ignore \n')
        res.flags.append('"The Map" flags expanded \n')

        world.properties.update({
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
        })

    else:
        world.properties.update(worldSpawnSettings)
    
    progress.log("Writing map file...")
    progress.overall(12, 13)
    res.Save(file)
    progress.overall(13, 13)
