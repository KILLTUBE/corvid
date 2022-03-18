from typing import Dict, List
from modules.Brush import Brush
from .Decal import *
from modules.Overlay import Overlay
from modules.SourceDir import SourceDir
from modules.AABB import AABB
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

def convertSide(side: Side, matSize, origin=Vector3(0, 0, 0), scale=1):
    # skip invalid sides
    if len(side.points) < 3:
        print(f"Brush face {side.id} has less than 3 vertices. Skipping...")
        return ""

    res = f"// Side {side.id}\n"
    points = side.points

    material = newPath(side.material)

    # get uv points
    if material not in matSize:
        matSize[material] = Vector2(512, 512)
        
    # get the uv of each point
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

def convertDisplacement(side: Side, matSize, origin=Vector3(0, 0, 0), scale=1, game="WaW"):
    res = f"// Side {side.id}\n"
    points = side.points
    material = newPath(side.material)
    
    if material not in matSize:
        matSize[material] = Vector2(512, 512)

    # get the uv of each point
    for point in side.points:
        side.uvs.append(side.getUV(point, matSize[material]))
        uvs: list[Vector2] = side.uvs

    if len(points) != 4:
        print(f"Displacement has {len(points)} points. Displacements can have 4 points only. Side id: {side.id}\n")
        for point in points:
            print(point)
        return ""
    
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

    # CoD 4  and CoD 2 can't handle terrain patches bigger than 16x16
    # So when we're converting a map for that game, we're going to slice them into 9x9 patches
    if (game == "CoD4" or game == "CoD2") and numVerts == 17:
        for k in range(2):
            for l in range(2):
                res += (
                    "{\n" +
                    "mesh\n" +
                    "{\n" +
                    "" + material + "\n" +
                    "lightmap_gray\n"
                    "9 9 " + str(side.lightmapScale) + " 8\n"
                )
                for i in range(k * 8, k * 8 + 9):
                    row = rows[i]
                    res += "(\n"
                    for j in range(l * 8, l * 8 + 9):
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

        for k in range(2):
            for l in range(2):
                res += (
                    "{\n" +
                    "mesh\n" +
                    "{\n" +
                    "" + material + "\n" +
                    "lightmap_gray\n"
                    "9 9 " + str(side.lightmapScale) + " 8\n"
                )
                for i in range(k * 8, k * 8 + 9):
                    row = rows[i]
                    res += "(\n"
                    for j in range(l * 8, l * 8 + 9):
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

    else:
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
            "" + material + "_blend\n" +
            "lightmap_gray\n" +
            "" + str(len(rows[0])) + " " + str(len(rows[0])
                                                ) + " " + str(side.lightmapScale) + " 8\n"
        )

        for i in range(numVerts):
            row = rows[i]
            res += "(\n"
            for j in range(numVerts):
                col = row[j]
                pos = (
                    col["pos"] + Vector3(0, 0, disp["elevation"]) +
                    (disp["row"][j]["normals"][i] * disp["row"][j]["distances"][i])
                )

                if game == "WaW": # move the blended patch away from the other one to avoid techset errors
                    normal = side.normal().normalize()
                    offset = normal * 0.1
                    pos = pos + offset

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

def convertBrush(brush: Brush, world=True, game="WaW", mapName="", origin=Vector3(0, 0, 0), scale=1, matSizes: dict={}, brushConversion=False, sideDict: dict={}, AABBmin: Vector3=Vector3.Zero(), AABBmax: Vector3=Vector3.Zero()):
    tools = {
        "toolsnodraw": "caulk",
        "toolsclip": "clip",
        "toolsplayerclip": "clip",
        "toolsinvisible": "clip",
        "toolsinvisibleladder": "ladder",
        "toolsnpcclip": "clip",
        "toolsgrenadeclip": "clip_missile",
        "toolsareaportal": "portal_nodraw",
        "toolsblocklight": "shadowcaster",
        "toolshint": "hint",
        "toolsskip": "skip",
        "toolstrigger": "trigger",
        "toolsskybox": "sky" if game == "BO3" else f"{mapName}_sky"
    }

    if game == "BO3" and brush.entity == "func_areaportal":
        return ""
    elif brush.entity == "func_brush":
        if "targetname" in brush.entData and brush.entData["targetname"].startswith("retake"):
            return ""
    elif brush.entity == "func_dustmotes" or brush.entity == "func_buyzone" or brush.entity.startswith("trigger"):
        return ""
    elif brush.sides[0].material == "tools/toolstrigger":
        return ""

    resBrush = f"// Brush {brush.id}\n" 
    resBrush += "{\n"

    if not world:
        if brush.entity == "func_detail" or brush.entity == "func_breakable":
            resBrush += "contents detail;\n"
        elif brush.entity == "func_illusionary":
            resBrush += "contents nonColliding;\n"

    resPatch = ""
    
    for side in brush.sides:
        if side.material == "tools/toolsskybox":
            if brush.isToolBrush:
                return ""
            else:
                side.material = "tools/toolsnodraw"
        
        if game == "BO3":
            if side.material in ["tools/toolsareaportal", "tools/toolshint", "tools/toolsskip"]:
                return ""
        
        for point in side.points.copy():
            point = (point - origin) * scale
            AABBmax.set(AABBmax.max(point))
            AABBmin.set(AABBmin.min(point))
        
        if len(side.points) >= 3:
            sideDict[side.id] = side

        if side.hasDisp:
            resPatch += convertDisplacement(side, matSizes, origin, scale, game)
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
        
        elif brushConversion:
            mat = newPath(side.material)
            side.texSize = matSizes.get(mat, Vector2(512, 512))
            tex = side.getTexCoords()
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

