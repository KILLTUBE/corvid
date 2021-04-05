from genericpath import exists
from PIL import Image
from modules.Vector3 import Vector3FromStr
from modules.Vector2 import Vector2
from modules.vdfutils import parse_vdf
from os.path import basename, splitext, dirname
from .Static import fixVmt, rgbToHex, uniqueName
from .Gdt import Gdt
from tempfile import gettempdir
from .AssetConverter import getTexSize, convertImage
from SourceIO.source1.mdl.mdl_file import Mdl
from pathlib import Path
from .SourceDir import SourceDir
from vrProjector.vrProjector.CubemapProjection import CubemapProjection
from vrProjector.vrProjector import CubemapProjection, EquirectangularProjection

tempDir = f"{gettempdir()}/corvid"

def copyMaterials(mats, dir: SourceDir):
    res = []
    total = len(mats)
    for i in range(total):
        print(f"{i}|{total}|done", end="")
        mat = mats[i]
        name = basename(mat)
        dir.copy(f"materials/{mat}.vmt", f"{tempDir}/mat/{name}.vmt")
        res.append(name)
    return res

def copyTextures(mats, dir: SourceDir, mdl=False):
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
    i = 0
    for file in mats:
        print(f"{i}|{total}|done", end=""); i += 1;
        fileName = basename(file)
        vmtPath = f"{tempDir}/{vmtDir}/{fileName}.vmt"
        if not exists(vmtPath):
            print(f"Could not find material {fileName}. Creating an empty material for it...")
            res["vmts"][fileName] = 'lightmappedgeneric\n{\n"$basetexture" "404"\n}'
            res["sizes"][file.strip()] = Vector2(512, 512)
            return res
        vmt = parse_vdf(fixVmt(open(vmtPath).read()))
        res["vmts"][fileName] = vmt
        shader = list(vmt)[0]
        mat = vmt[shader]

        # some materials in Source can reference & inherit other materials' properties
        if "include" in mat:
            includeFile = mat["include"]
            if not includeFile.startswith("materials"):
                includeFile = "materials/" + includeFile
            if not includeFile.endswith(".vmt"):
                includeFile += ".vmt"
            includeFile = Path(includeFile).as_posix().lower().strip()
            if dir.copy(includeFile, f"{tempDir}/{vmtDir}/{basename(includeFile)}"):
                try:
                    includeVmt = parse_vdf(fixVmt(open(f"{tempDir}/{vmtDir}/{basename(includeFile)}").read()))
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
            name = splitext(basename(baseTexture))[0]
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
            name: str = splitext(basename(bumpMap))[0]
            dir.copy(f"materials/{bumpMap}.vtf", f"{tempDir}/{vtfDir}/{name}.vtf")
            res["normalMaps"].append(name)
        if "$envmapmask" in mat:
            envMap: str = mat["$envmapmask"].strip()
            name = splitext(basename(envMap))[0]
            dir.copy(f"materials/{envMap}.vtf", f"{tempDir}/{vtfDir}/{name}.vtf")
            res["envMaps"].append(name)
        if "$blendmodulatetexture" in mat:
            revealMap: str = mat["$blendmodulatetexture"].strip()
            name = splitext(basename(revealMap))[0]
            dir.copy(f"materials/{revealMap}.vtf", f"{tempDir}/{vtfDir}/{name}.vtf")
            res["revealMaps"].append(name)
        if "$basetexture2" in mat:
            basetexture2 = mat["$basetexture2"].strip()
            name: str = splitext(basename(basetexture2))[0]
            dir.copy(f"materials/{basetexture2}.vtf", f"{tempDir}/{vtfDir}/{name}.vtf")
            res["colorMaps"].append(name)
            res["sizes"][file.strip() + "_"] = getTexSize(f"{tempDir}/{vtfDir}/{name}.vtf")
        if "$bumpmap2" in mat:
            bumpMap2 = mat["$bumpmap2"].strip()
            name: str = splitext(basename(bumpMap2))[0]
            dir.copy(f"materials/{bumpMap2}.vtf", f"{tempDir}/{vtfDir}/{name}.vtf")
            res["normalMaps"].append(name)
        if "$envmapmask2" in mat:
            envMap2: str = mat["$envmapmask2"].strip()
            name = splitext(basename(envMap2))[0]
            dir.copy(f"materials/{envMap2}.vtf", f"{tempDir}/{vtfDir}/{name}.vtf")
            res["envMaps"].append(name)
        if "$basealphaenvmapmask" in mat:
            res["envMapsAlpha"].append(basename(mat["$basetexture"].strip()))
        if "$basealphaenvmapmask2" in mat:
            res["envMapsAlpha"].append(basename(mat["$basetexture2"].strip()))
        if "$normalmapalphaenvmapmask" in mat and "$bumpmap" in mat:
            res["envMapsAlpha"].append(basename(mat["$bumpmap"].strip()))
        if "$normalmapalphaenvmapmask2" in mat and "$bumpmap2" in mat:
            res["envMapsAlpha"].append(basename(mat["$bumpmap2"].strip()))
    return res

