from collections import OrderedDict
from typing import List, Dict, Tuple
from Helpers.UtilFuncs import ParseQuotedKV

class GdtEntry:
    """
    GDT entries used for game assets like materials, models and images.
    """

    __slots__ = ("name", "gdf", "base", "data")

    name: str
    gdf: str
    base: str
    data: Dict

    def __init__(self, name: str, gdf: str, data: Dict, base: str=None) -> None:
        self.name = name
        self.gdf = gdf
        self.data = data
        self.base = base

    def InheritFrom(self, base: 'GdtEntry'):
        self.data = self.data.update(base.data.copy())

    def __setitem__(self, __name: str, __value: str) -> None:
        self.data[__name] = __value

    def __getitem__(self, __name: str) -> str:
        return self.data[__name]

    def __delitem__(self, __name: str) -> None:
        del self.data[__name]
    
    def __contains__(self, __name: str) -> bool:
        return __name in self.data

    def __str__(self):
        res = ""
        
        if self.gdf is not None and self.base is not None:
            res += f'"{self.name}" ( "{self.gdf}.gdf" ) [ "{self.base}" ]\n'
        elif self.gdf is not None and self.base is None:
            res += f'"{self.name}" ( "{self.gdf}.gdf" )\n'
        elif self.gdf is None and self.base is not None:
            res += f'"{self.name}" [ "{self.base}" ]\n'
        
        res += "{\n"

        for key, value in self.data.items():
            res += f'"{key}" "{value}"\n'

        res += "}\n"

        return res

class Gdt:
    """
    GDT files store data about game assets like materials, models and images.

    This class is used to create GDT files programmatically.
    """

    __slots__ = ("entries", "CoD2")

    entries: Dict[str, GdtEntry]
    CoD2: bool

    def __init__(self, CoD2=False) -> None:
        self.entries = OrderedDict()
        self.CoD2 = CoD2

    def ToBat(self, fileName):
        """
        In CoD games before Black Ops 3, the assets in GDT files need to be converted manually in asset manager.

        This method creates a batch file that calls converter.exe to convert each asset in a GDT file automatically.
        """

        res = ""
        total = len(self.entries.values())
        for i, entry in enumerate(self.entries.values()):
            res += f"@echo Converting {entry.name}, {i} out of {total}...\n"
            
            if self.CoD2: # the bat file needs different arguments 
                res += f'@converter -nopause -single "source_data\\{fileName}.gdt" {entry.name}\n'
            else:
                res += f"@converter -nopause -single \"{entry.gdf}\" {entry.name}\n"
        
        return res + "\n"

    def __str__(self):
        res = "{\n"

        for entry in self.entries.values():
            res += str(entry)

        res += "}\n"

        return res

    def __setitem__(self, __name: str, __value: str) -> None:
        self.entries[__name] = __value

    def __getitem__(self, __name: str) -> GdtEntry:
        return self.entries[__name]

    def __delitem__(self, __name: str) -> None:
        del self.entries[__name]
    
    def __contains__(self, __name: str) -> bool:
        return __name in self.entries

    def Combine(self, other: 'Gdt'):
        """
        Returns a new GDT object that contains all the entries from both GDT objects.
        
        Entries from the old GDT will be overwrittten if there are duplicates.
        """

        res = Gdt(self.CoD2)

        res.entries.update(self.entries)
        res.entries.update(other.entries)

        return res

    @staticmethod
    def FromStr(gdt: str):
        """
        Parses a GDT file and returns a GDT object.
        """

        res = Gdt()

        NONE, ENTRY, DATA = (0, 1, 2)
        mode = NONE
        current = None

        lines = gdt.strip().split("\n")

        for i, line in enumerate(lines):
            line = line.strip()
            if line == "{":
                if mode == NONE:
                    mode = ENTRY
                elif mode == ENTRY:
                    mode = DATA
                else:
                    print("error")
            elif line == "}":
                if mode == DATA:
                    mode = ENTRY
                elif mode == ENTRY:
                    mode = NONE
                else:
                    print("error")
            elif line.startswith('"'):
                if mode == ENTRY:
                    name = gdf = data = base = None
                    tok = line.split()
                    name = tok[0][1:-1]
                    current = name

                    for j, k in enumerate(tok):
                        if k == "(":
                            gdf = tok[j + 1][1:-5]
                        elif k == "[":
                            base = tok[j + 1][1:-1]
                    
                    res[name] = GdtEntry(name, gdf, {}, base)
                
                elif mode == DATA:
                    key, value = ParseQuotedKV(line)
                    res[current][key] = value
        return res
