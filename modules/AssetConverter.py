import os
from os.path import splitext, exists
os.environ["NO_BPY"] = "1"
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from SourceIO.library.utils.pylib.vtf import load_vtf_texture
from glm import vec2
from .Static import newPath, VecFromStr, Vec2Str, Vec2Hex
from .ModelConverter import convertModel

def convertImage(vtf_data, dest, format="rgba", invert=False, resize=False):
    if vtf_data is None:
        return False
    format = format.upper()
    pixel_data, width, height, is_float = load_vtf_texture(vtf_data)
    if is_float:
        rgba_arr = np.frombuffer(pixel_data, dtype=np.float32).reshape(height, width, 4)
        rgba_arr = (np.clip(rgba_arr, 0, 1) * 255).astype(np.uint8)
    else:
        rgba_arr = np.frombuffer(pixel_data, dtype=np.uint8).reshape(height, width, 4)
    rgba = Image.fromarray(rgba_arr, "RGBA")
    if rgba.size[0] < 4 or rgba.size[1] < 4:
        x = max(rgba.size[0], 4)
        y = max(rgba.size[1], 4)
        rgba = rgba.resize((x, y))
    if resize:
        rgba = rgba.resize((512, 512))
    if invert:
        rgba = ImageOps.invert(rgba.convert("RGB"))
    if format == "RGBA":
        rgba.save(dest)
    elif format == "RGB":
        rgba.convert("RGB").save(dest)
    elif len(format) == 1:
        rgba.getchannel(format).save(dest)

def convertImages(images, outDir, ext="tga"):
    vtf_data = images["vtfData"]

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

    for i, file in enumerate(images["colorMapsAlpha"]):
        print(f"{i}|{total}|done", end="")
        convertImage(vtf_data.get(file), f"{outDir}/{file}.{ext}", "rgba")
    for i, file in enumerate(images["normalMaps"], lencolorMapsAlpha):
        print(f"{i}|{total}|done", end="")
        convertImage(vtf_data.get(file), f"{outDir}/{file}.{ext}", "rgb")
    for i, file in enumerate(images["envMaps"], lencolorMapsAlpha + lennormalMaps):
        print(f"{i}|{total}|done", end="")
        convertImage(vtf_data.get(file), f"{outDir}/{file}.{ext}", "rgb")
    for i, file in enumerate(images["envMapsAlpha"], lencolorMapsAlpha + lennormalMaps + lenenvMaps):
        print(f"{i}|{total}|done", end="")
        convertImage(vtf_data.get(file), f"{outDir}/{file}_.{ext}", "a")
    for i, file in enumerate(images["revealMaps"], lencolorMapsAlpha + lennormalMaps + lenenvMaps + lenenvMapsAlpha):
        print(f"{i}|{total}|done", end="")
        convertImage(vtf_data.get(file), f"{outDir}/{file}.{ext}", "g", True)
    for i, file in enumerate(images["colorMaps"], lencolorMapsAlpha + lennormalMaps + lenenvMaps + lenenvMapsAlpha + lenrevealMaps):
        print(f"{i}|{total}|done", end="")
        convertImage(vtf_data.get(file), f"{outDir}/{file}.{ext}", "rgb")

    # create 404 image for the textures that aren't found
    h = 512
    w = 512
    img = Image.new("RGB", (h,w), (255, 0, 0))
    pixels = img.load()

    col1, col2 = (255, 0, 255), (0, 255, 0)

    box_size = 64
    for i in range (0, h, box_size):
        for j in range(0, w, box_size):
            y, x = i // box_size, j // box_size
            if (y&1)^(x&1):
                for di in range(box_size):
                    for dj in range(box_size):
                        pixels[i+di,j+dj] = col1
            else:
                for di in range(box_size):
                    for dj in range(box_size):
                        pixels[i+di,j+dj] = col2

    draw = ImageDraw.Draw(img)
    draw.text((62, 206), "TEXTURE NOT FOUND", (255, 255, 255), font=ImageFont.truetype("impact.ttf", 50))
    img.save(f"{outDir}/404.{ext}")

def getTexSize(vtf_data):
    pixel_data, width, height, is_float = load_vtf_texture(vtf_data)
    return vec2(width, height)

def convertModels(models, modelData, modelTints, modelSkins, skinTints, materialNames, game="WaW", scale=1.0, outDir=""):
    convertDir = f"{outDir}/model_export/corvid"
    total = len(models)

    for i, model in enumerate(models):
        print(f"{i}|{total}|done", end="")
        model = splitext(newPath(model))[0]
        if model not in modelData:
            continue
        data = modelData[model]
        # convert models with tints
        if game == "BO3" and model in modelTints:
            for tint in modelTints[model]:
                hex = Vec2Hex(VecFromStr(tint, 3))
                convertModel(data, convertDir, materialNames, tint=hex, scale=scale, game=game)
        convertModel(data, convertDir, materialNames, scale=scale, game=game)

        # convert models with skins
        if model in modelSkins:
            for skin in modelSkins[model]:
                convertModel(data, convertDir, materialNames, skin=skin, scale=scale, game=game)

        if game == "BO3" and model in skinTints:
            for skin, tints in skinTints[model].items():
                for tint in tints:
                    hex = Vec2Hex(VecFromStr(tint, 3))
                    convertModel(data, convertDir, materialNames, hex, skin, scale, game=game)
