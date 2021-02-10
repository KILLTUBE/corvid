def parseSmd(smd):
    lines = smd.split("\n")

    joints = [None] * 128
    frames = [None] * 1024
    frame = 0
    triangles = [] * 4096
    tri = -1
    materials = []
    NONE, NODES, SKELETON , TRIANGLES, VERTEXANIMATION = 0, 1, 2, 3, 4
    current = NONE

    for i in range(len(lines)):
        line = lines[i].strip()

        # decide what to expect
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
                frame = int(line.split(" ")[1])
                frames[frame] = [None] * 1024
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
            joint = line.split(" ")
            joints[int(joint[0])] = {
                "id": int(joint[0]),
                "name": joint[1][1 : len(joint[1]) - 1],
                "parent": int(joint[2])
            }
        elif current == SKELETON:
            # jointId posX posY posZ angleX angleY angleZ
            tok = line.split(" ")
            frames[frame][int(tok[0])] = {
                "joint": int(tok[0]),
                "pos": {"x": float(tok[1]), "y": float(tok[2]), "z": float(tok[3])},
                "angles": {"x": float(tok[4]), "y": float(tok[5]), "z": float(tok[6])}
            }
        elif current == VERTEXANIMATION:
            continue
        elif current == TRIANGLES:
            tok = line.split(" ")
            if len(tok) == 1:
                tri += 1
                triangles.append({
                    "material": line,
                    "vertices": []
                })
                if line not in materials:
                    materials.append(line)
            else:
                # parentJoint posX posY posZ normX normY normZ U V numJoints [jointId weight...
                numJoints = int(tok[9])
                links = []

                for j in range(10, 10 + numJoints * 2, 2):
                    links.append({
                        "joint": int(tok[j]),
                        "weight": float(tok[j + 1])
                    })
                
                triangles[tri]["vertices"].append({
                    "parentJoint": int(tok[0]),
                    "pos": {"x": float(tok[1]), "y": float(tok[2]), "z": float(tok[3])},
                    "normal": {"x": float(tok[4]), "y": float(tok[5]), "z": float(tok[6])},
                    "UV": {"x": float(tok[7]), "y": float(tok[8])},
                    "links": links
                })
    
    return {
        "joints": joints,
        "frames": frames,
        "triangles": triangles,
        "materials": materials
    }
