import os
os.environ["NO_BPY"] = "1"
from PIL import Image
from SourceIO.source1.vtf.VTFWrapper import VTFLib
from modules.Vector3 import Vector3
from modules.Vector2 import Vector2
from modules.cube2equi import find_corresponding_pixel
from modules.vdfutils import parse_vdf
from os.path import basename, splitext, dirname, exists
from os import listdir
from .Static import fixVmt, newPath
from .Gdt import Gdt
from tempfile import gettempdir
from .AssetConverter import getTexSize, convertImage
from SourceIO.source1.mdl.mdl_file import Mdl
from pathlib import Path
from .SourceDir import SourceDir

tempDir = f"{gettempdir()}/corvid"

def copyMaterials(mats, dir: SourceDir, mapname=""):
    res = []
    total = len(mats)
    for i, mat in enumerate(mats):
        print(f"{i}|{total}|done", end="")
        name = newPath(mat, prefix=mapname)
        dir.copy(f"materials/{mat}.vmt", f"{tempDir}/mat/{name}.vmt")
        res.append(name)
    return res

def copyTextures(mats, dir: SourceDir, mdl=False, mapname=""):
    res = {
        "sizes": {}, # save the dimensions of $basetexture
        "colorMaps": [],
        "colorMapsAlpha": [],
        "envMaps": [],
        "envMapsAlpha": [],
        "normalMaps": [],
        "revealMaps": [],
        "vmts": {} # save vmt data to create GDT's later
    }
    if not mdl:
        vmtDir, vtfDir = "mat", "matTex"
    else:
        vmtDir, vtfDir = "mdlMats", "mdlTex"
    total = len(mats)
    for i, file in enumerate(mats):
        print(f"{i}|{total}|done", end="")
        fileName = basename(file)
        vmtPath = f"{tempDir}/{vmtDir}/{fileName}.vmt"
        if not exists(vmtPath):
            print(f"Could not find material {fileName}. Creating an empty material for it...")
            res["vmts"][fileName] = parse_vdf('lightmappedgeneric\n{\n"$basetexture" "404"\n}')
            res["sizes"][file.strip()] = Vector2(512, 512)
            return res

        try:
            vmt = parse_vdf(fixVmt(open(vmtPath).read()))
            res["vmts"][fileName] = vmt
            shader = list(vmt)[0]
            mat = vmt[shader]
        except:
            print(f"Could not parse {vmtPath}. Skipping...")

        # some materials in Source can reference & inherit other materials' properties
        if "include" in mat:
            includeFile = mat["include"]
            if not includeFile.startswith("materials"):
                includeFile = "materials/" + includeFile
            if not includeFile.endswith(".vmt"):
                includeFile += ".vmt"
            includeFile = Path(includeFile).as_posix().lower().strip()
            if dir.copy(includeFile, f"{tempDir}/{vmtDir}/{newPath(includeFile, prefix=mapname)}"):
                try:
                    includeVmt = parse_vdf(fixVmt(open(f"{tempDir}/{vmtDir}/{newPath(includeFile, prefix=mapname)}").read()))
                    patch = list(includeVmt)[0]
                    includeMat = includeVmt[patch]
                    mat = {**includeMat, **mat}
                except:
                    pass
                else:
                    res["vmts"][fileName][shader] = mat
    
        if "insert" in mat:
            mat = {**mat, **mat["insert"]}
            res["vmts"][fileName][shader] = mat
            pass

        if "$basetexture" in mat:
            baseTexture = mat["$basetexture"].strip()
            name = newPath(splitext(baseTexture)[0], True, prefix=mapname)
            dir.copy(f"materials/{baseTexture}.vtf", f"{tempDir}/{vtfDir}/{name}.vtf")
        if not mdl: # we don't need to get the dimensions of model textures
            if "$basetexture" in mat:
                res["sizes"][file.strip()] = getTexSize(f"{tempDir}/{vtfDir}/{name}.vtf")
            else:
                res["sizes"][file.strip()] = Vector2(512, 512)
        if "$basetexture" in mat:
            if "$translucent" in mat or "$alpha" in mat or "$alphatest" in mat:
                res["colorMapsAlpha"].append(name)
            elif "$blendtintbybasealpha" in mat or "$blendtintcoloroverbase" in mat:
                res["colorMapsAlpha"].append(name)
            else:
                res["colorMaps"].append(name)
        if "$bumpmap" in mat:
            bumpMap = mat["$bumpmap"].strip()
            name: str = newPath(splitext(bumpMap)[0], True, prefix=mapname)
            dir.copy(f"materials/{bumpMap}.vtf", f"{tempDir}/{vtfDir}/{name}.vtf")
            res["normalMaps"].append(name)
        if "$envmapmask" in mat:
            envMap: str = mat["$envmapmask"].strip()
            name = splitext(newPath(envMap, True, prefix=mapname))[0]
            dir.copy(f"materials/{envMap}.vtf", f"{tempDir}/{vtfDir}/{name}.vtf")
            res["envMaps"].append(name)
        if "$blendmodulatetexture" in mat:
            revealMap: str = mat["$blendmodulatetexture"].strip()
            name = newPath(splitext(revealMap)[0], True, prefix=mapname)
            dir.copy(f"materials/{revealMap}.vtf", f"{tempDir}/{vtfDir}/{name}.vtf")
            res["revealMaps"].append(name)
        if "$basetexture2" in mat:
            basetexture2 = mat["$basetexture2"].strip()
            name: str = newPath(splitext(basetexture2)[0], True, prefix=mapname)
            dir.copy(f"materials/{basetexture2}.vtf", f"{tempDir}/{vtfDir}/{name}.vtf")
            res["colorMaps"].append(name)
            res["sizes"][file.strip() + "_"] = getTexSize(f"{tempDir}/{vtfDir}/{name}.vtf")
        if "$bumpmap2" in mat:
            bumpMap2 = mat["$bumpmap2"].strip()
            name: str = newPath(splitext(bumpMap2)[0], True, prefix=mapname)
            dir.copy(f"materials/{bumpMap2}.vtf", f"{tempDir}/{vtfDir}/{name}.vtf")
            res["normalMaps"].append(name)
        if "$envmapmask2" in mat:
            envMap2: str = mat["$envmapmask2"].strip()
            name = newPath(splitext(envMap2)[0], True, prefix=mapname)
            dir.copy(f"materials/{envMap2}.vtf", f"{tempDir}/{vtfDir}/{name}.vtf")
            res["envMaps"].append(name)
        if "$basealphaenvmapmask" in mat:
            res["envMapsAlpha"].append(newPath(splitext(mat["$basetexture"])[0], True, prefix=mapname))
        if "$basealphaenvmapmask2" in mat:
            res["envMapsAlpha"].append(newPath(splitext(mat["$basetexture2"])[0], True, prefix=mapname))
        if "$normalmapalphaenvmapmask" in mat and "$bumpmap" in mat:
            res["envMapsAlpha"].append(newPath(splitext(mat["$bumpmap"])[0], True, prefix=mapname))
        if "$normalmapalphaenvmapmask2" in mat and "$bumpmap2" in mat:
            res["envMapsAlpha"].append(newPath(splitext(mat["$bumpmap2"])[0], True, prefix=mapname))
    return res