def copyModels(models, dir: SourceDir):
    total = len(models)
    i = 0
    for model in models:
        print(f"{i}|{total}|done", end=""); i += 1;
        name = splitext(basename(model))[0]
        path = dirname(model)
        dir.copy(f"{model}", f"{tempDir}/mdl/{name}.mdl")
        for ext in ["dx90.vtx", "vtx", "vvd"]:
            dir.copy(f"{path}/{name}.{ext}", f"{tempDir}/mdl/{name}.{ext}", True)

def copyModelMaterials(models, dir: SourceDir, modelTints, BO3=False):
    materials = []
    res = []
    total = len(models)
    i = 0
    for model in models:
        print(f"{i}|{total}|done", end=""); i += 1;
        mdlName = splitext(basename(model))[0]
        tints = modelTints[mdlName] if mdlName in modelTints else []
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
    i = 0
    for mat, surface_prop, tints in materials:
        print(f"{i}|{total}|done", end=""); i += 1;
        name = basename(mat)
        if dir.copy(f"materials/{mat}.vmt", f"{tempDir}/mdlMats/{name}.vmt", True):
            # unlike CoD, the surface type of a model isn't defined in the material so we have to copy that value
            # from the model and paste it in the materials it uses
            try:
                file = open(f"{tempDir}/mdlMats/{name}.vmt")
                new = file.read().replace("{\n", f'{{\n"$surfaceprop" "{surface_prop}"\n', 1)
                open(f"{tempDir}/mdlMats/{name}.vmt", "w").write(new)
            except:
                pass
            res.append(mat)

            # create new a material for each tint value used for the model
            if BO3 and len(tints) > 0:
                for tint in tints:
                    hex = rgbToHex(tint)
                    tint = (Vector3FromStr(tint) / 255).round(3)
                    try:
                        file = open(f"{tempDir}/mdlMats/{name}.vmt")
                        new = file.read().replace("{\n", f'{{\n"$colortint" "{tint} 1"\n', 1)
                        open(f"{tempDir}/mdlMats/{name}_{hex}.vmt", "w").write(new)
                        res.append(f"{mat}_{hex}")
                    except:
                        pass

    return sorted(set(res))

def surfaceType(surface):
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
    if surface in surfaces:
        return {
            "surface": surfaces[surface][0],
            "gloss": surfaces[surface][1],
        }
    else:
        return {
            "surface": "<none>",
            "gloss": "<full>"
        }
    
