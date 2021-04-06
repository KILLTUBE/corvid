from modules.Vector3 import Vector3
from modules.Vector2 import Vector2 

class Smd:
    def __init__(self, smdString):
        self.joints = []
        self.frames = []
        self.triangles = []
        self.materials = []
        self.vertices = []
        self.normals = []
        
        self.parse(smdString)

    def parse(self, smdString: str):
        lines: str = smdString.split("\n")

        NONE, NODES, SKELETON , TRIANGLES, VERTEXANIMATION = 0, 1, 2, 3, 4
        current = NONE

        material = ""

        for i in range(len(lines)):
            line = lines[i].strip()
            if line.startswith("//") or line == "version 1":
                continue
            elif line == "nodes":
                if current == NONE:
                    current = NODES
                    continue
                else:
                    print(f"Unexpected '{line}' on line {i}"); exit()
            elif line == "skeleton":
                if current == NONE:
                    current = SKELETON
                    continue
                else:
                    print(f"Unexpected '{line}' on line {i}"); exit()
            elif line == "vertexanimation":
                if current == NONE:
                    current = VERTEXANIMATION
                    continue
                else:
                    print(f"Unexpected '{line}' on line {i}"); exit()
            elif line.startswith("time"):
                if current == SKELETON:
                    continue
                elif current == VERTEXANIMATION:
                    continue
                else:
                    print(f"Unexpected '{line}' on line {i}"); exit()
            elif line.startswith("triangles"):
                if current == NONE:
                    current = TRIANGLES
                    continue
                else:
                    print(f"Unexpected '{line}' on line {i}"); exit()
            elif line == "end":
                if current == NODES or current == SKELETON or current == TRIANGLES:
                    current = NONE
                    continue
                else:
                    print(f"Unexpected '{line}' on line {i}"); exit()
            
            # parse the data
            if current == NODES:
                # id name parent
                tok = line.split(" ")
                self.joints.append({
                    "id": int(tok[0]),
                    "name": tok[1][1:-1],
                    "parent": int(tok[2])
                })
            elif current == SKELETON:
                continue
            elif current == VERTEXANIMATION:
                continue
            elif current == TRIANGLES:
                tok = line.split(" ")
                if len(tok) == 1:
                    material = line.lower()
                    if material not in self.materials:
                        self.materials.append(material)
                        mat = self.materials.index(material)

                # parentJoint posX posY posZ normX normY normZ U V numJoints [jointId weight...
                if len(self.triangles) == 0:
                    self.triangles.append({"material": mat, "vertices": []})
                elif len(self.triangles[-1]["vertices"]) == 3:
                    self.triangles.append({"material": mat, "vertices": []})
                else:
                    numJoints = int(tok[9])
                    links = []
                    for j in range(10, 10 + numJoints * 2, 2):
                        links.append({
                        "joint": int(tok[j]),
                        "weight": float(tok[j + 1])
                    })
                    self.triangles[-1]["vertices"].append({
                        "parent": int(tok[0]),
                        "pos": Vector3(tok[1], tok[2], tok[3]),
                        "normals": Vector3(tok[4], tok[5], tok[6]),
                        "uv": Vector2(tok[7], tok[8]),
                        "links": links
                    })
    def toXmodel(self, suffix=""):
        res =  ("MODEL\n"
            + "VERSION 6\n\n"

            + "NUMBONES 1\n"
            + "BONE 0 -1 \"tag_origin\"\n\n"

            + "BONE 0\n"
            + "OFFSET 0.000000 0.000000 0.000000\n"
            + "SCALE 1.000000 1.000000 1.000000\n"
            + "X 1.000000 0.000000 0.000000\n"
            + "Y 0.000000 1.000000 0.000000\n"
            + "Z 0.000000 0.000000 1.000000\n\n"
        )

        res += f"NUMVERTS {len(self.triangles) * 3}\n"
        v = 0
        for tri in self.triangles:
            for vert in tri["vertices"]:
                res += (
                    f"VERT {v}\n"
                    + f"OFFSET {vert['pos']}\n"
                    + "BONES 1\n"
                    + "BONE 0 1.000000\n\n"
                )
                v += 1

        res += f"NUMFACES {len(self.triangles)}\n"
        v = 0
        for tri in self.triangles:
            res += f"TRI {tri['material']} {tri['material']} 0 0\n"
            for vert in [tri["vertices"][0], tri["vertices"][2], tri["vertices"][1]]:
                res += (
                    f"VERT {v}\n"
                    + f'NORMAL {vert["normals"]}\n'
                    + "COLOR 1.000000 1.000000 1.000000 1.000000\n"
                    + f'UV 1 {vert["uv"]}\n\n'
                )
            v += 3


        o = 0
        res += f"NUMOBJECTS {len(self.materials)}\n"
        for mat in self.materials:
            res += f"OBJECT {o} johndoeMesh_{o}\n"
        res += "\n"

        m = 0
        res += f"NUMMATERIALS {len(self.materials)}\n"
        for mat in self.materials:
            res += (
                f'MATERIAL {m} "{mat}{suffix}" "Phong" "404.tga"\n'
                + "COLOR 0.000000 0.000000 0.000000 1.000000\n"
                + "TRANSPARENCY 0.000000 0.000000 0.000000 1.000000\n"
                + "AMBIENTCOLOR 0.000000 0.000000 0.000000 1.000000\n"
                + "INCANDESCENCE 0.000000 0.000000 0.000000 1.000000\n"
                + "COEFFS 0.800000 0.000000\n"
                + "GLOW 0.000000 0\n"
                + "REFRACTIVE 6 1.000000\n"
                + "SPECULARCOLOR -1.000000 -1.000000 -1.000000 1.000000\n"
                + "REFLECTIVECOLOR -1.000000 -1.000000 -1.000000 1.000000\n"
                + "REFLECTIVE -1 1.000000\n"
                + "BLINN -1.000000 -1.000000\n"
                + "PHONG -1.000000\n\n"
            )
            m += 1
        return res