def copyModels(models, dir: SourceDir, mapname=""):
    total = len(models)
    for i, model in enumerate(models):
        print(f"{i}|{total}|done", end="")
        modelName = splitext(basename(model))[0]
        newName = splitext(newPath(model, prefix=mapname))[0]
        path = dirname(model)
        dir.copy(f"{model}", f"{tempDir}/mdl/{newName}.mdl")
        for ext in ["dx90.vtx", "vtx", "vvd"]:
            dir.copy(f"{path}/{modelName}.{ext}", f"{tempDir}/mdl/{newName}.{ext}", True)

def copyModelMaterials(models, dir: SourceDir, modelTints, skinTints, game="WaW", mapname=""):
    materials = []
    res = []
    total = len(models)
    
    for i, model in enumerate(models):
        print(f"{i}|{total}|done", end="")
        mdlName = splitext(newPath(model, prefix=mapname))[0]
        tints = modelTints[mdlName] if mdlName in modelTints else []
        
        if mdlName in skinTints:
            for _, _tints in skinTints[mdlName].items():
                tints += _tints
        
        if not exists(f"{tempDir}/mdl/{mdlName}.mdl"):
            continue
        mdl = Mdl(f"{tempDir}/mdl/{mdlName}.mdl")
        mdl.read()

        for material in mdl.materials:
            for path in mdl.materials_paths:
                path = Path(path).as_posix()
                name = basename(material.name)
                name = f"{path}/{name}".lower()
                if name not in materials:
                    materials.append((name, mdl.header.surface_prop, tints))

                name = Path(material.name).as_posix().lower()
                if name not in materials:
                    materials.append((name, mdl.header.surface_prop, tints))

    total = len(materials)
    for i, (mat, surface_prop, tints) in enumerate(materials):
        print(f"{i}|{total}|done", end="")
        name = newPath(mat, prefix=mapname)
        if dir.copy(f"materials/{mat}.vmt", f"{tempDir}/mdlMats/{name}.vmt", True):
            # unlike CoD, the surface type of a model isn't defined in the material so we have to copy that value
            # from the model and paste it in the materials it uses
            try:
                file = open(f"{tempDir}/mdlMats/{name}.vmt")
                new = file.read().replace("{\n", f'{{\n"$surfaceprop" "{surface_prop}"\n', 1)
                open(f"{tempDir}/mdlMats/{name}.vmt", "w").write(new)
            except:
                pass
            res.append(name)

            # create new a material for each tint value used for the model
            if game == "BO3" and len(tints) > 0:
                for tint in tints:
                    hex = Vector3.FromStr(tint).toHex()
                    tint = (Vector3.FromStr(tint) / 255).round(3)
                    try:
                        file = open(f"{tempDir}/mdlMats/{name}.vmt")
                        new = file.read().replace("{\n", f'{{\n"$colortint" "{tint} 1"\n', 1)
                        open(f"{tempDir}/mdlMats/{name}_{hex}.vmt", "w").write(new)
                        res.append(f"{name}_{hex}")
                    except:
                        pass

    return sorted(set(res))

