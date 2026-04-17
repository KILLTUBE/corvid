import struct
import zipfile
from io import BytesIO

import vpk
from typing import List
from os import walk
from os.path import isdir, isfile, relpath
from shutil import copyfile
from pathlib import Path
from tempfile import gettempdir
from .Gma import Addon, load as loadGma

_BSP_PAK_LUMP_INDEX = 40

def _read_bsp_pak(path):
    """Read the PAK lump (ZIP archive) from a BSP file."""
    with open(path, "rb") as f:
        magic = f.read(4)
        if magic != b"VBSP":
            print(f'"{path}" is not a valid BSP file.')
            return None
        f.read(4)  # version
        # Each lump header: offset(4) + length(4) + version(4) + fourCC(4) = 16 bytes
        f.seek(8 + _BSP_PAK_LUMP_INDEX * 16)
        offset, length = struct.unpack("<II", f.read(8))
        if length == 0:
            return None
        f.seek(offset)
        zip_data = BytesIO(f.read(length))
    try:
        return zipfile.ZipFile(zip_data)
    except zipfile.BadZipFile:
        print(f'PAK lump in "{path}" is not a valid ZIP archive.')
        return None

class _BspPak:
    """Lightweight wrapper around a ZipFile from a BSP's PAK lump."""
    def __init__(self, zip_file: zipfile.ZipFile, source_path: str):
        self.zip_file = zip_file
        self.source_path = source_path
        self.map_name = Path(source_path).stem.lower()
        self._cache = {name.replace("\\", "/").lower(): name
                       for name in zip_file.namelist()}

    def read(self, filepath: str):
        original = self._cache.get(filepath)
        if original is not None:
            return self.zip_file.read(original)
        return None

    def read_wvt_fallback(self, material: str):
        """Try to find a _wvt_patch VMT for a missing material.
        material should be e.g. 'de_santorini/cleantoneblend_50' (no 'materials/' prefix, no extension)."""
        key = f"materials/maps/{self.map_name}/{material}_wvt_patch.vmt"
        return self.read(key)

class SourceDir:
    def __init__(self):
        self.dirs = []
        self.paks: List[vpk.VPK] = []
        self.addons: List[Addon] = []
        self.bspPaks: List[_BspPak] = []
        self._file_index = {} # lowercase relative path -> actual full path

    def add(self, path):
        if isfile(path):
            if not path.endswith((".vpk", ".gma", ".bsp")):
                print(f"\"{path}\" is not a valid file.")
                return
            if path.endswith(".vpk"):
                self.paks.append(vpk.open(path))
            elif path.endswith(".gma"):
                self.addons.append(loadGma(path))
            elif path.endswith(".bsp"):
                zf = _read_bsp_pak(path)
                if zf is not None:
                    self.bspPaks.append(_BspPak(zf, path))

        elif isdir(path):
            self.dirs.append(path)
            for root, dirs, files in walk(path):
                for f in files:
                    full = f"{root}/{f}"
                    rel = relpath(full, path).replace("\\", "/").lower()
                    if rel not in self._file_index:
                        self._file_index[rel] = full
        else:
            print(f"\"{path}\" is an invalid path.")

    def read_bytes(self, src, silent=False):
        src = Path(src.replace("\\", "/")).as_posix().lower()
        for pak in self.paks:
            try:
                return pak.get_file(src).read()
            except:
                continue

        for addon in self.addons:
            if src in addon.entries:
                tmpPath = f"{gettempdir()}/corvid_addon_tmp"
                addon.entries[src].save(tmpPath)
                with open(tmpPath, "rb") as f:
                    return f.read()

        for bsp in self.bspPaks:
            data = bsp.read(src)
            if data is not None:
                return data

        resolved = self._file_index.get(src)
        if resolved is not None:
            try:
                with open(resolved, "rb") as f:
                    return f.read()
            except:
                pass

        if not silent:
            print(f"Could not find file {src}")
        return None

    def read_text(self, src, silent=False):
        data = self.read_bytes(src, silent)
        if data is not None:
            return data.decode("utf-8", errors="replace")
        return None

    def read_wvt_fallback(self, material):
        """Try to find a _wvt_patch VMT from BSP paks for a missing material."""
        for bsp in self.bspPaks:
            data = bsp.read_wvt_fallback(material)
            if data is not None:
                return data.decode("utf-8", errors="replace")
        return None