def createMaterialGdt(vmts: dict, BO3=False):
    if BO3:
        return createMaterialGdtBo3(vmts)
    gdt = Gdt()
    textureDir = "texture_assets\\\\corvid\\\\"
    ext, _ext = ".tga", "_.tga"

    total = len(vmts.items())
    i = 0
    for name, vmt in vmts.items():
        print(f"{i}|{total}|done", end=""); i += 1;
        shader = list(vmt)[0]
        mat = vmt[shader]
        data = {}
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
            if "$translucent" in mat or "$alpha" in mat or "$alphatest" in mat:
                data["colorMap"] = textureDir + uniqueName(mat["$basetexture"].strip()) + ext
            else:
                data["colorMap"] = textureDir + uniqueName(mat["$basetexture"].strip()) + ext
        else:
            data["colorMap"] = textureDir + "noColorMap" + ext

        if "$bumpmap" in mat and "$ssbump" not in mat:
            data["normalMap"] = textureDir + uniqueName(mat["$bumpmap"].strip()) + ext
        if "$envmapmask" in mat:
            data["cosinePowerMap"] = textureDir + uniqueName(mat["$envmapmask"].strip()) + ext
        if "$basealphaenvmapmask" in mat and "$envmapmask" not in mat:
            data["cosinePowerMap"] = textureDir + uniqueName(mat["$basetexture"].strip()) + _ext
        if "$normalmapalphaenvmapmask" in mat and "$envmapmask" not in mat and "$bumpmap" in mat:
            data["cosinePowerMap"] = textureDir + uniqueName(mat["$bumpmap"].strip()) + _ext

        if "$nocull" in mat:
            data["cullFace"] = "None"

        if "$surfaceprop" in mat:
            data["surfaceType"] = surfaceType(mat["$surfaceprop"].strip())["surface"]
        else:
            data["surfaceType"] = "<none>"

        if "$alphatest" in mat or "$alpha" in mat:
            data["alphaTest"] = "GE128"
        if "$translucent" in mat:
            data["blendFunc"] = "Blend"

        if "$basetexture2" in mat:
            data2 = {}
            data2["materialType"] = "world phong"
            data2["colorMap"] = textureDir + uniqueName(mat["$basetexture2"].strip()) + ext
            data2["blendFunc"] = "Blend"
            data2["usage"] = "tools"

            if "$bumpmap2" in mat and "$ssbump" not in mat:
                data2["normalMap"] = textureDir + uniqueName(mat["$bumpmap2"].strip()) + ext
            if "$envmapmask2" in mat:
                data["cosinePowerMap2"] = textureDir + uniqueName(mat["$envmapmask2"].strip()) + ext
            if "$basealphaenvmapmask2" in mat and "$envmapmask2" not in mat:
                data2["cosinePowerMap2"] = textureDir + uniqueName(mat["$basetexture2"].strip()) + _ext
            if "$normalmapalphaenvmapmask2" in mat and "$envmapmask2" not in mat and "$bumpmap2" in mat:
                data2["cosinePowerMap2"] = textureDir + uniqueName(mat["$bumpmap2"].strip()) + _ext

            if "$surfaceprop2" in mat:
                data2["surfaceType"] = surfaceType(mat["$surfaceprop2"].strip())["surface"]
            else:
                data2["surfaceType"] = "<none>"

            if "$alphatest" in mat or "$alpha" in mat:
                data2["alphaTest"] = "GE128"

            gdt.add(name.strip() + "_", "material", data2)

        gdt.add(name.strip(), "material", data)
    return gdt

def createMaterialGdtBo3(vmts: dict):
    gdt = Gdt()
    total = len(vmts.items())
    i = 0
    for name, vmt in vmts.items():
        print(f"{i}|{total}|done", end=""); i += 1;
        shader = list(vmt)[0]
        mat = vmt[shader]
        data = {}

        # these are default values and should stay the same unless the material requires more than a color map and a normal map
        data["materialCategory"] = "Geometry"
        data["materialType"] = "lit"

        if "$basetexture" in mat:
            data["colorMap"] = "i_" + uniqueName(mat["$basetexture"].strip())
        else:
            data["colorMap"] = "404.tif"
        data["usage"] = "tools" # probably not a good idea

        if "$bumpmap" in mat and "$ssbump" not in mat:
            data["normalMap"] = "i_" + uniqueName(mat["$bumpmap"].strip())
        if "$envmapmask" in mat:
            data["cosinePowerMap"] = "i_" + uniqueName(mat["$envmapmask"].strip())
            data["materialCategory"] = "Geometry Plus"
            data["materialType"] = "lit_plus"
        if "$basealphaenvmapmask" in mat and "$envmapmask" not in mat:
            data["cosinePowerMap"] = "i_" + uniqueName(mat["$basetexture"].strip()) + "_"
            data["materialCategory"] = "Geometry Plus"
            data["materialType"] = "lit_plus"
        if "$normalmapalphaenvmapmask" in mat and "$envmapmask" not in mat and "$bumpmap" in mat:
            data["cosinePowerMap"] = "i_" + uniqueName(mat["$bumpmap"].strip()) + "_"
            data["materialCategory"] = "Geometry Plus"
            data["materialType"] = "lit_plus"

        if "$surfaceprop" in mat:
            surfaceprop = surfaceType(mat["$surfaceprop"].strip())
            data["surfaceType"] = surfaceprop["surface"]
            if "cosinePowerMap" not in data:
                data["glossSurfaceType"] = surfaceprop["gloss"]
            else:
                data["glossSurfaceType"] = "<custom>"
        else:
            data["surfaceType"] = "<none>"
            data["glossSurfaceType"] = "<full>" if not "cosinePowerMap" in data else "<custom>"
        
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
                
        if "$selfillum" in mat:
            if mat["$selfillum"] == "1":
                data["materialType"] = "lit_emissive"

        if "$color" in mat:
            if mat["$color"].startswith("{"):
                data["colorTint"] = (Vector3FromStr(mat["$color"]) / 255).round(3)
            else:
                data["colorTint"] = Vector3FromStr(mat["$color"])

        if "$colortint" in mat:
            data["colorTint"] = mat["$colortint"]

        if "$layertint1" in mat:
            if mat["$layertint1"].startswith("{"):
                data["colorTint"] = (Vector3FromStr(mat["$layertint1"]) / 255).round(3)
            else:
                data["colorTint"] = Vector3FromStr(mat["$layertint1"])

        if "$basetexture2" in mat:
            data2 = {}
            data2["materialCategory"] = "Decal"
            data2["materialType"] = "lit_decal_reveal"

            data2["colorMap"] = "i_" + uniqueName(mat["$basetexture2"].strip())
            data2["usage"] = "tools" # probably not a good idea
                    
            if "$bumpmap2" in mat and "$ssbump2" not in mat:
                data2["normalMap"] = "i_" + uniqueName(mat["$bumpmap2"].strip())
            if "$blendmodulatetexture" in mat:
                data2["alphaRevealMap"] = "i_" + uniqueName(mat["$blendmodulatetexture"].strip())
            if "$envmapmask2" in mat:
                data2["cosinePowerMap2"] = "i_" + uniqueName(mat["$envmapmask2"].strip())
                data2["materialType"] = "lit_decal_reveal_plus"
            if "$basealphaenvmapmask2" in mat and "$envmapmask2" not in mat:
                data2["cosinePowerMap2"] = "i_" + uniqueName(mat["$basetexture2"].strip()) + "_"
                data2["materialType"] = "lit_decal_reveal_plus"
            if "$normalmapalphaenvmapmask2" in mat and "$envmapmask2" not in mat and "$bumpmap2" in mat:
                data2["cosinePowerMap"] = "i_" + uniqueName(mat["$bumpmap2"].strip()) + "_"
                data2["materialType"] = "lit_decal_reveal_plus"

            if "$surfaceprop2" in mat:
                surfaceprop = surfaceType(mat["$surfaceprop2"].strip())
                data2["surfaceType"] = surfaceprop["surface"]
                if "cosinePowerMap" not in data:
                    data2["glossSurfaceType"] = surfaceprop["gloss"]
                else:
                    data2["glossSurfaceType"] = "<custom>"
            else:
                data2["surfaceType"] = "<none>"
                data2["glossSurfaceType"] = "<full>" if not "cosinePowerMap" in data2 else "<custom>"

            if "$layertint2" in mat:
                if mat["$layertint2"].startswith("{"):
                    data2["colorTint"] = (Vector3FromStr(mat["$layertint2"]) / 255).round(3)
                else:
                    data2["colorTint"] = Vector3FromStr(mat["$layertint2"])            

            gdt.add(name.strip() + "_", "material", data2, "tinted" if "$colortint" in mat else "")
        
        gdt.add(name.strip(), "material", data)
    
    return gdt