def surfaceType(surface: str, game=""):
    surface = surface.lower()
    surfaces =     {
        "default": ["plaster", "plaster"],
        "default_silent": ["plaster", "plaster"],
        "floatingstandable": ["plaster", "plaster"],
        "item": ["plastic", "plastic"],
        "ladder": ["metal", "metal"],
        "no_decal": ["plastic", "plastic"],
        "baserock": ["rock", "rock"],
        "boulder": ["rock", "rock"],
        "brick": ["brick", "brick"],
        "concrete": ["concrete", "concrete"],
        "concrete_block": ["concrete", "concrete"],
        "gravel": ["gravel", "gravel"],
        "rock": ["rock", "rock"],
        "canister": ["metal", "metal"],
        "chain": ["metal", "metal"],
        "chainlink": ["metal", "metal"],
        "combine_metal": ["metal", "metal"],
        "crowbar": ["metal", "metal"],
        "floating_metal_barrel": ["metal", "metal"],
        "grenade": ["metal", "metal"],
        "gunship": ["metal", "metal"],
        "metal": ["metal", "metal"],
        "metal_barrel": ["metal", "metal"],
        "metal_bouncy": ["metal", "metal"],
        "metal_box": ["metal", "metal"],
        "metal_seafloorcar": ["metal", "metal"],
        "metalgrate": ["metal", "metal"],
        "metalpanel": ["metal", "metal"],
        "metalvent": ["metal", "metal"],
        "metalvehicle": ["metal", "metal"],
        "paintcan": ["metal", "metal"],
        "popcan": ["metal", "metal"],
        "roller": ["metal", "metal"],
        "slipperymetal": ["metal", "metal"],
        "solidmetal": ["metal", "metal"],
        "strider": ["metal", "metal"],
        "weapon": ["metal", "metal"],
        "wood": ["wood", "wood"],
        "wood_box": ["wood", "wood"],
        "wood_crate": ["wood", "wood"],
        "wood_furniture": ["wood", "wood"],
        "wood_lowdensity": ["wood", "wood"],
        "wood_plank": ["wood", "wood"],
        "wood_panel": ["wood", "wood"],
        "wood_solid": ["wood", "wood"],
        "dirt": ["dirt", "dirt"],
        "grass": ["grass", "foliage"],
        "mud": ["mud", "mud"],
        "quicksand": ["sand", "sand"],
        "sand": ["sand", "sand"],
        "slipperyslime": ["mud", "mud"],
        "antlionsand": ["sand", "sand"],
        "slime": ["mud", "mud"],
        "water": ["water", "water"],
        "wade": ["water", "water"],
        "puddle": ["water", "water"],
        "ice": ["ice", "ice"],
        "snow": ["snow", "snow"],
        "alienflesh": ["flesh", "skin"],
        "antlion": ["flesh", "skin"],
        "armorflesh": ["flesh", "skin"],
        "bloodyflesh": ["flesh", "skin"],
        "flesh": ["flesh", "skin"],
        "foliage": ["foliage", "foliage"],
        "watermelon": ["fruit", "foliage"],
        "zombieflesh": ["flesh", "flesh"],
        "asphalt": ["asphalt", "asphalt"],
        "glass": ["glass", "glass"],
        "glassbottle": ["glass", "glass"],
        "combine_glass": ["glass", "glass"],
        "tile": ["ceramic", "ceramic"],
        "paper": ["paper", "paper"],
        "papercup": ["paper", "paper"],
        "cardboard": ["paper", "paper"],
        "plaster": ["plaster", "plaster"],
        "plastic_barrel": ["plastic", "plastic"],
        "plastic_barrel_buoyant": ["plastic", "plastic"],
        "plastic_box": ["plastic", "plastic"],
        "plastic": ["plastic", "plastic"],
        "rubber": ["plastic", "plastic"],
        "rubbertire": ["plastic", "plastic"],
        "slidingrubbertire": ["plastic", "plastic"],
        "slidingrubbertire_front": ["plastic", "plastic"],
        "slidingrubbertire_rear": ["plastic", "plastic"],
        "jeeptire": ["plastic", "plastic"],
        "brakingrubbertire": ["plastic", "plastic"],
        "carpet": ["carpet", "carpet"],
        "ceiling_tile": ["ceramic", "ceramic"],
        "computer": ["plastic", "plastic"],
        "pottery": ["brick", "brick"]
    }

    glossranges = {
        "<full>": (0.0, 17.0), "asphalt": (0.0, 4.0), "brick": (0.0, 4.0), "carpet": (0.0, 2.0),"ceramic": (0.0, 17.0), "cloth": (0.0, 4.0), "concrete": (0.0, 4.0),
        "dirt": (0.0, 4.0), "skin": (2.0, 10.0), "foliage": (0.0, 6.5), "glass": (6.0, 17.0), "gravel": (0.0, 4.0), "ice": (4.0, 17.0), "metal": (0.0, 17.0),
        "mud": (4.0, 13.0), "paint": (2.0, 7.0), "paper": (0.0, 2.0), "plaster": (0.0, 2.0), "plastic": (4.0, 13.0), "rock": (0.0, 4.0), "rubber": (0.0, 4.0),
        "sand": (2.0, 8.0), "snow": (4.0, 12.0), "water": (6.0, 17.0), "wood": (2.0, 5.0), "bark": (0.0, 4.0)
    }

    if surface in surfaces:
        if game == "CoD2": # some surface types don't exist in CoD 2
            cod2surfs = [
                'asphalt', 'bark', 'brick', 'carpet', 'cloth',
                'concrete', 'dirt', 'flesh', 'foliage',
                'glass', 'grass', 'gravel', 'ice', 'metal', 'mud', 'paper',
                'plaster', 'rock', 'sand', 'snow', 'water', 'wood'
            ]

            if surfaces[surface][0] not in cod2surfs:
                surfaces[surface][0] = "<none>"

        return {
            "surface": surfaces[surface][0],
            "gloss": surfaces[surface][1],
            "glossrange": glossranges[surfaces[surface][1]]
        }

    else:
        return {
            "surface": "<none>",
            "gloss": "<custom>",
            "glossrange": (0, 0.5)
        }
    
