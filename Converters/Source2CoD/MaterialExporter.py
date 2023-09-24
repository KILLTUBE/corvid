import os
os.environ["NO_BPY"] = "1"
from os.path import exists
from typing import Dict, List, Tuple
from PIL import Image, ImageOps
from Formats.CoD.Gdt import Gdt, GdtEntry
from Formats.Source.Material import Material
from Libs.SourceIO.source1.vtf.VTFWrapper.VTFLib import VTFLib
from Helpers.FileHelpers import GetTempDir, NewPath

def GetSurfaceType(surface: str) -> str:
    """
    Fetches the most appropriate surface type based on the $surfaceprop property in a VMT file.
    """

    surface = surface.lower()

    surfaces = {
        "default": "plaster", "default_silent": "plaster", "floatingstandable": "plaster", "item": "plastic", "ladder": "metal",
        "no_decal": "plastic", "baserock": "rock", "boulder": "rock", "brick": "brick", "concrete": "concrete",
        "concrete_block": "concrete", "gravel": "gravel", "rock": "rock", "canister": "metal", "chain": "metal", "chainlink": "metal",
        "combine_metal": "metal", "crowbar": "metal", "floating_metal_barrel": "metal", "grenade": "metal", "gunship": "metal",
        "metal": "metal", "metal_barrel": "metal", "metal_bouncy": "metal", "metal_box": "metal", "metal_seafloorcar": "metal",
        "metalgrate": "metal", "metalpanel": "metal", "metalvent": "metal", "metalvehicle": "metal", "paintcan": "metal",
        "popcan": "metal", "roller": "metal", "slipperymetal": "metal", "solidmetal": "metal", "strider": "metal",
        "weapon": "metal", "wood": "wood", "wood_box": "wood", "wood_crate": "wood", "wood_furniture": "wood",
        "wood_lowdensity": "wood", "wood_plank": "wood", "wood_panel": "wood", "wood_solid": "wood", "dirt": "dirt",
        "grass": "grass", "mud": "mud", "quicksand": "sand", "sand": "sand", "slipperyslime": "mud", "antlionsand": "sand",
        "slime": "mud", "water": "water", "wade": "water", "puddle": "water", "ice": "ice", "snow": "snow", "alienflesh": "flesh",
        "antlion": "flesh", "armorflesh": "flesh", "bloodyflesh": "flesh", "flesh": "flesh", "foliage": "foliage", "watermelon": "fruit",
        "zombieflesh": "flesh", "asphalt": "asphalt", "glass": "glass", "glassbottle": "glass", "combine_glass": "glass",
        "tile": "ceramic", "paper": "paper", "papercup": "paper", "cardboard": "paper", "plaster": "plaster",
        "plastic_barrel": "plastic", "plastic_barrel_buoyant": "plastic", "plastic_box": "plastic", "plastic": "plastic",
        "rubber": "plastic", "rubbertire": "plastic", "slidingrubbertire": "plastic", "slidingrubbertire_front": "plastic",
        "slidingrubbertire_rear": "plastic", "jeeptire": "plastic", "brakingrubbertire": "plastic", "carpet": "carpet",
        "ceiling_tile": "ceramic", "computer": "plastic", "pottery": "brick"
    }

    return surfaces.get(surface, "<none>")

def GetGlossRange(surface: str):
    """
    Determines gloss range based on material's surface type.
    Since the materials in Source games are made for old gen renderers, we need to set proper gloss range values to make them look good in Black Ops 3's PBR renderer.
    """

    glossRanges = {
        "asphalt": (0.0, 4.0), "brick": (0.0, 4.0), "carpet": (0.0, 2.0),"ceramic": (0.0, 17.0), "cloth": (0.0, 4.0),
        "concrete": (0.0, 4.0),"dirt": (0.0, 4.0), "skin": (2.0, 10.0), "foliage": (0.0, 6.5), "glass": (6.0, 17.0), "gravel": (0.0, 4.0),
        "ice": (4.0, 17.0), "metal": (0.0, 17.0), "mud": (4.0, 13.0), "paint": (2.0, 7.0), "paper": (0.0, 2.0),
        "plaster": (0.0, 2.0), "plastic": (4.0, 13.0), "rock": (0.0, 4.0), "rubber": (0.0, 4.0),
        "sand": (2.0, 8.0), "snow": (4.0, 12.0), "water": (6.0, 17.0), "wood": (2.0, 5.0), "bark": (0.0, 4.0)
    }

    return glossRanges.get(surface, (0.0, 17.0))

