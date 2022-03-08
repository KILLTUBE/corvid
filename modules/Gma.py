# based on https://github.com/TheClonerx/py-gmav/blob/master/addon.py

import json

MAX_VER = 3

class FileEntry:
    def __init__(self, addon):
        self.addon: 'Addon' = addon
        self.name = ""
        self.size = 0
        self.CRC  = 0
        self.offset = 0

    def save(self, path):
        block_size = 2**12
        written = 0
        self.addon.file.seek(self.addon.file_block)
        self.addon.file.seek(self.offset, 1)
        with open(path, "wb") as file:
            while written < self.size:
                if block_size > self.size - written:
                    block_size = self.size - written
                file.write(self.addon.file.read(block_size))
                written += block_size

    # TODO: write a method to open files directly from addons

class Addon:
    def __init__(self, path):
        self.path = path
        self.file = None
        self.format_ver = 0
        self.name    = ""
        self.desc    = ""
        self.type    = ""
        self.tags    = []
        self.author  = ""
        self.version = 0
        self.file_block = 0

        self.entries: dict[str, FileEntry] = {}

    def open(self):
        self.file = open(self.path, "rb")

    def check_file(self):
        gmad = self.read_buff(4)
        if gmad != b"GMAD":
            return False
        self.format_ver = self.read_int(1)
        if self.format_ver > MAX_VER:
            return False
        return True

    def parse(self):
        self.read_buff(16) # steamid & timestamp

        if self.format_ver > 1:
            while self.read_str(): pass

        self.name    = self.read_str()
        self.desc    = self.read_str()
        self.author  = self.read_str()
        self.version = self.read_int(4, True)

        self.desc = json.loads(self.desc)
        self.type = self.desc["type"]
        self.tags = self.desc["tags"]

        if "description" in self.desc:
            self.desc = self.desc["description"]
        else:
            self.desc = "placeholder"

    def get_entries(self):
        offset = 0
        while self.read_int(4):
            entry = FileEntry(self)
            entry.name = self.read_str()
            entry.size = self.read_int(8)
            entry.CRC  = self.read_int(4)
            entry.offset = offset
            offset += entry.size
            self.entries[entry.name] = entry

        self.file_block = self.file.tell()

    def read_buff(self, size):
        buff = self.file.read(size)
        if len(buff) != size:
            raise ValueError("readed %d instead of %s" % (len(buff), size))
        return buff

    def read_int(self, size, signed = False):
        buff = self.read_buff(size)
        return int.from_bytes(buff, "little", signed = signed)

    def read_str(self):
        buff = b""
        c = self.file.read(1)
        while c != b"\0":
            buff += c
            c = self.file.read(1)
        return buff.decode()

def load(path):
    addon = Addon(path)
    addon.open()
    if not addon.check_file():
        raise TypeError("wrong file type")
    addon.parse()
    addon.get_entries()
    return addon