def createMaterialGdt(vmts: dict, game="WaW", mapname=""):
    if game == "BO3":
        return createMaterialGdtBo3(vmts, mapname)
    gdt = Gdt()
    textureDir = f"texture_assets\\\\corvid\\\\{mapname}\\\\"
    ext, _ext = ".tga", "_.tga"

    fileList = listdir(f"{tempDir}/matTex") + listdir(f"{tempDir}/mdlTex")

    total = len(vmts.items())

    for i, (name, vmt) in enumerate(vmts.items()):
        print(f"{i}|{total}|done", end="")
        shader = list(vmt)[0]
        
        try:
            mat = vmt[shader]
            data = {}
        except:
            print(f"Error parsing {name}. Skipping...")
            print(vmt)
            continue

        assetName = name

        if shader == "lightmappedgeneric" or shader == "worldvertextransition":
            data["materialType"] = "world phong"
        elif shader == "unlitgeneric":
            data["materialType"] = "world unlit"
        elif shader == "vertexlitgeneric":
            data["materialType"] = "model phong"
        else:
            data["materialType"] = "world phong"
        
        data["usage"] = "tools"

        if "$basetexture" in mat:
            fileName = newPath(mat["$basetexture"], shorten=True, prefix=mapname)
            if fileName + ".vtf" in fileList:
                data["colorMap"] = textureDir + fileName + ext
            else:
                data["colorMap"] = textureDir + "404" + ext
        else:
            data["colorMap"] = textureDir + "404" + ext
        
        if "$bumpmap" in mat and "$ssbump" not in mat:
            fileName = newPath(mat["$bumpmap"], shorten=True, prefix=mapname)
            if fileName + ".vtf" in fileList:
                data["normalMap"] = textureDir + fileName + ext
        if "$envmapmask" in mat:
            fileName = newPath(mat["$envmapmask"], shorten=True, prefix=mapname)
            if fileName + ".vtf" in fileList:
                data["cosinePowerMap"] = textureDir + fileName + ext
        if "$basealphaenvmapmask" in mat and "$envmapmask" not in mat:
            fileName = newPath(mat["$basetexture"], shorten=True, prefix=mapname)
            if fileName + "_.vtf" in fileList:
                data["cosinePowerMap"] = textureDir + fileName + _ext
        if "$normalmapalphaenvmapmask" in mat and "$envmapmask" not in mat and "$bumpmap" in mat:
            fileName = newPath(mat["$bumpmap"], shorten=True, prefix=mapname)
            if fileName + "_.vtf" in fileList:
                data["cosinePowerMap"] = textureDir + fileName + _ext

        if "$nocull" in mat:
            data["cullFace"] = "None"

        if "$surfaceprop" in mat:
            data["surfaceType"] = surfaceType(mat["$surfaceprop"].strip(), game)["surface"]
        else:
            data["surfaceType"] = "<none>"

        if "$alphatest" in mat or "$alpha" in mat:
            data["alphaTest"] = "GE128"
        if "$translucent" in mat:
            data["blendFunc"] = "Blend"

        if "$decal" in mat:
            data["sort"] = "decal - static decal"
            data["polygonOffset"] = "Static Decal"
            data["locale_decal"] = "1"

        if "$basetexture2" in mat:
            data2 = {}
            data2["materialType"] = "world phong"
            fileName = newPath(mat["$basetexture2"], shorten=True, prefix=mapname)
            if fileName + ".vtf" in fileList:
                data2["colorMap"] = textureDir + fileName + ext
            else:
                data2["colorMap"] = textureDir + "404" + ext

            data2["blendFunc"] = "Blend"
            data2["usage"] = "tools"

            if "$bumpmap2" in mat and "$ssbump" not in mat:
                fileName = newPath(mat["$bumpmap2"], shorten=True, prefix=mapname)
                if fileName + ".vtf" in fileList:
                    data2["normalMap"] = textureDir + fileName + ext
            if "$envmapmask2" in mat:
                fileName = newPath(mat["$envmapmask2"], shorten=True, prefix=mapname)
                if fileName + ".vtf" in fileList:
                    data["cosinePowerMap"] = textureDir + fileName + ext
            if "$basealphaenvmapmask2" in mat and "$envmapmask2" not in mat:
                fileName = newPath(mat["$basetexture2"], shorten=True, prefix=mapname)
                if fileName + "_.vtf" in fileList:
                    data2["cosinePowerMap"] = textureDir + fileName + _ext
            if "$normalmapalphaenvmapmask2" in mat and "$envmapmask2" not in mat and "$bumpmap2" in mat:
                fileName = newPath(mat["$bumpmap2"], shorten=True, prefix=mapname)
                if fileName + "_.vtf" in fileList:
                    data2["cosinePowerMap"] = textureDir + fileName + _ext

            if "$surfaceprop2" in mat:
                data2["surfaceType"] = surfaceType(mat["$surfaceprop2"].strip())["surface"]
            else:
                data2["surfaceType"] = "<none>"

            if "$alphatest" in mat or "$alpha" in mat:
                data2["alphaTest"] = "GE128"

            gdt.add(assetName.strip() + "_blend", "material", data2)

        gdt.add(assetName.strip(), "material", data)
    return gdt