def CreateMaterialGdt(materials: Dict[str, Material], options: dict={}):
    """
    Creates a GDT object for materials to be used in older CoD games.
    """

    if "TargetGame" in options and options["TargetGame"] == "BO3":
        return CreateMaterialGdtBo3(materials)

    res = Gdt()

    if "TargetGame" in options and options["TargetGame"] == "CoD2":
        res.CoD2 = True

    # not all surface types that exist in later CoD games exist in CoD2
    # so we need to filter the ones that don't
    CoD2SurfaceTypes = [
        "<none>", "asphalt", "bark", "brick", "carpet", "cloth", "concrete", "dirt", "flesh", "foliage",
        "glass", "grass", "gravel", "ice", "metal", "mud", "paper", "plaster", "rock", "sand", "snow", "water", "wood"
    ]

    texturePath = "texture_assets\\\\Corvid\\\\"

    shaders = {
        "lightmappedgeneric": "world phong",
        "worldvertextransition": "world phong",
        "unlitgeneric": "world unlit",
        "vertexlitgeneric": "model phong",
    }
    
    for name, material in materials.items():
        data = {}

        data["materialType"] = shaders.get(material.shader, "world phong")

        if "$basetexture" in material:
            data["colorMap"] = texturePath + NewPath(material["$basetexture"], shorten=True) + ".tga"
        else:
            data["colorMap"] = f"{texturePath}404.tga"
        
        if "$bumpmap" in material and "$ssbump" not in material:
            data["normalMap"] = texturePath + NewPath(material["$bumpmap"], shorten=True) + ".tga"
        
        if "$envmapmask" in material:
            data["cosinePowerMap"] = texturePath + NewPath(material["$envmapmask"], shorten=True) + ".tga"
        
        if "$basealphaenvmapmask" in material and "$envmapmask" not in material:
            data["cosinePowerMap"] = texturePath + NewPath(material["$basetexture"], shorten=True) + "_env.tga"
        elif "$normalmapalphaenvmapmask" in material and "$envmapmask" not in material and "$bumpmap" in material:
            data["cosinePowerMap"] = texturePath + NewPath(material["$bumpmap"], shorten=True) + "_env.tga"

        if "$surfaceprop" in material:
            data["surfaceType"] = GetSurfaceType(material["$surfaceprop"])
        else:
            data["surfaceType"] = "<none>"
        
        if "TargetGame" in options and options["TargetGame"] == "CoD2":
            data["surfaceType"] = data["surfaceType"] if data["surfaceType"] in CoD2SurfaceTypes else "<none>"

        if "$nocull" in material:
            data["cullFace"] = "None"

        if "$alphatest" in material or "$alpha" in material:
            data["alphaTest"] = "GE128"
        if "$translucent" in material:
            data["blendFunc"] = "Blend"

        if "$decal" in material:
            data["sort"] = "decal - static decal"
            data["polygonOffset"] = "Static Decal"
            data["locale_decal"] = "1"

        res.entries[name] = GdtEntry(name, "material", data)

        if "$basetexture2" in material: # if the material has another color map we can blend it with
            data2 = {}
            data2["materialType"] = data["materialType"]
            data2["colorMap"] = texturePath + NewPath(material["$basetexture2"], shorten=True) + ".tga"
            
            if "$bumpmap2" in material and "$ssbump2" not in material:
                data2["normalMap"] = texturePath + NewPath(material["$bumpmap2"], shorten=True) + ".tga"
            
            if "$envmapmask2" in material:
                data2["cosinePowerMap"] = texturePath + NewPath(material["$envmapmask2"], shorten=True) + ".tga"
            
            if "$basealphaenvmapmask2" in material and "$envmapmask2" not in material:
                data2["cosinePowerMap"] = texturePath + NewPath(material["$basetexture2"], shorten=True) + "_env.tga"
            elif "$normalmapalphaenvmapmask2" in material and "$envmapmask2" not in material and "$bumpmap2" in material:
                data2["cosinePowerMap"] = texturePath + NewPath(material["$bumpmap2"], shorten=True) + "_env.tga"
            
            if "$alphatest" in material or "$alpha" in material:
                data2["alphaTest"] = "GE128"
            
            data2["surfaceType"] = data["surfaceType"]

            res.entries[name + "_blend"] = GdtEntry(name + "_blend", "material", data2)

    return res

