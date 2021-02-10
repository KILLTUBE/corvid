class Gdt:
    def __init__(self):
        self.entries = []
    
    def add(self, name: str, type: str, data: dict, comment: str = ""):
        self.entries.append({
            "name": name,
            "type": type,
            "data": data,
            "comment": comment
        })
    
    def toStr(self):
        res = "{\n"
        for entry in self.entries:
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
        count = len(self.entries)
        for i in range(count):
            name, type = self.entries[i]["name"], self.entries[i]["type"]
            res += f"@echo Converting {name}, {i+1} of {count}\n"
            res += f'@converter -nopause -single "{type}" {name}\n'
        return res