def createMaterialGdtBo3(vmts: dict, mapname=""):
    gdt = Gdt()
    total = len(vmts.items())
    fileList = listdir(f"{tempDir}/matTex") + listdir(f"{tempDir}/mdlTex")

    for i, (name, vmt) in enumerate(vmts.items()):
        print(f"{i}|{total}|done", end="")
        shader = list(vmt)[0]
        mat = vmt[shader]
        assetName = name

        data = {}
        data["template"] = "material.template"

        # these are default values and should stay the same unless the material requires more than a color map and a normal map
        data["materialCategory"] = "Geometry"
        data["materialType"] = "lit"

        if "$basetexture" in mat:
            fileName = newPath(mat["$basetexture"], shorten=True, prefix=mapname)
            if fileName + ".vtf" in fileList:
                data["colorMap"] = "i_" + newPath(mat["$basetexture"], shorten=True, prefix=mapname)
            else:
                data["colorMap"] = "i_404"
        else:
            data["colorMap"] = "i_404"
        
        if shader == "vertexlitgeneric" or shader == "vertexunlitgeneric":
            data["usage"] = "<not in editor>"
        else:
            data["usage"] = "tools" # probably not a good idea

        if "$bumpmap" in mat and "$ssbump" not in mat:
            fileName = newPath(mat["$bumpmap"], shorten=True, prefix=mapname)
            if fileName + ".vtf" in fileList:
                data["normalMap"] = "i_" + fileName
        if "$envmapmask" in mat:
            fileName = newPath(mat["$envmapmask"], shorten=True, prefix=mapname)
            if fileName + ".vtf" in fileList:
                data["cosinePowerMap"] = "i_" + fileName
                data["materialCategory"] = "Geometry Plus"
                data["materialType"] = "lit_plus"
        if "$basealphaenvmapmask" in mat and "$envmapmask" not in mat:
            fileName = newPath(mat["$basetexture"], shorten=True, prefix=mapname)
            if fileName + "_.vtf" in fileList:
                data["cosinePowerMap"] = "i_" + fileName + "_"
                data["materialCategory"] = "Geometry Plus"
                data["materialType"] = "lit_plus"
        if "$normalmapalphaenvmapmask" in mat and "$envmapmask" not in mat and "$bumpmap" in mat:
            fileName = newPath(mat["$bumpmap"], shorten=True, prefix=mapname)
            if fileName + "_.vtf" in fileList:
                data["cosinePowerMap"] = "i_" + fileName + "_"
                data["materialCategory"] = "Geometry Plus"
                data["materialType"] = "lit_plus"

        if "$surfaceprop" in mat:
            surfaceprop = surfaceType(mat["$surfaceprop"].strip())
            data["surfaceType"] = surfaceprop["surface"]
            data["glossSurfaceType"] = "<custom>"
            data["glossRangeMin"] = surfaceprop["glossrange"][0] / 10
            data["glossRangeMax"] = surfaceprop["glossrange"][1]
        else:
            data["surfaceType"] = "<none>"
            data["glossSurfaceType"] = "<custom>"
            data["glossRangeMin"] = "0.0"
            data["glossRangeMax"] = "0.5"
        
        # gotta change the material type for things like alphatest, translucency and back face culling
        # that's one of the major differences between the old and new asset pipeline from what I can tell

        if "$translucent" in mat:
            if data["materialType"] == "lit_plus":
                data["materialType"] = "lit_transparent_plus"
            else:
                data["materialType"] = "lit_transparent"

        if "$alpha" in mat or "$alphatest" in mat:
            if data["materialType"] == "lit_plus":
                data["materialType"] = "lit_alphatest_plus"
            else:
                data["materialType"] = "lit_alphatest"
        
        if "$nocull" in mat:
            if data["materialType"] == "lit_transparent_plus":
                data["materialType"] = "lit_transparent_nocull_plus"
            elif data["materialType"] == "lit_transparent":
                data["materialType"] = "lit_transparent_nocull"
            elif data["materialType"] == "lit_alphatest":
                data["materialType"] = "lit_alphatest_nocull"
            elif data["materialType"] == "lit_alphatest_plus":
                data["materialType"] = "lit_alphatest_nocull_plus"
            elif data["materialType"] == "lit_plus":
                data["materialType"] = "lit_nocull_plus"
            else:
                data["materialType"] = "lit_nocull"

        # if "$selfillum" in mat:
        #     if mat["$selfillum"] == "1":
        #         data["materialType"] = "lit_emissive"

        if "$color" in mat:
            if mat["$color"].startswith("{"):
                data["colorTint"] = (Vector3.FromStr(mat["$color"]) / 255).round(3)
            else:
                data["colorTint"] = Vector3.FromStr(mat["$color"])

        if "$colortint" in mat:
            data["colorTint"] = mat["$colortint"]

        if "$layertint1" in mat:
            if mat["$layertint1"].startswith("{"):
                data["colorTint"] = (Vector3.FromStr(mat["$layertint1"]) / 255).round(3)
            else:
                data["colorTint"] = Vector3.FromStr(mat["$layertint1"])

        if "$basetexture2" in mat:
            data2 = {}
            data2["materialCategory"] = "Decal"
            data2["materialType"] = "lit_decal_reveal"

            fileName = newPath(mat["$basetexture2"], shorten=True, prefix=mapname)
            if fileName + ".vtf" in fileList:
                data2["colorMap"] = "i_" + fileName
            else:
                data2["colorMap"] = "404"
            data2["usage"] = "tools" # probably not a good idea
                    
            if "$bumpmap2" in mat and "$ssbump2" not in mat:
                fileName = newPath(mat["$bumpmap2"], shorten=True)
                if fileName + ".vtf" in fileList:
                    data2["normalMap"] = "i_" + newPath(mat["$bumpmap2"], shorten=True, prefix=mapname)
            if "$blendmodulatetexture" in mat:
                fileName = newPath(mat["$blendmodulatetexture"], shorten=True)
                if fileName + ".vtf" in fileList:
                    data2["alphaRevealMap"] = "i_" + newPath(mat["$blendmodulatetexture"], shorten=True, prefix=mapname)
            if "$envmapmask2" in mat:
                fileName = newPath(mat["$envmapmask2"], shorten=True)
                if fileName + ".vtf" in fileList:
                    data2["cosinePowerMap"] = "i_" + newPath(mat["$envmapmask2"], shorten=True, prefix=mapname)
                    data2["materialType"] = "lit_decal_reveal_plus"
            if "$basealphaenvmapmask2" in mat and "$envmapmask2" not in mat:
                fileName = newPath(mat["$basetexture2"], shorten=True)
                if fileName + "_.vtf" in fileList:
                    data2["cosinePowerMap"] = "i_" + newPath(mat["$basetexture2"], shorten=True, prefix=mapname) + "_"
                    data2["materialType"] = "lit_decal_reveal_plus"
            if "$normalmapalphaenvmapmask2" in mat and "$envmapmask2" not in mat and "$bumpmap2" in mat:
                fileName = newPath(mat["$bumpmap2"], shorten=True)
                if fileName + "_.vtf" in fileList:
                    data2["cosinePowerMap"] = "i_" + newPath(mat["$bumpmap2"], shorten=True, prefix=mapname) + "_"
                    data2["materialType"] = "lit_decal_reveal_plus"

            if "$surfaceprop2" in mat:
                surfaceprop = surfaceType(mat["$surfaceprop2"].strip())
                data2["surfaceType"] = surfaceprop["surface"]
                data2["glossSurfaceType"] = surfaceprop["gloss"]
                data2["glossRangeMin"] = surfaceprop["glossrange"][0]
                data2["glossRangeMax"] = surfaceprop["glossrange"][1]
            else:
                data2["surfaceType"] = "<none>"
                data2["glossSurfaceType"] = "<custom>"
                data2["glossRangeMin"] = "0.0"
                data2["glossRangeMax"] = "0.4"

            if "$layertint2" in mat:
                if mat["$layertint2"].startswith("{"):
                    data2["colorTint"] = (Vector3.FromStr(mat["$layertint2"]) / 255).round(3)
                else:
                    data2["colorTint"] = Vector3.FromStr(mat["$layertint2"])            

            gdt.add(assetName + "_blend", "material", data2)
        
        gdt.add(assetName, "material", data)
    
    return gdt

