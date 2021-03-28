class Gdt:
    def __init__(self, entries={}):
        self.entries = entries
    
    def add(self, name: str, type: str, data: dict, comment: str = ""):
        self.entries[name] = {
            "name": name,
            "type": type,
            "data": data,
            "comment": comment
        }
    
    def toStr(self):
        res = "{\n"
        for entry in list(self.entries.values()):
            if entry["comment"] != "":
                res += f' // {entry["comment"]}\n'
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
            res += f'@converter -nopause -single "{type}" {name}\n'
        return res + "\n"
    
    def __add__(self, other: 'Gdt'):
        return Gdt({**self.entries, **other.entries})