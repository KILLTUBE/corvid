import numpy as np
import os
os.environ["NO_BPY"] = "1"
from mathutils import Vector
from pathlib import Path
from typing import List
from os.path import basename, exists
from Libs.SourceIO.source1.mdl.mdl_file import Mdl
from Libs.SourceIO.source1.vtx.vtx import Vtx
from Libs.SourceIO.source1.vvd.vvd import Vvd
from Formats.BaseMap.Model import Group, Model

def merge_strip_groups(vtx_mesh):
    indices_accumulator = []
    vertex_accumulator = []
    vertex_offset = 0
    for strip_group in vtx_mesh.strip_groups:
        indices_accumulator.append(np.add(strip_group.indexes, vertex_offset))
        vertex_accumulator.append(strip_group.vertexes['original_mesh_vertex_index'].reshape(-1))
        vertex_offset += sum(strip.vertex_count for strip in strip_group.strips)
    return np.hstack(indices_accumulator), np.hstack(vertex_accumulator), vertex_offset

def get_slice(data, start, count=None):
    if count is None:
        count = len(data) - start
    return data[start:start + count]

def merge_meshes(model, vtx_model):
    vtx_vertices = []
    acc = 0
    mat_arrays = []
    indices_array = []
    for n, (vtx_mesh, mesh) in enumerate(zip(vtx_model.meshes, model.meshes)):

        if not vtx_mesh.strip_groups:
            continue

        vertex_start = mesh.vertex_index_start
        indices, vertices, offset = merge_strip_groups(vtx_mesh)
        indices = np.add(indices, acc)
        mat_array = np.full(indices.shape[0] // 3, mesh.material_index)
        mat_arrays.append(mat_array)
        vtx_vertices.extend(np.add(vertices, vertex_start))
        indices_array.append(indices)
        acc += offset

    return vtx_vertices, np.hstack(indices_array), np.hstack(mat_arrays)

class SourceModel(Model):
    __slots__ = ("materialPaths", "skinGroups", "surfaceProp")

    materialPaths: List[str]
    skinGroups: List[List[str]]
    surfaceProp: str

    def __init__(self) -> None:
        super().__init__()

        self.materialPaths = []
        self.skinGroups = []
        self.surfaceProp = None

    @staticmethod
    def Load(path: str) -> 'SourceModel':
        FixPath = lambda x: Path(x).as_posix().strip().lower()
        res = SourceModel()
        mdl = Mdl(f"{path}.mdl")
        mdl.read()

        # most materials used by models don't have the $surfaceprop property, because the game uses the one defined in the mdl
        res.surfaceProp = mdl.header.surface_prop.lower()

        vtx: Vtx = None

        if exists(f"{path}.dx90.vtx"):
            vtx = Vtx(f"{path}.dx90.vtx")
            vtx.read()

        elif exists(f"{path}.vtx"):
            vtx = Vtx(f"{path}.dx90.vtx")
            vtx.read()

        else:
            print(f"Can't find vtx file for the model {basename(path)}.mdl. Skipping...")
            return None
        
        vvd = Vvd(f"{path}.vvd")
        vvd.read()

        for material in mdl.materials:
            res.materials.append(FixPath(material.name))

        for materialPath in mdl.materials_paths:
            res.materialPaths.append(FixPath(materialPath))
        
        for group in mdl.skin_groups:
            res.skinGroups.append([FixPath(mat) for mat in group])

        desired_lod = 0
        all_vertices = vvd.lod_data[desired_lod]

        groupCount = 0

        for mdl_parts, vtx_parts in zip(mdl.body_parts, vtx.body_parts):
            for vtx_model, model in zip(vtx_parts.models, mdl_parts.models):
                if model.vertex_count == 0:
                    continue

                res.groups.append(Group(f"CorvidModel_{groupCount}"))

                model_vertices = get_slice(all_vertices, model.vertex_offset, model.vertex_count)
                vtx_vertices, indices_array, material_indices_array = merge_meshes(model, vtx_model.model_lods[desired_lod])

                indices_array = np.array(indices_array, dtype=np.uint32)
                vertices = model_vertices[vtx_vertices]

                res.groups[groupCount].vertices.extend([Vector([float(i) for i in v]) for v in vertices["vertex"]])
                res.groups[groupCount].uvs.extend([Vector([float(i) for i in uv]) for uv in vertices["uv"]])
                res.groups[groupCount].normals.extend([Vector([float(i) for i in n]) for n in vertices["normal"]])

                for i in range(0, len(indices_array), 3):
                    res.groups[groupCount].faces.append((
                        material_indices_array[int(i / 3)],
                        (indices_array[i], indices_array[i], indices_array[i]),
                        (indices_array[i + 2], indices_array[i + 2], indices_array[i + 2]),
                        (indices_array[i + 1], indices_array[i + 1], indices_array[i + 1])
                    ))

                groupCount += 1

        return res