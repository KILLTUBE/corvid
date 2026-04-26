import os
from os.path import splitext, exists
os.environ["NO_BPY"] = "1"
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from SourceIO.library.utils.pylib.vtf import load_vtf_texture
from glm import vec2
from .Static import newPath, VecFromStr, Vec2Str, Vec2Hex
from .ModelConverter import convertModel
from .Progress import Progress

def _load_gradient_vtf(vtf_data):
    """Load a BGR888 gradient texture from VTF data, reading the top mip directly.
    load_vtf_texture mishandles BGR888, so we parse the VTF header ourselves."""
    import struct
    width, height = struct.unpack_from('<HH', vtf_data, 16)
    # BGR888: 3 bytes per pixel, top mip is last in the file
    mip_size = width * height * 3
    raw = vtf_data[-mip_size:]
    bgr = np.frombuffer(raw, np.uint8).reshape(height, width, 3)
    return bgr[:, :, ::-1].copy(), width, height

def reconstructInfectedTexture(base_vtf, gradient_vtf, dest, clothRow=0, skinRow=0):
    """Reconstruct a diffuse texture from the L4D2 Infected shader's inputs.
    The $basetexture alpha channel indexes into the $gradienttexture horizontally.
    The blue channel separates clothing (0-127) from skin (128-255).
    The gradient texture is 256x16: rows 0-7 are clothing, rows 8-15 are skin.
    $colortintgradient and $skintintgradient are absolute row indices (0-15)."""
    if base_vtf is None or gradient_vtf is None:
        return False

    # load basetexture
    px, w, h, is_f = load_vtf_texture(base_vtf)
    if is_f:
        base = (np.clip(np.frombuffer(px, np.float32).reshape(h, w, 4), 0, 1) * 255).astype(np.uint8)
    else:
        base = np.frombuffer(px, np.uint8).reshape(h, w, 4).copy()

    # load gradient texture (BGR888 — parsed manually to avoid SourceIO bug)
    grad, gw, gh = _load_gradient_vtf(gradient_vtf)

    alpha = base[:, :, 3]  # luminosity / gradient X coordinate
    blue = base[:, :, 2]   # cloth vs skin mask

    # scale alpha to gradient width
    x_coords = (alpha.astype(np.float32) / 255.0 * (gw - 1)).astype(np.int32)

    # $colortintgradient and $skintintgradient are absolute row indices (0-15)
    cloth_y = min(clothRow, gh - 1)
    skin_y = min(skinRow, gh - 1)

    cloth_color = grad[cloth_y, x_coords, :3]
    skin_color = grad[skin_y, x_coords, :3]

    # blue < 128 = clothing, blue >= 128 = skin
    skin_mask = (blue >= 128)[:, :, np.newaxis]
    result = np.where(skin_mask, skin_color, cloth_color)

    Image.fromarray(result, "RGB").save(dest)
    return True

_SSBUMP_BASIS_T = np.array([
    [0.81649661064147949, -0.40824833512306213, -0.40824833512306213],
    [0.0,                  0.70710676908493042, -0.70710682868957520],
    [0.57735025882720947,  0.57735025882720947,  0.57735025882720947],
], dtype=np.float32)

def convertImage(vtf_data, dest, format="rgba", invert=False, resize=False, removeBg=False, ssbump=False):
    if vtf_data is None:
        return False
    format = format.upper()
    pixel_data, width, height, is_float = load_vtf_texture(vtf_data)
    if is_float:
        rgba_arr = np.frombuffer(pixel_data, dtype=np.float32).reshape(height, width, 4)
        rgba_arr = (np.clip(rgba_arr, 0, 1) * 255).astype(np.uint8)
    else:
        rgba_arr = np.frombuffer(pixel_data, dtype=np.uint8).reshape(height, width, 4).copy()
    if ssbump:
        # Source SSBump → tangent-space normal: project the per-pixel basis weights
        # onto the SSBump basis (rob5300/ssbumpToNormal), remap [-1,1] → [0,1].
        rgb_f = rgba_arr[:, :, :3].astype(np.float32) / 255.0
        rgb_f = rgb_f @ _SSBUMP_BASIS_T.T
        rgb_f = np.clip(rgb_f * 0.5 + 0.5, 0.0, 1.0)
        rgba_arr[:, :, :3] = (rgb_f * 255.0).astype(np.uint8)
    rgba = Image.fromarray(rgba_arr, "RGBA")
    if rgba.size[0] < 4 or rgba.size[1] < 4:
        x = max(rgba.size[0], 4)
        y = max(rgba.size[1], 4)
        rgba = rgba.resize((x, y))
    if resize:
        if isinstance(resize, tuple):
            rgba = rgba.resize(resize)
        else:
            rgba = rgba.resize((512, 512))
    if invert:
        rgba = ImageOps.invert(rgba.convert("RGB"))
    if removeBg:
        rgba = removeBackground(rgba)
    if format == "RGBA":
        rgba.save(dest)
    elif format == "RGB":
        rgba.convert("RGB").save(dest)
    elif len(format) == 1:
        rgba.getchannel(format).save(dest)