def convertLight(entity, scale=1.0):
    if "_light" in entity:
        _color = [int(i) for i in entity["_light"].split(" ")]
        if len(_color) == 3:
            _color.append(300)
    else:
        _color = [0, 0, 0, 300]
    # In Radiant, color value of light entities range between 0 and 1 whereas it varies between 0 and 255 in Source engine
    color = (Vector3(_color[0], _color[1], _color[2]) / 255).round(3)
    return convertEntity({
        "classname": "light",
        "origin": Vector3.FromStr(entity["origin"]) * scale,
        "_color": color,
        "radius": _color[3] if _color[3] > 100 else 300,
        "intensity": "1"
    }, entity["id"])

def convertSpotLight(entity, game="WaW", scale=1.0):
    if "_light" in entity:
        _color = [i for i in entity["_light"].split(" ") if i != ""]
        if len(_color) == 3:
            _color.append(500)
    else:
        _color = [0, 0, 0, 500]
    # In Radiant, color value of light entities range between 0 and 1 whereas it varies between 0 and 255 in Source engine
    color = (Vector3(_color[0], _color[1], _color[2]) / 255).round(3)
    origin = Vector3.FromStr(entity["origin"])
    if "_fifty_percent_distance" in entity and "_zero_percent_distance" not in entity:
        radius = int(entity["_fifty_percent_distance"])
    elif "_zero_percent_distance" in entity and "_fifty_percent_distance" not in entity:
        radius = int(entity["_zero_percent_distance"])
    elif "_fifty_percent_distance" in entity and "_zero_percent_distance" in entity:
        radius = (int(entity["_fifty_percent_distance"]) * 2 + int(entity["_zero_percent_distance"])) / 2
    else:
        radius = 250
    
    if game != "BO3":
        res = convertEntity({
            "classname": "light",
            "origin": origin * scale,
            "_color": color,
            "radius": radius,
            "intensity": "1",
            "target": "spotlight_" + entity["id"],
            "fov_outer": entity["_cone"],
            "fov_inner": entity["_inner_cone"],
        }, entity["id"])
        res += convertEntity({
            "classname": "info_null",
            "origin": (origin + Vector3(0, 0, -70)) * scale,
            "targetname": "spotlight_" + entity["id"]
        })
    else:
        angles = Vector3.FromStr(entity["angles"])
        pitch = float(entity["pitch"])
        res = convertEntity({
            "classname": "light",
            "origin": origin * scale,
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
            if "targetname" in entity:
                ropeDict["end"][entity["targetname"]] = {
                    "origin": (Vector3.FromStr(entity["origin"]) - skyOrigin) * scale,
                    "targetname": entity["targetname"],
                    "id": entity["id"]
                }
    
            if "NextKey" in entity and "target" in entity:
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

def convertRopeAsCurve(start: Vector3, end: Vector3, slack: float, width: float=1, game="WaW"):
    mid: Vector3 = start.lerp(end, 0.5)
    mid.z -= slack * 0.75

    # calculate the forward, left and right vectors so all the ropes will be consistent in size
    up = Vector3.Up()

    # sometimes, the length of (end - start) returns 0, which makes it impossible to normalize it
    dif = end - start
    if dif.len() == 0:
        forward = Vector3.Zero()
    else:
        forward = dif.normalize()

    right = forward.cross(up)
    left = right * -1

    # multiply each value with the half of the width value to get proper thickness
    width *= 0.5
    up *= width
    left *= width
    right *= width
    top = left.lerp(right, 0.5) + up
    bottom = left.lerp(right, 0.5) - up
    topLeft = top.lerp(left, 0.5) + up
    bottomLeft = bottom.lerp(left, 0.5) - up
    topRight = top.lerp(right, 0.5) + up
    bottomRight = bottom.lerp(right, 0.5) - up

    if game == "WaW":
        mat = "global_wires"
    elif game == "CoD4":
        mat = "ap_chrome_trim"
    elif game == "CoD2":
        mat = "egypt_metal_pipe2"
    
    return (
        "{\n"
        + "curve\n"
        + "{\n"
        + "contents nonColliding;\n"
        + f"{mat}\n"
        + "lightmap_gray\n"
        + "9 3 16 8\n"
        + "(\n"
        + f"v {start + bottom} t 1 1 1 1\n"
        + f"v {mid + bottom} t 1 1 1 25\n"
        + f"v {end + bottom} t 1 1 1 25\n"
        + ")\n"
        + "(\n"
        + f"v {start + bottomLeft} t 1 1 3 1\n"
        + f"v {mid + bottomLeft} t 1 1 3 25\n"
        + f"v {end + bottomLeft} t 1 1 3 25\n"
        + ")\n"
        + "(\n"
        + f"v {start + left} t 1 1 3 1\n"
        + f"v {mid + left} t 1 1 3 25\n"
        + f"v {end + left} t 1 1 3 25\n"
        + ")\n"
        + "(\n"
        + f"v {start + topLeft} t 1 1 5 1\n"
        + f"v {mid + topLeft} t 1 1 5 25\n"
        + f"v {end + topLeft} t 1 1 5 25\n"
        + ")\n"
        + "(\n"
        + f"v {start + top} t 1 1 5 1\n"
        + f"v {mid + top} t 1 1 5 25\n"
        + f"v {end + top} t 1 1 5 25\n"
        + ")\n"
        + "(\n"
        + f"v {start + topRight} t 1 1 5 1\n"
        + f"v {mid + topRight} t 1 1 5 25\n"
        + f"v {end + topRight} t 1 1 5 25\n"
        + ")\n"
        + "(\n"
        + f"v {start + right} t 1 1 7 1\n"
        + f"v {mid + right} t 1 1 7 25\n"
        + f"v {end + right} t 1 1 7 25\n"
        + ")\n"
        + "(\n"
        + f"v {start + bottomRight} t 1 1 5 1\n"
        + f"v {mid + bottomRight} t 1 1 5 25\n"
        + f"v {end + bottomRight} t 1 1 5 25\n"
        + ")\n"
        + "(\n"
        + f"v {start + bottom} t 1 1 9 1\n"
        + f"v {mid + bottom} t 1 1 9 25\n"
        + f"v {end + bottom} t 1 1 9 25\n"
        + ")\n"
        + "}\n"
        + "}\n"
    )

def convertProp(entity, game="WaW", skyOrigin=Vector3(0, 0, 0), scale=1, mdlScale=1):
    origin = (Vector3.FromStr(entity["origin"]) - skyOrigin) * scale
    modelScale = float(entity["uniformscale"] if "uniformscale" in entity else entity["modelscale"] if "modelscale" in entity else "1") * mdlScale

    if "model" not in entity:
        return convertEntity({
            "classname": "info_null",
            "original_classname": entity["classname"],
            "origin": origin
        }, entity["id"])

    modelName = "m_" + splitext(newPath(entity["model"]))[0]

    if "skin" in entity:
        if entity["skin"] != "0":
            modelName += f'_skin{entity["skin"]}'

    if game == "BO3" and "rendercolor" in entity:
        if entity["rendercolor"] != "255 255 255":
            modelName += "_" + Vector3.FromStr(entity["rendercolor"]).toHex()

    if game == "CoD2":
        modelName = "xmodel/" + modelName

    return convertEntity({
        "classname": "dyn_model" if entity["classname"].startswith("prop_physics") and game != "CoD2" else "misc_model",
        "model": modelName,
        "origin": origin,
        "angles": entity["angles"],
        "spawnflags": "16" if entity["classname"].startswith("prop_physics") else "",
        "modelscale": modelScale
    }, entity["id"])

def convertCubemap(entity, scale=1.0):
    return convertEntity({
        "classname": "reflection_probe",
        "origin": Vector3.FromStr(entity["origin"]) * scale
    }, entity["id"])

def convertSpawner(entity, scale=1.0):
    origin = Vector3.FromStr(entity["origin"]) * scale

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
        return ""

    res = convertEntity({
        "classname": classname,
        "origin": origin,
        "angles": entity["angles"]
    }, entity["id"])

    if classname == "info_player_start":
        res += convertEntity({
            "classname": "mp_global_intermission",
            "origin": origin
        })

        res += convertEntity({
            "classname": "mp_tdm_spawn",
            "origin": origin
        })
    
    # make sure to add spawners for sd too
    if classname == "mp_tdm_spawn_axis_start" or classname == "mp_tdm_spawn_allies_start":
        res += convertEntity({
            "classname": "mp_sd_spawn_attacker" if classname == "mp_tdm_spawn_axis_start" else "mp_sd_spawn_defender",
            "origin": origin,
            "angles": entity["angles"]
        })

    return res

def convertBombsite(entity, scale=1, game="WaW", site=""):
    solids = entity["solids"] if "solids" in entity else [entity["solid"]]
    brushes: List[Brush] = []

    # calculate the geo of the trigger(s)
    for solid in solids:
        sides: List[Side] = []
        for side in solid["sides"]:
            sides.append(Side(side))
        brushes.append(Brush(sides))
    
    # get the center of the trigger(s) to decide where to place the bomb model
    center = Vector3.Zero()
    lowest = None
    for brush in brushes:
        for side in brush.sides:
            if lowest is not None:
                lowest = min(lowest, side.center().z)
            center = center + side.center()
    
    center = center / sum([len(brush.sides) for brush in brushes])
    if lowest is not None:
        center.z = lowest # make sure the model is always at the bottom of the trigger
    bombsite = "_" + (entity["targetname"][0].lower() if "targetname" in entity else site)

    res = convertEntity({
        "classname": "trigger_use_touch",
        "script_bombmode_original": "1",
        "target": "target" + bombsite,
        "script_gameobjectname": "bombzone",
        "targetname": "bombzone",
        "script_label": bombsite
    }, geo="".join(convertBrush(brush, scale=scale) for brush in brushes))

    res += convertEntity({
        "targetname": "targetname" + bombsite,
        "classname": "trigger_use_touch",
        "script_gameobjectname": "bombzone"
    }, geo="".join(convertBrush(brush, scale=scale) for brush in brushes))

    res += convertEntity({
        "target": "targetname" + bombsite,
        "targetname": "target" + bombsite,
        "spawnflags": "4",
        "script_gameobjectname": "bombzone",
        "script_exploder": "1",
        "origin": center * scale,
        "model": "xmodel/tag_origin" if game=="CoD2" else "tag_origin",
        "classname": "script_model"
    })

    res += convertEntity({
        "classname": "script_model",
        "model": "xmodel/tag_origin" if game=="CoD2" else "tag_origin",
        "origin": center * scale,
        "spawnflags": "4",
        "targetname": "exploder",
        "script_exploder": "1"
    })

    return res

# in CoD, it is better to seal the whole map in 6 skybox brushes
# in Source however, there are always too many skybox brushes, which is not ideal for CoD
# this function basically takes the two far ends of the map and then uses those positions to create 6 skybox brushes with them
def createSkyBrushes(AABBmin: Vector3, AABBmax: Vector3, mapName="", game="WaW"):
    if AABBmin == AABBmax:
        return ""
    
    # move the points further to avoid collision with map geo
    AABBmax += Vector3(250, 250, 500)
    AABBmin += Vector3(-250, -250, -100)

    top1 = AABBmax # top points
    top2 = Vector3(AABBmax.x, AABBmin.y, AABBmax.z)
    top3 = Vector3(AABBmin.x, AABBmax.y, AABBmax.z)
    top4 = Vector3(AABBmin.x, AABBmin.y, AABBmax.z)
    bot1 = AABBmin # bottom points
    bot2 = Vector3(AABBmin.x, AABBmax.y, AABBmin.z)
    bot3 = Vector3(AABBmax.x, AABBmin.y, AABBmin.z)
    bot4 = Vector3(AABBmax.x, AABBmax.y, AABBmin.z)

    sky = ""
    if game == "BO3":
        inner = "sky 128 128 0 0 0 0 lightmap_gray 16384 16384 0 0 0 0"
        outer = "sky 128 128 0 0 0 0 lightmap_gray 16384 16384 0 0 0 0"
    else:
        inner = mapName + "_sky 128 128 0 0 0 0 lightmap_gray 16384 16384 0 0 0 0"
        outer = "caulk 128 128 0 0 0 0 lightmap_gray 16384 16384 0 0 0 0"

    up, right, forward = Vector3.Up() * 64, Vector3.Right() * 64, Vector3.Forward() * 64

    # sky brushes
    # top brush
    sky += (
        "{\n"
        f"( {top1 + up} ) ( {top2 + up} ) ( {top3 + up} ) {outer}\n" # top
        f"( {top3} ) ( {top2} ) ( {top1} ) {inner}\n" # bottom
        f"( {top3} ) ( {top4} ) ( {bot1} ) {outer}\n" # back
        f"( {bot4} ) ( {top2} ) ( {top1} ) {outer}\n" # front
        f"( {top1} ) ( {top3} ) ( {bot2} ) {outer}\n" # left
        f"( {top4} ) ( {top2} ) ( {bot3} ) {outer}\n" # right
        "}\n"
    )

    # bottom
    sky += (
        "{\n"
        f"( {bot1} ) ( {bot2} ) ( {bot3} ) {inner}\n" # top
        f"( {bot3 - up} ) ( {bot2 - up} ) ( {bot1 - up} ) {outer}\n" # bottom
        f"( {top3} ) ( {top4} ) ( {bot1} ) {outer}\n" # back
        f"( {bot4} ) ( {top2} ) ( {top1} ) {outer}\n" # front
        f"( {top1} ) ( {top3} ) ( {bot2} ) {outer}\n" # left
        f"( {top4} ) ( {top2} ) ( {bot3} ) {outer}\n" # right
        "}\n"
    )

    # back
    sky += (
        "{\n"
        f"( {top1} ) ( {top2} ) ( {top3} ) {outer}\n" # top
        f"( {bot3} ) ( {bot2} ) ( {bot1} ) {outer}\n" # bottom
        f"( {bot1} ) ( {top4} ) ( {top3} ) {inner}\n" # back
        f"( {top3 - forward} ) ( {top4 - forward} ) ( {bot1 - forward} ) {outer}\n" # front
        f"( {top1} ) ( {top3} ) ( {bot2} ) {outer}\n" # left
        f"( {top4} ) ( {top2} ) ( {bot3} ) {outer}\n" # right
        "}\n"
    )

    # front
    sky += (
        "{\n"
        f"( {top1} ) ( {top2} ) ( {top3} ) {outer}\n" # top
        f"( {bot3} ) ( {bot2} ) ( {bot1} ) {outer}\n" # bottom
        f"( {bot4 + forward} ) ( {top2 + forward} ) ( {top1 + forward} ) {outer}\n" # back
        f"( {top1} ) ( {top2} ) ( {bot4} ) {inner}\n" # front
        f"( {top1} ) ( {top3} ) ( {bot2} ) {outer}\n" # left
        f"( {top4} ) ( {top2} ) ( {bot3} ) {outer}\n" # right
        "}\n"
    )

    # left
    sky += (
        "{\n"
        f"( {top1} ) ( {top2} ) ( {top3} ) {outer}\n" # top
        f"( {bot3} ) ( {bot2} ) ( {bot1} ) {outer}\n" # bottom
        f"( {top3} ) ( {top4} ) ( {bot1} ) {outer}\n" # back
        f"( {bot4} ) ( {top2} ) ( {top1} ) {outer}\n" # front
        f"( {top1 + right} ) ( {top3 + right} ) ( {bot2 + right} ) {outer}\n" # left
        f"( {bot2} ) ( {top3} ) ( {top1} ) {inner}\n" # right
        "}\n"
    )

    # right
    sky += (
        "{\n"
        f"( {top1} ) ( {top2} ) ( {top3} ) {outer}\n" # top
        f"( {bot3} ) ( {bot2} ) ( {bot1} ) {outer}\n" # bottom
        f"( {top3} ) ( {top4} ) ( {bot1} ) {outer}\n" # back
        f"( {bot4} ) ( {top2} ) ( {top1} ) {outer}\n" # front
        f"( {bot3} ) ( {top2} ) ( {top4} ) {inner}\n" # left
        f"( {top4 - right} ) ( {top2 - right} ) ( {bot3 - right} ) {outer}\n" # right
        "}\n"
    )

    # create sun, fps and umbra volumes for BO3 
    vol = ""
    if game == "BO3":
        suntex = "sun_volume 128 128 0 0 0 0 lightmap_gray 16384 16384 0 0 0 0"
        vol += convertEntity({
            "classname": "volume_sun",
            "ssi": f"{mapName}_ssi",
            "grid_density": "32",
            "shadowBiasScale": "1",
            "shadowSplitDistance": "2000",
            "ssi1": f"{mapName}_ssi",
            "streamLighting": "1"
        }, geo=(
            "{\n"
            f"( {top1} ) ( {top2} ) ( {top3} ) {suntex}\n" # top
            f"( {bot3} ) ( {bot2} ) ( {bot1} ) {suntex}\n" # bottom
            f"( {top3} ) ( {top4} ) ( {bot1} ) {suntex}\n" # back
            f"( {bot4} ) ( {top2} ) ( {top1} ) {suntex}\n" # front
            f"( {top1} ) ( {top3} ) ( {bot2} ) {suntex}\n" # left
            f"( {top4} ) ( {top2} ) ( {bot3} ) {suntex}\n" # right

            + "}\n"
        ))

        umbtex = "umbra_volume 128 128 0 0 0 0 lightmap_gray 16384 16384 0 0 0 0"
        vol += convertEntity({
            "classname": "umbra_volume",
        }, geo=(
            "{\n"
            f"( {top1} ) ( {top2} ) ( {top3} ) {umbtex}\n" # top
            f"( {bot3} ) ( {bot2} ) ( {bot1} ) {umbtex}\n" # bottom
            f"( {top3} ) ( {top4} ) ( {bot1} ) {umbtex}\n" # back
            f"( {bot4} ) ( {top2} ) ( {top1} ) {umbtex}\n" # front
            f"( {top1} ) ( {top3} ) ( {bot2} ) {umbtex}\n" # left
            f"( {top4} ) ( {top2} ) ( {bot3} ) {umbtex}\n" # right

            + "}\n"
        ))

        fpstex = "volume_fpstool 128 128 0 0 0 0 lightmap_gray 16384 16384 0 0 0 0"
        vol += convertEntity({
            "classname": "volume_fpstool",
        }, geo=(
            "{\n"
            f"( {top1} ) ( {top2} ) ( {top3} ) {fpstex}\n" # top
            f"( {bot3} ) ( {bot2} ) ( {bot1} ) {fpstex}\n" # bottom
            f"( {top3} ) ( {top4} ) ( {bot1} ) {fpstex}\n" # back
            f"( {bot4} ) ( {top2} ) ( {top1} ) {fpstex}\n" # front
            f"( {top1} ) ( {top3} ) ( {bot2} ) {fpstex}\n" # left
            f"( {top4} ) ( {top2} ) ( {bot3} ) {fpstex}\n" # right

            + "}\n"
        ))

    return sky, vol

def exportMap(
        vmfString, vpkFiles=[], gameDirs=[], game="WaW",
        skipMats=False, skipModels=False, mapName="",
        brushConversion=False, scale=1.0
    ):
    # create temporary directories to extract assets
    copyDir = gettempdir() + "/corvid"

    if not exists(f"{copyDir}"):
        try:
            makedirs(f"{copyDir}/mdl")
            makedirs(f"{copyDir}/mat")
            makedirs(f"{copyDir}/mdlMats")
            makedirs(f"{copyDir}/matTex")
            makedirs(f"{copyDir}/mdlTex")
            if game != "BO3":
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
        mdlMaterials = copyModelMaterials(mapData["models"], gamePath, mapData["modelTints"], game)
        mdlMatData = copyTextures(mdlMaterials, gamePath, True)

    # create GDT files
    gdtFile = Gdt()

    # CoD 2 needs different arguments for converter, so we need to make the GDT class we're converting for CoD 2
    if game == "CoD2":
        gdtFile.CoD2 = True
        gdtFile.name = mapName

    batFile = ""
    if not skipMats or not skipModels:
        print("Generating GDT file...")
    if not skipMats:
        worldMats = createMaterialGdt(matData["vmts"], game)
        gdtFile += worldMats
    if game != "BO3" and not skipMats:
        batFile += worldMats.toBat()
    if not skipModels:
        modelMats = createMaterialGdt(mdlMatData["vmts"], game)
        gdtFile += modelMats
    if game != "BO3" and not skipModels:
        batFile += modelMats.toBat()
    if not skipModels:
        models = createModelGdt(mapData["models"], game, mapData["modelTints"], mapData["modelSkins"])
        gdtFile += models
    if game != "BO3" and not skipModels:
        batFile += models.toBat()
    # create GDT files for images for Bo3
    if game == "BO3":
        if not skipMats:
            gdtFile += createImageGdt(matData)
        if not skipModels:
            gdtFile += createImageGdt(mdlMatData)

    # convert the textures
    if not skipMats:
        print("Converting textures...")
        convertImages(matData, "matTex", "texture_assets/corvid", "tif" if game == "BO3" else "tga")
        if not skipModels:
            convertImages(mdlMatData, "mdlTex", "texture_assets/corvid", "tif" if game == "BO3" else "tga")

    # convert the models
    if not skipModels:
        print("Converting models...")
        convertModels(mapData["models"], mapData["modelTints"], mapData["modelSkins"], game, scale)

    # generate map geometry
    print("Generating .map file...")
    mapGeo = ""
    mapEnts = ""
    worldSpawnSettings = {}

    # store the furthest points for each axis to calculate the bounding box of the whole map
    AABBmin = Vector3.Zero()
    AABBmax = Vector3.Zero()

    # store brush sides in a dictionary for info_overlay entities
    sideDict: Dict[str, Side] = {}
    
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
        print(f"{i}|{total}|done", end="")
        mapGeo += convertBrush(brush, True, game, mapName, matSizes=matSizes, brushConversion=brushConversion, sideDict=sideDict, scale=scale, AABBmin=AABBmin, AABBmax=AABBmax)
        if not brush.isToolBrush and not brush.hasDisp:
            brushDict[brush.id] = brush

    for i, brush in enumerate(mapData["entityBrushes"], lenWorld):
        print(f"{i}|{total}|done", end="")
        mapGeo += convertBrush(brush, False, game, mapName, matSizes=matSizes, sideDict=sideDict, scale=scale, AABBmin=AABBmin, AABBmax=AABBmax)
        if not brush.isToolBrush and not brush.hasDisp:
            brushDict[brush.id] = brush

    for i, entity in enumerate(mapData["entities"], lenWorld + lenEntBrushes):
        if "origin" in entity:
            origin = Vector3.FromStr(entity["origin"]) * scale
            AABBmax.set(AABBmax.max(origin))
            AABBmin.set(AABBmin.min(origin))
        print(f"{i}|{total}|done", end="")
        if entity["classname"].startswith("prop_"):
            mapEnts += convertProp(entity, game, scale=scale)
        elif entity["classname"] == "light":
            mapEnts += convertLight(entity, scale=scale)
        elif entity["classname"] == "light_spot":
            mapEnts += convertSpotLight(entity, game, scale=scale)
        elif entity["classname"] == "move_rope" or entity["classname"] == "keyframe_rope":
            if game == "CoD4" or game == "CoD2":
                convertRope(entity, curve=True, ropeDict=ropeDict, scale=scale)
            else:
                mapEnts += convertRope(entity)
        elif entity["classname"] == "env_cubemap" and game != "CoD2":
            mapEnts += convertCubemap(entity, scale=scale)
        elif entity["classname"].startswith("info_player") or entity["classname"].endswith("_spawn"):
            mapEnts += convertSpawner(entity, scale=scale)
        # elif entity["classname"] == "info_overlay":
        #     if entity["sides"] != "":
        #         overlays.append(entity)
        # elif entity["classname"] == "infodecal":
        #     decals.append(entity)
        elif entity["classname"] == "func_bomb_target":
            mapEnts += convertBombsite(entity, scale=scale, game=game, site=bombsites[currentBombsite])
            currentBombsite += 1
        elif entity["classname"] == "light_environment":
            sundirection = Vector3.FromStr(entity["angles"])
            sundirection.x = float(entity["pitch"])
            sundirection.y = sundirection.y - 180 if sundirection.y >= 180 else sundirection.y + 180
            worldSpawnSettings["sundirection"] = sundirection
            worldSpawnSettings["sunlight"] = "1"
            worldSpawnSettings["sundiffusecolor"] = "0.75 0.82 0.85"
            worldSpawnSettings["diffusefraction"] = ".2"
            worldSpawnSettings["ambient"] = ".116"
            worldSpawnSettings["reflection_ignore_portals"] = "1"
            if "ambient" in entity:
                worldSpawnSettings["_color"] = (Vector3.FromStr(entity["_ambient"] if "_ambient" in entity else entity["ambient"]) / 255).round(3)
            if "_light" in entity:
                worldSpawnSettings["suncolor"] = (Vector3.FromStr(entity["_light"]) / 255).round(3)
            
    # convert 3d skybox geo & entities
    for i, brush in enumerate(mapData["skyBrushes"], lenWorld + lenEntBrushes + lenEnts):
        print(f"{i}|{total}|done", end="")
        mapGeo += convertBrush(brush, True, game, mapName, origin=mapData["skyBoxOrigin"], scale=scale * mapData["skyBoxScale"], sideDict=sideDict, AABBmin=AABBmin, AABBmax=AABBmax)

    for i, brush in enumerate(mapData["skyEntityBrushes"], lenWorld + lenEntBrushes + lenEnts + lenSky):
        print(f"{i}|{total}|done", end="")
        mapGeo += convertBrush(brush, False, game, mapName, origin=mapData["skyBoxOrigin"], scale=scale * mapData["skyBoxScale"], sideDict=sideDict, AABBmin=AABBmin, AABBmax=AABBmax)

    for i, entity in enumerate(mapData["skyEntities"], lenWorld + lenEntBrushes + lenEnts + lenSky + lenSkyEntBrushes):
        print(f"{i}|{total}|done", end="")

        origin = (Vector3.FromStr(entity["origin"]) - mapData["skyBoxOrigin"]) * mapData["skyBoxScale"] * scale
        AABBmax.set(AABBmax.max(origin))
        AABBmin.set(AABBmin.min(origin))

        if entity["classname"].startswith("prop_"):
            mapEnts += convertProp(entity, game, mapData["skyBoxOrigin"], mdlScale=mapData["skyBoxScale"], scale=scale * mapData["skyBoxScale"])
        elif entity["classname"] == "move_rope" or entity["classname"] == "keyframe_rope":
            if game == "CoD4":
                convertRope(entity, skyOrigin=mapData["skyBoxOrigin"], scale=scale * mapData["skyBoxScale"], curve=True, ropeDict=ropeDict)
            else:
                mapEnts += convertRope(entity, skyOrigin=mapData["skyBoxOrigin"], scale=scale * mapData["skyBoxScale"])

    # convert ropes to curve patches for cod 4
    if game == "CoD4" or game == "CoD2":
        for val in ropeDict["start"].values(): 
            if val["target"] in ropeDict["end"]:
                mapGeo += convertRopeAsCurve(
                    val["origin"],
                    ropeDict["end"][val["target"]]["origin"],
                    val["slack"],
                    val["width"],
                    game
                )

    # create sky brushes and other necessary stuff
    skyBrushes, volumes = createSkyBrushes(AABBmin, AABBmax, mapName, game)
    mapGeo += skyBrushes
    mapEnts += volumes

    # convert overlays
    # i = 0
    # total = len(overlays)
    # print("Converting decals...")
    # for overlay in overlays:
    #     i += 1
    #     print(f"{i}|{total}|done", end="")
    #     decal = Overlay(overlay, sideDict, matSizes)
    #     if decal is not None:
    #         mapGeo += str(decal)
    #     del decal

    # for decal in decals:
    #     convertDecal(entity, sideDict)

    # create an octree to check for brushes colliding with infodecal entities
    # octree = AABB(AABBmin, AABBmax, True)
        
    # iterate over brushes, add them to the octree
    # for brush in brushDict.values():
    #     AddBrusesToOctree(octree, brush)

    # add corners for minimap and create a minimap material in gdt
    if game != "CoD2":
        minimapData, x, y = exportMinimap(mapName, gamePath, game)
        if minimapData is not None:
            if not skipMats:
                gdtFile += minimapData

            # make the z axis of minimap_corner entities the average of min.z/max.z
            z = (AABBmin.z + AABBmax.z) / 2

            # top left
            origin = Vector3(x, y, z) * scale

            mapEnts += convertEntity({
                "classname": "script_origin",
                "origin": f"{origin}",
                "targetname": "minimap_corner",
                "_color": "1.0 0.6470588 0.0"
            })

            # bottom right
            mapEnts += convertEntity({
                "classname": "script_origin",
                "origin": f"{origin.y} {origin.x} {z}",
                "targetname": "minimap_corner",
                "_color": "1.0 0.6470588 0.0"
            })

    # convert the skybox textures
    if not skipMats and mapData["sky"] != "sky":
        skyData = exportSkybox(mapData["sky"], mapName, worldSpawnSettings, gamePath, game)
        gdtFile += skyData
        if game != "BO3":
            batFile += skyData.toBat()


    # write the gdt & bat files
    open(f"{copyDir}/converted/source_data/_{mapName}.gdt", "w").write(gdtFile.toStr())
    if game != "BO3":
        open(f"{copyDir}/converted/bin/_convert_{mapName}_assets.bat", "w").write(gdtFile.toBat())

    if game == "BO3":
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