def createModelGdt(models, BO3=False, modelTints={}):
    gdt = Gdt()
    total = len(models)
    i = 0
    for model in models:
        print(f"{i}|{total}|done", end=""); i += 1;
        name = splitext(basename(model))[0].lower()
        gdt.add("m_" + name, "xmodel", {
            "collisionLOD" if not BO3 else "BulletCollisionLOD": "High",
            "filename": f"corvid\\\\{name}." + ("xmodel_export" if not BO3 else "xmodel_bin"),
            "type": "rigid",
            "physicsPreset": "default"
        })
        if BO3 and name in modelTints:
            for tint in modelTints[name]:
                hex = rgbToHex(tint)
                gdt.add(f"{name}_{hex}", "xmodel", {
                    "collisionLOD" if not BO3 else "BulletCollisionLOD": "High",
                    "filename": f"corvid\\\\{name}_{hex}." + ("xmodel_export" if not BO3 else "xmodel_bin"),
                    "type": "rigid",
                    "physicsPreset": "default"
                }, "tinted")

    return gdt

def createImageGdt(images):
    gdt = Gdt()
    images["colorMaps"] = list(dict.fromkeys(images["colorMaps"]))
    images["colorMapsAlpha"] = list(dict.fromkeys(images["colorMapsAlpha"]))
    images["normalMaps"] = list(dict.fromkeys(images["normalMaps"]))
    images["envMaps"] = list(dict.fromkeys(images["envMaps"]))
    images["envMapsAlpha"] = list(dict.fromkeys(images["envMapsAlpha"]))
    images["revealMaps"] = list(dict.fromkeys(images["revealMaps"]))

    total = len(images["colorMaps"] + images["colorMapsAlpha"] + images["normalMaps"] + images["envMaps"] + images["envMapsAlpha"] + images["revealMaps"])
    i = 0

    for file in images["colorMaps"]:
        print(f"{i}|{total}|done", end=""); i += 1;
        file = uniqueName(file)
        gdt.add(f"i_{file}", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}.tif",
            "semantic": "diffuseMap",
            "compressionMethod": "compressed high color",
            "coreSemantic": "sRGB3chAlpha",
            "streamable": "1"
        })
    for file in images["colorMapsAlpha"]:
        print(f"{i}|{total}|done", end=""); i += 1;
        file = uniqueName(file)
        gdt.add(f"i_{file}", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}.tif",
            "semantic": "diffuseMap",
            "compressionMethod": "compressed high color",
            "coreSemantic": "sRGB3chAlpha",
            "streamable": "1"
        })
    for file in images["normalMaps"]:
        print(f"{i}|{total}|done", end=""); i += 1;
        file = uniqueName(file)
        gdt.add(f"i_{file}", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}.tif",
            "semantic": "normalMap",
            "compressionMethod": "compressed",
            "coreSemantic": "Normal",
            "streamable": "1"
        })
    for file in images["envMaps"]:
        print(f"{i}|{total}|done", end=""); i += 1;
        file = uniqueName(file)
        gdt.add(f"i_{file}", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}.tif",
            "semantic": "glossMap",
            "compressionMethod": "compressed",
            "coreSemantic": "Linear1ch",
            "streamable": "1"
        })
    for file in images["envMapsAlpha"]:
        print(f"{i}|{total}|done", end=""); i += 1;
        file = uniqueName(file)
        gdt.add(f"i_{file}_", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}_.tif",
            "semantic": "glossMap",
            "compressionMethod": "compressed",
            "coreSemantic": "Linear1ch",
            "streamable": "1"
        })
    for file in images["revealMaps"]:
        print(f"{i}|{total}|done", end=""); i += 1;
        file = uniqueName(file)
        gdt.add(f"i_{file}", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\{file}.tif",
            "semantic": "revealMap",
            "compressionMethod": "compressed",
            "coreSemantic": "Linear1ch",
            "streamable": "1"
        })
    return gdt

