from os import makedirs, listdir
import sys
import tkinter as tk
import tkinter.constants
import tkinter.messagebox as alert
import tkinter.font as tkFont
from tkinter import filedialog
from sys import stderr, stdout
import os.path
from modules.MapExporter import exportMap
import time 
from threading import *
import shutil
from tempfile import gettempdir, tempdir

class App:
    def __init__(self, root: tk.Tk):
        root.title("Corvid")
        root.iconbitmap("icon.ico")
        width=800
        height=650
        screenwidth = root.winfo_screenwidth()
        screenheight = root.winfo_screenheight()
        alignstr = '%dx%d+%d+%d' % (width, height, (screenwidth - width) / 2, (screenheight - height) / 2 - 30)
        root.geometry(alignstr)
        root.resizable(width=False, height=False)
        ft = tkFont.Font(family='Verdana',size=8)

        vmfLabel=tk.Label(root)
        vmfLabel["font"] = ft
        vmfLabel["fg"] = "#333333"
        vmfLabel["justify"] = "left"
        vmfLabel["text"] = "VMF File"
        vmfLabel.place(x=20,y=10,width=50,height=30)

        self.vmfPath=tk.Entry(root)
        self.vmfPath["borderwidth"] = "1px"
        self.vmfPath["font"] = ft
        self.vmfPath["fg"] = "#333333"
        self.vmfPath["justify"] = "left"
        self.vmfPath.place(x=80,y=10,width=571,height=30)

        chooseVmfDialog=tk.Button(root)
        chooseVmfDialog["bg"] = "#f0f0f0"
        chooseVmfDialog["font"] = ft
        chooseVmfDialog["fg"] = "#000000"
        chooseVmfDialog["justify"] = "center"
        chooseVmfDialog["text"] = "Choose file"
        chooseVmfDialog.place(x=660,y=10,width=115,height=30)
        chooseVmfDialog["command"] = self.chooseVmfDialog_command

        vpkLabel=tk.Label(root)
        vpkLabel["font"] = ft
        vpkLabel["fg"] = "#333333"
        vpkLabel["justify"] = "left"
        vpkLabel["text"] = "VPK files"
        vpkLabel.place(x=20,y=50,width=50,height=30)

        self.vpkList=tk.Listbox(root)
        self.vpkList["selectmode"] = tk.EXTENDED
        self.vpkList["borderwidth"] = "1px"
        self.vpkList["font"] = ft
        self.vpkList["fg"] = "#333333"
        self.vpkList["justify"] = "left"
        self.vpkList.place(x=20,y=90,width=755,height=60)
        vpkScrollbar = tk.Scrollbar(self.vpkList)
        vpkScrollbar.pack(side=tk.RIGHT, fill=tk.BOTH)
        self.vpkList["yscrollcommand"] = vpkScrollbar.set

        gameDirLabel=tk.Label(root)
        gameDirLabel["font"] = ft
        gameDirLabel["fg"] = "#333333"
        gameDirLabel["justify"] = "left"
        gameDirLabel["text"] = "Asset directories"
        gameDirLabel.place(x=20,y=160,width=99,height=30)

        self.gameDirList=tk.Listbox(root)
        self.gameDirList["selectmode"] = tk.EXTENDED
        self.gameDirList["borderwidth"] = "1px"
        self.gameDirList["font"] = ft
        self.gameDirList["fg"] = "#333333"
        self.gameDirList["justify"] = "left"
        self.gameDirList.place(x=20,y=200,width=755,height=60)
        gameDirScrollbar = tk.Scrollbar(self.gameDirList)
        gameDirScrollbar.pack(side=tk.RIGHT, fill=tk.BOTH)
        self.gameDirList["yscrollcommand"] = gameDirScrollbar.set

        deleteVpkButton=tk.Button(root)
        deleteVpkButton["bg"] = "#f0f0f0"
        deleteVpkButton["font"] = ft
        deleteVpkButton["fg"] = "#000000"
        deleteVpkButton["justify"] = "center"
        deleteVpkButton["text"] = "Remove"
        deleteVpkButton.place(x=660,y=50,width=114,height=30)
        deleteVpkButton["command"] = self.deleteVpkButton_command

        deleteDirButton=tk.Button(root)
        deleteDirButton["bg"] = "#f0f0f0"
        deleteDirButton["font"] = ft
        deleteDirButton["fg"] = "#000000"
        deleteDirButton["justify"] = "center"
        deleteDirButton["text"] = "Remove"
        deleteDirButton.place(x=660,y=160,width=115,height=30)
        deleteDirButton["command"] = self.deleteDirButton_command

        addVpkButton=tk.Button(root)
        addVpkButton["bg"] = "#f0f0f0"
        addVpkButton["font"] = ft
        addVpkButton["fg"] = "#000000"
        addVpkButton["justify"] = "center"
        addVpkButton["text"] = "Add"
        addVpkButton.place(x=540,y=50,width=115,height=30)
        addVpkButton["command"] = self.addVpkButton_command

        addGameDirButton=tk.Button(root)
        addGameDirButton["bg"] = "#f0f0f0"
        addGameDirButton["font"] = ft
        addGameDirButton["fg"] = "#000000"
        addGameDirButton["justify"] = "center"
        addGameDirButton["text"] = "Add"
        addGameDirButton.place(x=540,y=160,width=115,height=30)
        addGameDirButton["command"] = self.addGameDirButton_command

        # decide what game the map is going to be converted for
        self.BO3 = tk.BooleanVar()

        radioBO3=tk.Radiobutton(root, variable=self.BO3)
        radioBO3["font"] = ft
        radioBO3["fg"] = "#333333"
        radioBO3["justify"] = "left"
        radioBO3["text"] = "Black ops 3"
        radioBO3.place(x=90,y=270,width=84,height=30)
        radioBO3["value"] = True

        radioOld=tk.Radiobutton(root, variable=self.BO3)
        radioOld["font"] = ft
        radioOld["fg"] = "#333333"
        radioOld["justify"] = "left"
        radioOld["text"] = "Cod 4/5/7"
        radioOld.place(x=230,y=270,width=80,height=30)
        radioOld["value"] = False
        
        radioBO3.select() # default value

        gameLabel=tk.Label(root)
        gameLabel["font"] = ft
        gameLabel["fg"] = "#333333"
        gameLabel["justify"] = "left"
        gameLabel["text"] = "Game"
        gameLabel.place(x=20,y=270,width=34,height=30)

        removeLabel=tk.Label(root)
        removeLabel["font"] = ft
        removeLabel["fg"] = "#333333"
        removeLabel["justify"] = "left"
        removeLabel["text"] = "Remove"
        removeLabel.place(x=20,y=310,width=49,height=30)

        self.removeProbes = tk.BooleanVar()
        checkRemoveProbes=tk.Checkbutton(root)
        checkRemoveProbes["font"] = ft
        checkRemoveProbes["fg"] = "#333333"
        checkRemoveProbes["justify"] = "center"
        checkRemoveProbes["text"] = "Reflection probes"
        checkRemoveProbes["variable"] = self.removeProbes
        checkRemoveProbes.place(x=80,y=310,width=127,height=30)
        checkRemoveProbes["offvalue"] = False
        checkRemoveProbes["onvalue"] = True

        self.removeClips = tk.BooleanVar()
        checkRemoveClips=tk.Checkbutton(root)
        checkRemoveClips["font"] = ft
        checkRemoveClips["fg"] = "#333333"
        checkRemoveClips["justify"] = "left"
        checkRemoveClips["text"] = "Clip brushes"
        checkRemoveClips["variable"] = self.removeClips
        checkRemoveClips.place(x=240,y=310,width=89,height=30)
        checkRemoveClips["offvalue"] = False
        checkRemoveClips["onvalue"] = True

        self.removeLights = tk.BooleanVar()
        checkRemoveLights=tk.Checkbutton(root)
        checkRemoveLights["font"] = ft
        checkRemoveLights["fg"] = "#333333"
        checkRemoveLights["justify"] = "left"
        checkRemoveLights["text"] = "Lights"
        checkRemoveLights["variable"] = self.removeLights
        checkRemoveLights.place(x=360,y=310,width=50,height=30)
        checkRemoveLights["offvalue"] = False
        checkRemoveLights["onvalue"] = True

        self.removeSkybox = tk.BooleanVar()
        checkRemoveSky=tk.Checkbutton(root)
        checkRemoveSky["font"] = ft
        checkRemoveSky["fg"] = "#333333"
        checkRemoveSky["justify"] = "left"
        checkRemoveSky["text"] = "Skybox brushes"
        checkRemoveSky["variable"] = self.removeSkybox
        checkRemoveSky.place(x=460,y=310,width=110,height=30)
        checkRemoveSky["offvalue"] = False
        checkRemoveSky["onvalue"] = True

        consoleLabel=tk.Label(root)
        consoleLabel["font"] = ft
        consoleLabel["fg"] = "#333333"
        consoleLabel["justify"] = "left"
        consoleLabel["text"] = "Console"
        consoleLabel.place(x=20,y=440,width=49,height=30)

        self.consoleTextBox=tk.Text(root)
        self.consoleTextBox["borderwidth"] = "1px"
        self.consoleTextBox["font"] = ft
        self.consoleTextBox["fg"] = "#333333"
        self.consoleTextBox.place(x=20,y=480,width=755,height=132)
        sys.stdout = TextRedirector(self.consoleTextBox, stdout)
        sys.stderr = TextRedirector(self.consoleTextBox, stderr)
        self.consoleScrollbar = tk.Scrollbar(self.consoleTextBox)
        self.consoleScrollbar.pack(side=tk.RIGHT, fill=tk.BOTH)
        self.consoleTextBox["yscrollcommand"] = self.consoleScrollbar.set

        clearConsoleButton=tk.Button(root)
        clearConsoleButton["bg"] = "#f0f0f0"
        clearConsoleButton["font"] = ft
        clearConsoleButton["fg"] = "#000000"
        clearConsoleButton["justify"] = "center"
        clearConsoleButton["text"] = "Clear console"
        clearConsoleButton.place(x=660,y=440,width=114,height=30)
        clearConsoleButton["command"] = self.clearConsoleButton_command

        convertButton=tk.Button(root)
        convertButton["bg"] = "#f0f0f0"
        convertButton["font"] = ft
        convertButton["fg"] = "#000000"
        convertButton["justify"] = "center"
        convertButton["text"] = "Convert"
        convertButton.place(x=20,y=400,width=755,height=30)
        convertButton["command"] = self.convertButton_thread

        skipLabel=tk.Label(root)
        skipLabel["font"] = ft
        skipLabel["fg"] = "#333333"
        skipLabel["justify"] = "left"
        skipLabel["text"] = "Skip converting"
        skipLabel.place(x=20,y=350,width=93,height=30)

        self.skipMats = tk.BooleanVar()
        checkSkipMaterials=tk.Checkbutton(root)
        checkSkipMaterials["font"] = ft
        checkSkipMaterials["fg"] = "#333333"
        checkSkipMaterials["justify"] = "left"
        checkSkipMaterials["text"] = "Materials"
        checkSkipMaterials["variable"] = self.skipMats
        checkSkipMaterials.place(x=130,y=350,width=76,height=30)
        checkSkipMaterials["offvalue"] = False
        checkSkipMaterials["onvalue"] = True

        self.skipModels = tk.BooleanVar()
        checkSkipModels=tk.Checkbutton(root)
        checkSkipModels["font"] = ft
        checkSkipModels["fg"] = "#333333"
        checkSkipModels["justify"] = "center"
        checkSkipModels["text"] = "Models"
        checkSkipModels["variable"] = self.skipModels
        checkSkipModels.place(x=230,y=350,width=78,height=30)
        checkSkipModels["offvalue"] = False
        checkSkipModels["onvalue"] = True
        self.vpkList.insert(0, "C:/stuff/Steam/steamapps/common/Counter-Strike Global Offensive/csgo/pak01_dir.vpk")
        self.gameDirList.insert(0, "C:/stuff/Steam/steamapps/common/Half-Life 2/hl2")
    def chooseVmfDialog_command(self):
        file = filedialog.askopenfile(mode="r", filetypes=[("Source Engine map file", "*.vmf")])
        if file is not None:
            self.vmfPath.delete(0, tkinter.constants.END)
            self.vmfPath.insert(0, file.name)

    def addVpkButton_command(self):
        file = filedialog.askopenfile(mode="r", filetypes=[("Valve pak file", "*.vpk")])
        if file is not None:
            self.vpkList.insert(tk.END, file.name)

    def addGameDirButton_command(self):
        dir = filedialog.askdirectory()
        if dir is not None:
            self.gameDirList.insert(tk.END, dir)

    def deleteVpkButton_command(self):
        for file in self.vpkList.curselection():
            self.vpkList.delete(file)

    def deleteDirButton_command(self):
        for dir in self.gameDirList.curselection():
            self.gameDirList.delete(dir)

    def clearConsoleButton_command(self):
        self.consoleTextBox.delete(0.0, tkinter.constants.END)

    def convertButton_command(self):
        vpkFiles = list(self.vpkList.get(0, self.vpkList.size() - 1))
        gameDirs = list(self.gameDirList.get(0, self.gameDirList.size() - 1))
        '''
        print("VMF path:", self.vmfPath.get())
        print("Vpk files:", vpkFiles)
        print("Game dirs:", gameDirs)
        print("Bo3:", self.BO3.get())
        print("Remove clips:", self.removeClips.get())
        print("Remove probes:", self.removeProbes.get())
        print("Remove lights:", self.removeLights.get())
        print("Remove skybox:", self.removeSkybox.get())
        print("Skip materials:", self.skipMats.get())
        print("Skip models:", self.skipModels.get())
        '''
        vmfPath = self.vmfPath.get()
        # check if the selected file is a valid VMF file
        if len(vmfPath) == "0":
            ("Please select a VMF file!")
            return False
        if not os.path.isfile(vmfPath):
            alert.showerror(title="Error", message="Please select a valid file!")
            return False
        if not os.path.exists(vmfPath):
            alert.showerror(title="Error", message="VMF file does not exist.")
            return False
        if os.path.splitext(vmfPath)[1].lower() != ".vmf":
            alert.showerror(title="Error", message="Please choose a VMF file")
            return False
        # set the export directory
        outputDir = filedialog.askdirectory(title="Select a directory to export the converted map and its assets")
        if outputDir is None:
            alert.showwarning("Please select a directory to export the map!")
            return False
        # check vpks
        for vpk in vpkFiles:
            if not os.path.isfile(vpk):
                alert.showerror(title="Error", message=f"\"{vpk}\" is not a valid file!")
                return False
            if not vpk.endswith(".vpk"):
                alert.showerror(title="error", message=f"\"{vpk}\" is not a VPK file!")
                return False
        # check gamedirs
        for dir in gameDirs:
            if not os.path.isdir(dir):
                alert.showerror(title="Error", message=f"{dir} is not a valid directory.")
                return False
            if os.path.isdir(f"{dir}/materials") or os.path.isdir(f"{dir}/models"):
                pass
            else:
                alert.showerror(title="error", message=f"{dir} does not have any models or materials in it.")
                return False

        start = time.time()
        vmfName = os.path.splitext(os.path.basename(vmfPath))[0].lower()
        # read the map file and convert everything
        outputDir += f"/{vmfName}"
        print(f"Opening VMF file \"{vmfPath}\"...")
        vmfFile = open(vmfPath)
        print("Reading VMF file...")
        BO3 = self.BO3.get()
        res = exportMap(vmfFile, vpkFiles, gameDirs, BO3, self.removeClips.get(), self.removeProbes.get(), self.removeLights.get(), self.removeSkybox.get(), self.skipMats.get(), self.skipModels.get(), vmfName)
        # prepare the necessary stuff to move and write files
        try:
            makedirs(f"{outputDir}/map_source")
        except:
            pass
        if BO3:
            try:
                makedirs(f"{outputDir}/map_source/_prefabs/_{vmfName}")
            except:
                pass
        convertedDir = gettempdir() + "/corvid/converted/"
        convertedFiles = listdir(convertedDir)
        print(f"Moving all converted assets to \"{outputDir}\"...")
        try:
            for file in convertedFiles:
                shutil.move(os.path.join(convertedDir, file), outputDir)
        except:
            pass
        # create the .map file
        print(f"Writing \"{vmfName}.map\" in \"{outputDir}/map_source\"")
        open(f"{outputDir}/map_source/{vmfName}.map", "w").write(res)
        end = time.time()
        print(f"Conversion finished in {round(end - start)} seconds")

    def convertButton_thread(self):
        t1 = Thread(target=self.convertButton_command)
        t1.start()

class TextRedirector(object):
    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag
        self.eof = False

    def write(self, str):
        if self.eof:
            self.eof = False
            self.widget.delete(1.0, "end")
        self.widget.insert("end", str, (self.tag,))
        self.widget.see("end")

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