def removeBackground(rgba):
    """Detects a solid background color from edge pixels and replaces it with alpha.
    Recovers original colors by removing background contamination from blended pixels."""
    arr = np.array(rgba)[:, :, :3]
    # sample corner pixels (5x5 patches) to detect solid background
    h, w = arr.shape[:2]
    cs = min(5, h // 2, w // 2)
    corners = np.concatenate([
        arr[:cs, :cs].reshape(-1, 3),
        arr[:cs, -cs:].reshape(-1, 3),
        arr[-cs:, :cs].reshape(-1, 3),
        arr[-cs:, -cs:].reshape(-1, 3),
    ])
    # check if corners are uniform (solid background)
    # near-grayscale corners (R≈G≈B) get a looser uniformity threshold,
    # so noisy gray backgrounds still get stripped regardless of brightness
    bg = corners.mean(axis=0).astype(np.float32)
    std_limit = 8 if (bg.max() - bg.min()) < 5 else 2
    if corners.std(axis=0).max() > std_limit:
        return rgba
    # compute color distance from background and use as alpha
    pixels = np.array(rgba)[:, :, :3].astype(np.float32)
    dist = np.sqrt(((pixels - bg) ** 2).sum(axis=2))
    alpha_f = np.clip(dist / 64.0, 0.0, 1.0)
    # recover original color by removing background contribution
    # blended = bg * (1 - a) + original * a  =>  original = (blended - bg * (1 - a)) / a
    safe_alpha = np.maximum(alpha_f, 0.01)
    recovered = (pixels - bg[None, None, :] * (1.0 - safe_alpha[:, :, None])) / safe_alpha[:, :, None]
    recovered = np.clip(recovered, 0, 255).astype(np.uint8)
    result = np.array(rgba)
    result[:, :, :3] = np.where(alpha_f[:, :, None] > 0, recovered, 0)
    result[:, :, 3] = (alpha_f * 255).astype(np.uint8)
    return Image.fromarray(result, "RGBA")

def convertImages(images, outDir, ext="tga", overlayTextures=None, progress: Progress=None):
    if progress is None:
        progress = Progress()
    vtf_data = images["vtfData"]
    if overlayTextures is None:
        overlayTextures = set()

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
        progress.current(i + 1, total)
        convertImage(vtf_data.get(file), f"{outDir}/{file}.{ext}", "rgba")
    ssbumpMaps = images.get("ssbumpMaps", set())
    for i, file in enumerate(images["normalMaps"], lencolorMapsAlpha):
        progress.current(i + 1, total)
        convertImage(vtf_data.get(file), f"{outDir}/{file}.{ext}", "rgb", ssbump=(file in ssbumpMaps))
    for i, file in enumerate(images["envMaps"], lencolorMapsAlpha + lennormalMaps):
        progress.current(i + 1, total)
        convertImage(vtf_data.get(file), f"{outDir}/{file}.{ext}", "rgb")
    for i, file in enumerate(images["envMapsAlpha"], lencolorMapsAlpha + lennormalMaps + lenenvMaps):
        progress.current(i + 1, total)
        convertImage(vtf_data.get(file), f"{outDir}/{file}_.{ext}", "a")
    for i, file in enumerate(images["revealMaps"], lencolorMapsAlpha + lennormalMaps + lenenvMaps + lenenvMapsAlpha):
        progress.current(i + 1, total)
        convertImage(vtf_data.get(file), f"{outDir}/{file}.{ext}", "g", True)
    infected = images.get("infected", {})
    for i, file in enumerate(images["colorMaps"], lencolorMapsAlpha + lennormalMaps + lenenvMaps + lenenvMapsAlpha + lenrevealMaps):
        progress.current(i + 1, total)
        if file in infected:
            info = infected[file]
            reconstructInfectedTexture(
                vtf_data.get(file),
                vtf_data.get(info["gradient"]),
                f"{outDir}/{file}.{ext}",
                clothRow=info["clothRow"],
                skinRow=info["skinRow"],
            )
        elif file in overlayTextures:
            convertImage(vtf_data.get(file), f"{outDir}/{file}.{ext}", "rgba", removeBg=True)
        else:
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

def convertModels(models, modelData, modelTints, modelSkins, skinTints, materialNames, game="WaW", scale=1.0, outDir="", progress: Progress=None):
    if progress is None:
        progress = Progress()
    convertDir = f"{outDir}/model_export/corvid"
    total = len(models)

    for i, model in enumerate(models):
        progress.current(i + 1, total)
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