def createModelGdt(models, game="WaW", modelTints={}, modelSkins={}, skinTints={}, mapname=""):
    gdt = Gdt()
    total = len(models)

    for i, model in enumerate(models):
        print(f"{i}|{total}|done", end="")
        name = splitext(newPath(model, prefix=mapname))[0]

        gdt.add("m_" + name, "xmodel", {
            "collisionLOD" if game != "BO3" else "BulletCollisionLOD": "High",
            "filename": f"corvid\\\\{mapname}\\\\{name}." + ("xmodel_export" if game != "BO3" else "xmodel_bin"),
            "type": "rigid"
        })

        if game == "BO3" and name in modelTints:
            for tint in modelTints[name]:
                hex = Vector3.FromStr(tint).toHex()
                gdt.add(f"m_{name}_{hex}", "xmodel", {
                    "collisionLOD" if game != "BO3" else "BulletCollisionLOD": "High",
                    "filename": f"corvid\\\\{mapname}\\\\{name}_{hex}." + ("xmodel_export" if game != "BO3" else "xmodel_bin"),
                    "type": "rigid"
                })

        if name in modelSkins:
            for skin in modelSkins[name]:
                gdt.add(f"m_{name}_skin{skin}", "xmodel", {
                    "collisionLOD" if game != "BO3" else "BulletCollisionLOD": "High",
                    "filename": f"corvid\\\\{mapname}\\\\{name}_skin{skin}." + ("xmodel_export" if game != "BO3" else "xmodel_bin"),
                    "type": "rigid"
                })

        if name in skinTints:
            for skin, tints in skinTints[name].items():
                for tint in tints:
                    hex = Vector3.FromStr(tint).toHex()
                    gdt.add(f"m_{name}_skin{skin}_{hex}", "xmodel", {
                        "collisionLOD" if game != "BO3" else "BulletCollisionLOD": "High",
                        "filename": f"corvid\\\\{mapname}\\\\{name}_skin{skin}_{hex}." + ("xmodel_export" if game != "BO3" else "xmodel_bin"),
                        "type": "rigid"
                    })

    return gdt

def createImageGdt(images, mapname=""):
    gdt = Gdt()
    images["colorMaps"] = list(dict.fromkeys(images["colorMaps"]))
    images["colorMapsAlpha"] = list(dict.fromkeys(images["colorMapsAlpha"]))
    images["normalMaps"] = list(dict.fromkeys(images["normalMaps"]))
    images["envMaps"] = list(dict.fromkeys(images["envMaps"]))
    images["envMapsAlpha"] = list(dict.fromkeys(images["envMapsAlpha"]))
    images["revealMaps"] = list(dict.fromkeys(images["revealMaps"]))

    lencolorMaps = len(images["colorMaps"])
    lencolorMapsAlpha = len(images["colorMapsAlpha"])
    lennormalMaps = len(images["normalMaps"])
    lenenvMaps = len(images["envMaps"])
    lenenvMapsAlpha = len(images["envMapsAlpha"])
    lenrevealMaps = len(images["revealMaps"])
    total = lencolorMaps + lencolorMapsAlpha + lennormalMaps + lenenvMaps + lenenvMapsAlpha + lenrevealMaps

    for i, file in enumerate(images["colorMaps"]):
        print(f"{i}|{total}|done", end="")
        gdt.add(f"i_{file}", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{mapname}\\\\{file}.tif",
            "semantic": "diffuseMap",
            "compressionMethod": "compressed high color",
            "coreSemantic": "sRGB3chAlpha",
            "streamable": "1"
        })

    for i, file in enumerate(images["colorMapsAlpha"], lencolorMaps):
        print(f"{i}|{total}|done", end="")
        gdt.add(f"i_{file}", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}.tif",
            "semantic": "diffuseMap",
            "compressionMethod": "compressed high color",
            "coreSemantic": "sRGB3chAlpha",
            "streamable": "1"
        })

    for i, file in enumerate(images["normalMaps"], lencolorMaps + lencolorMapsAlpha):
        print(f"{i}|{total}|done", end="")
        gdt.add(f"i_{file}", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}.tif",
            "semantic": "normalMap",
            "compressionMethod": "compressed",
            "coreSemantic": "Normal",
            "streamable": "1"
        })

    for i, file in enumerate(images["envMaps"], lencolorMaps + lencolorMapsAlpha + lennormalMaps):
        print(f"{i}|{total}|done", end="")
        
        # some materials use the same image for both their color maps and env maps. we need to create seperate image asset for them
        file = file + "_" if file in images["colorMaps"] or file in images["colorMapsAlpha"] else file
        gdt.add(f"i_{file}", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}.tif",
            "semantic": "glossMap",
            "compressionMethod": "compressed",
            "coreSemantic": "Linear1ch",
            "streamable": "1"
        })

    for i, file in enumerate(images["envMapsAlpha"], lencolorMaps + lencolorMapsAlpha + lennormalMaps + lenenvMaps):
        print(f"{i}|{total}|done", end="")
        gdt.add(f"i_{file}_", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}_.tif",
            "semantic": "glossMap",
            "compressionMethod": "compressed",
            "coreSemantic": "Linear1ch",
            "streamable": "1"
        })

    for i, file in enumerate(images["revealMaps"], lencolorMaps + lencolorMapsAlpha + lennormalMaps + lenenvMaps + lenenvMapsAlpha):
        print(f"{i}|{total}|done", end="")
        gdt.add(f"i_{file}", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}.tif",
            "semantic": "revealMap",
            "compressionMethod": "compressed",
            "coreSemantic": "Linear1ch",
            "streamable": "1"
        })
    
    gdt.add("i_404", "image", {
        "imageType": "Texture",
        "type": "image",
        "baseImage": "texture_assets\\\\corvid\\\\404.tif",
        "semantic": "diffuseMap",
        "compressionMethod": "compressed high color",
        "coreSemantic": "sRGB3chAlpha",
        "streamable": "1"
    })
    
    return gdt