def exportSkybox(skyName: str, mapName: str, worldSpawnSettings, dir: SourceDir, BO3=False):
    skyName = skyName.lower()
    faces = ["up", "dn", "lf", "rt", "ft", "bk"]
    gdt = Gdt()
    ext = "tif" if BO3 else "tga"
    convertDir = f"{tempDir}/converted/texture_assets/corvid/"
    for face in faces:
        name = f"{mapName}_sky_{face}"
        dir.copy(f"materials/skybox/{skyName}{face}.vmt", f"{tempDir}/mat/{name}.vmt")
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
        convertImage(f"{tempDir}/matTex/{name}.vtf", f"{convertDir}/{name}.{ext}", format="rgb")
    if BO3:
        # convert cubemap images to an equirectangular image
        for face in faces:
            Image.open(f"{convertDir}/{mapName}_sky_{face}.tif").resize((1024, 1024)).save(f"{convertDir}/{mapName}_sky_{face}.tif")
        source = CubemapProjection()
        source.loadImages(
            f"{convertDir}/{mapName}_sky_ft.tif", f"{convertDir}/{mapName}_sky_rt.tif",
            f"{convertDir}/{mapName}_sky_bk.tif", f"{convertDir}/{mapName}_sky_lf.tif",
            f"{convertDir}/{mapName}_sky_up.tif", f"{convertDir}/{mapName}_sky_dn.tif"
        )
        output = EquirectangularProjection()
        output.initImage(4096, 2048)
        output.reprojectToThis(source)
        output.saveImage(f"{convertDir}/i_{mapName}_sky.tif")
        # create GDTs for the skybox assets
        gdt.add(f"i_{mapName}_sky", "image", {
            "imageType": "Texture",
            "type": "image",
            "baseImage": f"texture_assets\\\\corvid\\\\i_{mapName}_sky.tif",
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
            "filename": f"t6_props\\vista\\\\skybox\\\\t6_skybox.xmodel_bin",
            "type": "rigid",
            "skinOverride": f"mtl_skybox_default {mapName}_sky_mtl\\r\\n",
            "BulletCollisionLOD": "None"
        })
        gdt.add(f"{mapName}_ssi", "ssi", {
            "bounceCount": "4",
            "colorSRGB": f"{worldSpawnSettings['suncolor']} 1",
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
            "pitch": worldSpawnSettings['sundirection'].x,
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
            "yaw": worldSpawnSettings['sundirection'].y
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
            "colorMap": f"texture_assets\\\\corvid\\\\{mapName}_sky_ft.tga"
        })
    return gdt