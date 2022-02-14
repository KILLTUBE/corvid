class Gdt:
    def __init__(self, entries={}):
        self.entries = entries
        self.CoD2 = False
        self.name = ""
    
    def add(self, name: str, type: str, data: dict, base: str=""):
        self.entries[name] = {
            "name": name,
            "type": type,
            "data": data,
            "base": base
        }
    
    def toStr(self):
        res = "{\n"
        for entry in list(self.entries.values()):
            if entry["base"] != "":
                res += f' "{entry["name"]}" ( "{entry["type"]}.gdf" ) [ {entry["base"]} ]\n'
            else:
                res += f' "{entry["name"]}" ( "{entry["type"]}.gdf" )\n'
            res += " {\n"
            for key, value in entry["data"].items():
                res += f'  "{key}" "{value}"\n'
            res += " }\n"
        res += "}\n"
        return res
                
    def toBat(self):
        res = ""
        entries = list(self.entries.values())
        count = len(entries)
        for i in range(count):
            name, type = entries[i]["name"], entries[i]["type"]
            res += f"@echo Converting {name}, {i+1} of {count}\n"
            if self.CoD2: # the bat file needs different arguments 
                res += f'@converter -nopause -single "source_data\\_{self.name}.gdt" {name}\n'
            else:
                res += f'@converter -nopause -single "{type}" {name}\n'
        return res + "\n"
    
    def __add__(self, other: 'Gdt'):
        res = Gdt({**self.entries, **other.entries})
        res.CoD2 = self.CoD2
        res.name = self.name
        return res