def normalizeAngle(angle: int):
    if angle > 0:
        return angle % 360
    elif angle < 0:
        return (360 + angle) % 360

def exportSkybox(skyName: str, mapName: str, worldSpawnSettings, dir: SourceDir, game="WaW"):
    skyName = skyName.lower()
    faces = ["up", "dn", "lf", "rt", "ft", "bk"]
    gdt = Gdt()
    ext = "tif" if game == "BO3" else "tga"
    convertDir = f"{tempDir}/converted/texture_assets/corvid/{mapName}/"

    for face in faces:
        name = f"{mapName}_sky_{face}"
        if dir.copy(f"materials/skybox/{skyName}{face}.vmt", f"{tempDir}/mat/{name}.vmt"):
            vmt = fixVmt(open(f"{tempDir}/mat/{name}.vmt").read())
            vmt = parse_vdf(fixVmt(vmt))
            shader = list(vmt)[0]
            mat = vmt[shader]
            # could be any of these three
            for param in ["$basetexture", "$hdrcompressedtexture", "$hdrbasetexture"]:
                if param in mat:
                    texture = param
                    break
            texture = splitext(basename(mat[texture]))[0]
            dir.copy(f"materials/skybox/{texture}.vtf", f"{tempDir}/matTex/{name}.vtf")
            convertImage(f"{tempDir}/matTex/{name}.vtf", f"{convertDir}/{name}.{ext}", format="rgb", resize=True)
        else:
            return gdt # return an empty gdt in case the sky materials can't be found

    if game == "BO3":
        print("Converting skybox...")
        # load all sides of the cubemap
        images = {}
        for face in faces:
            if not exists(f"{convertDir}/{mapName}_sky_{face}.tif"):
                return gdt
            images[face] = Image.open(f"{convertDir}/{mapName}_sky_{face}.tif").resize((1024, 1024))
        
        # create an empty image and paste all sides in it
        cubemap = Image.new(mode="RGB", size=(4096, 3072), color=(255, 255, 255))

        # rt ft lf bk
        # bk rt ft lf

        cubemap.paste(images["bk"], (0, 1024))
        cubemap.paste(images["rt"], (1024, 1024))
        cubemap.paste(images["up"], (1024, 0))
        cubemap.paste(images["ft"], (2048, 1024))
        cubemap.paste(images["lf"], (3072, 1024))
        cubemap.paste(images["dn"], (1024, 2048))
        cubemap.save(f"{convertDir}/cubemap.tif")

        # create an equirectangular image from the new cubemap image
        # based on https://github.com/adamb70/Python-Spherical-Projection/blob/master/Example/Example%201/SingleExample.py
        wo, ho = cubemap.size

        h = int(wo / 3)
        w = int(2 * h)
        n = ho / 3

        res = Image.new(mode="RGB", size=(w, h), color=(0, 255, 239))

        for ycoord in range(0, h):
            for xcoord in range(0, w):
                corrx, corry = find_corresponding_pixel(xcoord, ycoord, w, h, n)
                res.putpixel((xcoord, ycoord), cubemap.getpixel((corrx, corry)))

        res.save(f"{convertDir}/i_{mapName}_sky.tif")

        # create GDTs for the skybox assets
        gdt.add(f"i_{mapName}_sky", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{mapName}\\\\i_{mapName}_sky.tif",
            "semantic": "HDR",
            "compressionMethod": "uncompressed",
            "coreSemantic": "HDR",
            "streamable": "1"
        })
        gdt.add(f"{mapName}_sky_mtl", "material", {
            "materialCategory": "Geometry",
            "materialType": "sky_latlong_hdr",
            "colorMap": f"i_{mapName}_sky",
            "surfaceType": "<none>",
            "glossSurfaceType": "<full>",
            "usage": "<not in editor>",
            "noImpact": "1",
            "noMarks": "1",
            "nonColliding": "1",
            "noCastShadow": "1",
            "skyHalfSpace": "1",
            "skyStops": "13.5",
            "skySize": "8000"

        })

        gdt.add(f"{mapName}_skybox", "xmodel", {
            "filename": f"t6_props\\\\vista\\\\skybox\\\\t6_skybox.xmodel_bin",
            "type": "rigid",
            "skinOverride": f"mtl_skybox_default {mapName}_sky_mtl\\r\\n",
            "BulletCollisionLOD": "None"
        })

        suncolor = worldSpawnSettings["suncolor"] if "suncolor" in worldSpawnSettings else "1 1 1 1"
        sundirection = worldSpawnSettings["sundirection"] if "sundirection" in worldSpawnSettings else Vector3(0, 0, 0)

        gdt.add(f"{mapName}_ssi", "ssi", {
            "bounceCount": "4",
            "colorSRGB": f"{suncolor} 1",
            "dynamicShadow": "1",
            "enablesun": "1",
            "ev": "15",
            "evcmp": "0",
            "evmax": "16",
            "evmin": "1",
            "lensFlare": "",
            "lensFlarePitchOffset": "0",
            "lensFlareYawOffset": "0",
            "penumbra_inches": "1.5",
            "pitch": normalizeAngle(int(-sundirection.x)),
            "skyboxmodel": f"{mapName}_skybox",
            "spec_comp": "0",
            "stops": "14",
            "sunCookieAngle": "0",
            "sunCookieIntensity": "0",
            "sunCookieLightDefName": "",
            "sunCookieOffsetX": "0",
            "sunCookieOffsetY": "0",
            "sunCookieRotation": "0",
            "sunCookieScale": "0",
            "sunCookieScrollX": "0",
            "sunCookieScrollY": "0",
            "sunVolumetricCookie": "0",
            "type": "ssi",
            "yaw": normalizeAngle((sundirection.y - 180))
        })
    else:
        gdt.add(f"{mapName}_sky", "material", {
            "materialType": "sky",
            "usage": "sky",
            "locale_tools": "1",
            "sort": "skybox - horizon",
            "surfaceType": "<none>",
            "noLightmap": "1",
            "noCastShadow": "1",
            "noReceiveDynamicShadow": "1",
            "nopicmipColor": "1",
            "sky": "1",
            "colorMap": f"texture_assets\\\\corvid\\\\{mapName}\\\\{mapName}_sky_ft.tga"
        })
    return gdt