def CreateMaterialGdtBo3(materials: Dict[str, Material]):
    res = Gdt()

    return res

def ConvertTexture(src: str, dest: str, alpha: bool=False, invert: bool=False, channel: str=None, resize: Tuple[int, int]=None):
    if not exists(src):
        print(f"{src} could not be found.")
        return

    IsPowOf2 = lambda n: (n & (n-1) == 0) and n != 0
    NearestPow = lambda n: 1 << (n - 1).bit_length()

    # load VTFLib    
    image = VTFLib()

    # load the VTF file and then create an image with its pixel data
    image.image_load(src)
    rgba = Image.frombuffer("RGBA", (image.width(), image.height()), image.convert_to_rgba8888().contents)

    # make sure the image's dimensions are powers of two
    if not IsPowOf2(rgba.size[0]) or not IsPowOf2(rgba.size[1]):
        size = (NearestPow(rgba.size[0]), NearestPow(rgba.size[1]))
        rgba = rgba.resize(size)

    # CoD does not accept images smaller than 4x4
    if rgba.size[0] < 4 or rgba.size[1] < 4:
        size = (max(rgba.size[0], 4), max(rgba.size[0], 4))
        rgba = rgba.resize(size)
    
    if resize is not None:
        rgba = rgba.resize(resize)
    
    if invert:
        rgba = ImageOps.invert(rgba.convert("RGB"))

    if channel is not None:
        rgba.getchannel(channel).save(dest)
        return

    if not alpha:
        rgba.convert("RGB").save(dest)
    else:
        rgba.save(dest)

def ConvertTextures(textures: Tuple[List[str], ...], exportPath, ext="tga"):
    tempDir = GetTempDir()

    if len(textures) == 5:
        colorMaps, colorMapsAlpha, normalMaps, envMaps, envMapsInAlpha = textures
        blendMaps = []

    else:
        colorMaps, colorMapsAlpha, normalMaps, envMaps, envMapsInAlpha, blendMaps = textures

    for texture in colorMaps:
        ConvertTexture(f"{tempDir}/textures/{texture}.vtf", f"{exportPath}/texture_assets/Corvid/{texture}.{ext}")

    for texture in colorMapsAlpha:
        ConvertTexture(f"{tempDir}/textures/{texture}.vtf", f"{exportPath}/texture_assets/Corvid/{texture}.{ext}", alpha=True)

    for texture in normalMaps:
        ConvertTexture(f"{tempDir}/textures/{texture}.vtf", f"{exportPath}/texture_assets/Corvid/{texture}.{ext}")

    for texture in envMaps:
        ConvertTexture(f"{tempDir}/textures/{texture}.vtf", f"{exportPath}/texture_assets/Corvid/{texture}.{ext}")

    for texture in envMapsInAlpha:
        ConvertTexture(f"{tempDir}/textures/{texture}.vtf", f"{exportPath}/texture_assets/Corvid/{texture}_env.{ext}", channel="A")

    for texture in blendMaps:
        ConvertTexture(f"{tempDir}/textures/{texture}.vtf", f"{exportPath}/texture_assets/Corvid/{texture}.{ext}", invert=True, channel="G")