def exportMinimap(mapName: str, dir: SourceDir, game="WaW"):
    gdt = Gdt()
    
    # if it's a decompiled map, we need to remove that suffix
    if mapName.endswith("_d"):
        mapName = mapName[0:-2].lower()
    elif mapName.endswith("_decompiled"):
        mapName = mapName[0:-11].lower()

    ext = "png" if game == "BO3" else "tga" # file extension

    overview = dir.open(f"resource/overviews/{mapName}.txt")

    if overview is None:
        return None, None, None
    
    if isinstance(overview, bytes): # it's from a vpk
        overview = overview.decode("ascii")
    
    overview = fixVmt(overview)

    data = parse_vdf(overview)
    data = data[list(data)[0]]

    if "material" not in data:
        return None, None, None
    
    image: Image
    # csgo uses dds images for radars whereas older games use vtf images
    if dir.copy(f"resource/overviews/{data['material']}_radar.dds", f"{tempDir}/matTex/{mapName}_radar.dds", silent=True):
        Image.open(f"{tempDir}/matTex/{mapName}_radar.dds").save(f"{tempDir}/converted/texture_assets/corvid/{mapName}/{mapName}_radar.{ext}", silent=True)
    elif dir.copy(f"materials/{data['material']}_radar.vmt", f"{tempDir}/mat/{mapName}_radar.vmt"):
        mat = parse_vdf(fixVmt(open(f"{tempDir}/mat/{mapName}_radar.vmt").read()))
        mat = mat[list(mat)[0]]
        if "$basetexture" in mat:
            if not dir.copy("materials/" + mat["$basetexture"] + ".vtf", f"{tempDir}/matTex/{mapName}_radar.vtf", silent=True):
                return None, None, None
        convertImage(f"{tempDir}/matTex/{mapName}_radar.vtf", f"{tempDir}/converted/texture_assets/corvid/{mapName}/{mapName}_radar.{ext}",  "rgb")
    else:
        return None, None, None

    image = Image.open(f"{tempDir}/converted/texture_assets/corvid/{mapName}/{mapName}_radar.{ext}")

    if "rotate" in data and data["rotate"] != "1":
        image = image.rotate(90)
    
    image.save(f"{tempDir}/converted/texture_assets/corvid/{mapName}/{mapName}_radar.{ext}")

    if game == "BO3":
        gdt.add(f"i_{mapName}_minimap", "image",{
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{mapName}\\\\{mapName}_radar.png",
            "semantic": "2d",
            "compressionMethod": "compressed",
            "coreSemantic": "Linear4ch",
            "streamable": "1",
            "clampU": "1",
            "clampV": "1"
        })

        gdt.add(f"{mapName}_minimap", "material",{
            "colorMap": f"i_{mapName}_minimap",
            "materialType": "2d_add"
        },
        "base:local")


    else:
        gdt.add(f"{mapName}_minimap", "material", {
            "materialType": "2d",
            "surfaceType": "<none>",
            "usage": "<not in editor>",
            "colorMap": f"texture_assets\\\\corvid\\\\{mapName}_radar.tga",
            "tileColor": "no tile",
            "filterColor": "nomip bilinear",
            "nopicmipColor": "1"
        })

    return gdt, data["pos_x"], data["pos_y"]
        