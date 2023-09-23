import sys
import winreg
import os.path
import time 
import threading
import shutil
import json
import webbrowser
import tkinter as tk
import tkinter.constants
import tkinter.messagebox as alert
import tkinter.font as tkFont
from tkinter import filedialog, simpledialog
from tkinter.ttk import Progressbar
from sys import stderr, stdout, exit
from os import makedirs, listdir
from os.path import exists
from tempfile import gettempdir
from datetime import datetime
from time import gmtime, strftime
from pathlib import Path
from modules.MapExporter import exportMap
from modules.Vector3 import Vector3
from modules.vdfutils import parse_vdf

# global settings
settings = json.loads(open("res/settings.json").read())
gameDef = json.loads(open("res/gameDef.json").read())
gameDefCustom = json.loads(open("res/gameDef.json").read())
version = open("res/version.txt").read().split("\n")[0]
steamAppsDirs = []

def ProperTime(time):
    f = strftime('%H:%M:%S', gmtime(time)).split(":")
    h, m, s = int(f[0]), int(f[1]), int(f[2])

    res = ""
    if h == 1:
        res += "1 hour "
    elif h > 1:
        res += f"{h} hours "
    
    if m == 1:
        res += "1 minute "
    elif m > 1:
        res += f"{m} minutes "
    
    if s == 1:
        res += "1 second"
    else:
        res += f"{s} seconds"
    
    return res

class popupWindow:
    def __init__(self, app: 'App'):
        top = self.top = tk.Toplevel(app.root)
        top.title("Set export scale")
        top.resizable(0, 0)
        top.wm_transient()
        top.grab_set_global()
        top.bind("<Escape>", lambda x: top.destroy())
        top.bind("<Return>", lambda x: self.okCommand())
        top.focus_force()
        top.transient(app.root)

        width=175
        height=105
        screenwidth = app.root.winfo_screenwidth()
        screenheight = app.root.winfo_screenheight()
        alignstr = '%dx%d+%d+%d' % (width, height, (screenwidth - width) / 2, (screenheight - height) / 2 - 30)
        top.geometry(alignstr)

        self.text=tk.Label(top, text="Please enter the scale value", justify="center")
        self.text.place(x=0, y=0, height=30, width=175)
        
        self.textXY = tk.Label(top, text="X/Y")
        self.textXY.place(x=5, y=25)
        self.scaleXY = tk.Entry(top)
        self.scaleXY.focus_force()
        self.scaleXY.insert(0, settings["scale"][0])
        self.scaleXY.place(x=30, y=25, width=140)
        
        self.textZ = tk.Label(top, text="Z")
        self.textZ.place(x=5, y=50)
        self.scaleZ = tk.Entry(top)
        self.scaleZ.insert(0, settings["scale"][1])
        self.scaleZ.place(x=30, y=50, width=140)

        self.ok=tk.Button(top,text='OK', command=self.okCommand)
        self.ok.place(x=5, y=75, width=83)
        self.cancel=tk.Button(top,text='Cancel', command=top.destroy)
        self.cancel.place(x=90, y=75, width=80)

    def okCommand(self):
        xy = z = None
        try:
            xy, z = float(self.scaleXY.get()), float(self.scaleZ.get())
        except ValueError:
            alert.showwarning(title="Error", message="Please enter a proper number.")
            return
        else:
            if xy is not None and z is not None:
                app.changeSetting("scale", [xy, z])
                self.top.destroy()

class App:
    def __init__(self, root: tk.Tk):
        root.title(f"Corvid - v{version}")
        root.iconbitmap(default="res/icon.ico")
        self.root = root
        width=800
        height=620
        screenwidth = root.winfo_screenwidth()
        screenheight = root.winfo_screenheight()
        alignstr = '%dx%d+%d+%d' % (width, height, (screenwidth - width) / 2, (screenheight - height) / 2 - 30)
        root.geometry(alignstr)
        root.resizable(width=False, height=False)
        ft = tkFont.Font(family='Verdana',size=8)

        # menu bar
        self.menuBar = tk.Menu(root)
        # file menu
        self.fileMenu = tk.Menu(self.menuBar, tearoff=0)
        self.fileMenu.add_command(label="Select VMF file", command=self.chooseVmfDialog_command)
        self.fileMenu.add_command(label="Clear console", command=self.clearConsoleButton_command)
        self.fileMenu.add_command(label="Save console log", command=self.saveConsoleLog)

        self.fileMenu.add_separator()
        self.fileMenu.add_command(label="Exit", command=root.quit)
        self.menuBar.add_cascade(label="File", menu=self.fileMenu)

        # edit menu
        settingsMenu = tk.Menu(self.menuBar, tearoff=0)
        self.menuBar.add_cascade(label="Settings", menu=settingsMenu)

        self.currentGame = tk.StringVar(value=settings["currentGame"])
        currentGameMenu = tk.Menu(self.menuBar, tearoff=0)

        for game in gameDef:
            if gameDef[game]["gameName"] == "seperator":
                currentGameMenu.add_separator()
            else:
                currentGameMenu.add_radiobutton(label=gameDef[game]["gameName"], variable=self.currentGame, value=game, command=self.setCurrentGame)

        self.convertBrush = tk.BooleanVar(value=settings["convertBrush"])
        brushConversionMenu = tk.Menu(self.menuBar, tearoff=0)
        brushConversionMenu.add_radiobutton(label="Terrain patches (default)", variable=self.convertBrush, value=False, command=lambda: self.changeSetting("convertBrush", False))
        brushConversionMenu.add_radiobutton(label="Plain brushes (experimental)", variable=self.convertBrush, value=True, command=lambda: self.changeSetting("convertBrush", True))

        settingsMenu.add_cascade(label="Select game profile", menu=currentGameMenu)
        settingsMenu.add_cascade(label="Brush conversion method", menu=brushConversionMenu)
        settingsMenu.add_command(label="Change export scale", command=self.popup)
        settingsMenu.add_separator()
        settingsMenu.add_command(label="Set Steam directory", command=self.setSteamDir)

        helpMenu = tk.Menu(self.menuBar, tearoff=0)
        helpMenu.add_command(label="Corvid on Github", command=lambda: webbrowser.open("https://github.com/KILLTUBE/corvid"))
        helpMenu.add_command(label="Corvid wiki", command=lambda: webbrowser.open("https://github.com/KILLTUBE/corvid/wiki"))
        helpMenu.add_command(label="Video tutorial", command=lambda: webbrowser.open("https://www.youtube.com/watch?v=izALMNZjgkA"))
        #helpMenu.add_command(label="Check for new versions", command=lambda: print("Checking for new versions..."))
        helpMenu.add_separator()
        # helpMenu.add_command(label="Support me on Patreon", command=lambda: webbrowser.open("https://www.patreon.com/johndoe_"))
        helpMenu.add_command(label="About Corvid", command=self.aboutButton_command)
        self.menuBar.add_cascade(label="Help", menu=helpMenu)

        root.config(menu=self.menuBar)

        vmfLabel=tk.Label(root)
        vmfLabel["font"] = ft
        vmfLabel["fg"] = "#333333"
        vmfLabel["justify"] = "left"
        vmfLabel["text"] = "VMF File"
        vmfLabel["anchor"] = "w"
        vmfLabel.place(x=20,y=10,width=50,height=30)

        self.vmfPath=tk.Entry(root)
        self.vmfPath["borderwidth"] = "1px"
        self.vmfPath["font"] = ft
        self.vmfPath["fg"] = "#333333"
        self.vmfPath["justify"] = "left"
        self.vmfPath.place(x=80,y=10,width=570,height=30)

        chooseVmfButton=tk.Button(root)
        chooseVmfButton["bg"] = "#f0f0f0"
        chooseVmfButton["font"] = ft
        chooseVmfButton["fg"] = "#000000"
        chooseVmfButton["justify"] = "center"
        chooseVmfButton["text"] = "Browse"
        chooseVmfButton.place(x=660,y=10,width=114,height=30)
        chooseVmfButton["command"] = self.chooseVmfDialog_command

        vpkLabel=tk.Label(root)
        vpkLabel["font"] = ft
        vpkLabel["fg"] = "#333333"
        vpkLabel["justify"] = "left"
        vpkLabel["text"] = "VPK files / Garry's Mod addons"
        vpkLabel["anchor"] = "w"
        vpkLabel.place(x=20,y=50,width=300,height=30)

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
        gameDirLabel["anchor"] = "w"
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
        deleteVpkButton.place(x=540,y=50,width=114,height=30)
        deleteVpkButton["command"] = self.deleteVpkButton_command

        deleteDirButton=tk.Button(root)
        deleteDirButton["bg"] = "#f0f0f0"
        deleteDirButton["font"] = ft
        deleteDirButton["fg"] = "#000000"
        deleteDirButton["justify"] = "center"
        deleteDirButton["text"] = "Remove"
        deleteDirButton.place(x=540,y=160,width=115,height=30)
        deleteDirButton["command"] = self.deleteDirButton_command

        addVpkButton=tk.Button(root)
        addVpkButton["bg"] = "#f0f0f0"
        addVpkButton["font"] = ft
        addVpkButton["fg"] = "#000000"
        addVpkButton["justify"] = "center"
        addVpkButton["text"] = "Add"
        addVpkButton.place(x=420,y=50,width=115,height=30)
        addVpkButton["command"] = self.addVpkButton_command

        addGameDirButton=tk.Button(root)
        addGameDirButton["bg"] = "#f0f0f0"
        addGameDirButton["font"] = ft
        addGameDirButton["fg"] = "#000000"
        addGameDirButton["justify"] = "center"
        addGameDirButton["text"] = "Add"
        addGameDirButton.place(x=420,y=160,width=115,height=30)
        addGameDirButton["command"] = self.addGameDirButton_command

        clearVpkButton=tk.Button(root)
        clearVpkButton["bg"] = "#f0f0f0"
        clearVpkButton["font"] = ft
        clearVpkButton["fg"] = "#000000"
        clearVpkButton["justify"] = "center"
        clearVpkButton["text"] = "Clear"
        clearVpkButton.place(x=660,y=50,width=115,height=30)
        clearVpkButton["command"] = lambda: self.vpkList.delete(0, tk.END)

        clearGameDirButton=tk.Button(root)
        clearGameDirButton["bg"] = "#f0f0f0"
        clearGameDirButton["font"] = ft
        clearGameDirButton["fg"] = "#000000"
        clearGameDirButton["justify"] = "center"
        clearGameDirButton["text"] = "Clear"
        clearGameDirButton.place(x=660,y=160,width=115,height=30)
        clearGameDirButton["command"] = lambda: self.gameDirList.delete(0, tk.END)

        # decide what game the map is going to be converted for
        self.game = tk.StringVar()
        self.game.set(settings["game"])

        radioBO3=tk.Radiobutton(root, variable=self.game)
        radioBO3["font"] = ft
        radioBO3["fg"] = "#333333"
        radioBO3["justify"] = "left"
        radioBO3["text"] = "Black Ops 3"
        radioBO3.place(x=134,y=270,width=88,height=30)
        radioBO3["value"] = "BO3"
        radioBO3["command"] = lambda: self.changeSetting("game", "BO3")

        radioWaW=tk.Radiobutton(root, variable=self.game)
        radioWaW["font"] = ft
        radioWaW["fg"] = "#333333"
        radioWaW["justify"] = "left"
        radioWaW["text"] = "WaW / Black Ops"
        radioWaW.place(x=270,y=270,width=120,height=30)
        radioWaW["value"] = "WaW"
        radioWaW["command"] = lambda: self.changeSetting("game", "WaW")

        radioCoD4=tk.Radiobutton(root, variable=self.game)
        radioCoD4["font"] = ft
        radioCoD4["fg"] = "#333333"
        radioCoD4["justify"] = "left"
        radioCoD4["text"] = "CoD 4"
        radioCoD4.place(x=425,y=270,width=75,height=30)
        radioCoD4["value"] = "CoD4"
        radioCoD4["command"] = lambda: self.changeSetting("game", "CoD4")

        radioCoD2=tk.Radiobutton(root, variable=self.game)
        radioCoD2["font"] = ft
        radioCoD2["fg"] = "#333333"
        radioCoD2["justify"] = "left"
        radioCoD2["text"] = "CoD 2"
        radioCoD2.place(x=515,y=270,width=100,height=30)
        radioCoD2["value"] = "CoD2"
        radioCoD2["command"] = lambda: self.changeSetting("game", "CoD2")

        gameLabel=tk.Label(root)
        gameLabel["font"] = ft
        gameLabel["fg"] = "#333333"
        gameLabel["justify"] = "left"
        gameLabel["anchor"] = "w"
        gameLabel["text"] = "Game"
        gameLabel.place(x=20,y=270,width=50,height=30)

        self.currentGameLabel=tk.Label(root)
        self.currentGameLabel["font"] = ft
        self.currentGameLabel["justify"] = "right"
        self.currentGameLabel["anchor"] = "e"
        self.currentGameLabel["fg"] = "#333333"
        self.currentGameLabel["text"] = gameDef[settings["currentGame"]]["gameName"]
        self.currentGameLabel.place(x=390,y=570,width=390,height=30)

        self.steamDirLabel=tk.Label(root)
        self.steamDirLabel["font"] = ft
        self.steamDirLabel["justify"] = "left"
        self.steamDirLabel["anchor"] = "w"
        self.steamDirLabel["fg"] = "#333333"
        self.steamDirLabel["text"] = settings["steamDir"] if settings["steamDir"] != "" else "Steam directory not found!"
        self.steamDirLabel.place(x=20,y=570,width=390,height=30)

        self.progressOverall = Progressbar()
        self.progressOverall.place(x=20,y=400,width=615,height=13)
        self.progressOverall["value"] = 0

        self.overallLabel = tk.Label()
        self.overallLabel["font"] = ft
        self.overallLabel["justify"] = "left"
        self.overallLabel["anchor"] = "w"
        self.overallLabel["fg"] = "#333333"
        self.overallLabel["text"] = f"Total: n/a"
        self.overallLabel.place(x=635,y=398,width=300,height=15)

        self.progressCurrent = Progressbar()
        self.progressCurrent.place(x=20,y=417,width=615,height=13)
        self.progressCurrent["value"] = 0

        self.currentLabel = tk.Label()
        self.currentLabel["font"] = ft
        self.currentLabel["justify"] = "left"
        self.currentLabel["anchor"] = "w"
        self.currentLabel["fg"] = "#333333"
        self.currentLabel["text"] = f"Current: n/a"
        self.currentLabel.place(x=635,y=416,width=300,height=15)

        self.consoleTextBox=tk.Text(root)
        self.consoleTextBox["borderwidth"] = "1px"
        self.consoleTextBox["font"] = ft
        self.consoleTextBox["fg"] = "#333333"
        self.consoleTextBox.place(x=20,y=440,width=755,height=132)
        sys.stdout = TextRedirector(self.consoleTextBox, self.progressOverall, self.progressCurrent, self.overallLabel, self.currentLabel, stdout)
        sys.stderr = TextRedirector(self.consoleTextBox, self.progressOverall, self.progressCurrent, self.overallLabel, self.currentLabel, stderr)
        self.consoleScrollbar = tk.Scrollbar(self.consoleTextBox)
        self.consoleScrollbar.pack(side=tk.RIGHT, fill=tk.BOTH)
        self.consoleTextBox["yscrollcommand"] = self.consoleScrollbar.set

        self.convertButton=tk.Button(root)
        self.convertButton["bg"] = "#f0f0f0"
        self.convertButton["font"] = ft
        self.convertButton["fg"] = "#000000"
        self.convertButton["justify"] = "center"
        self.convertButton["text"] = "Convert"
        self.convertButton.place(x=20,y=360,width=755,height=30)
        self.convertButton["command"] = self.convertButton_thread
        
        self.stopButton=tk.Button(root)
        self.stopButton["bg"] = "#f0f0f0"
        self.stopButton["font"] = ft
        self.stopButton["fg"] = "#000000"
        self.stopButton["justify"] = "center"
        self.stopButton["text"] = "Abort conversion"
        self.stopButton["command"] = self.stopButton_command

        skipLabel=tk.Label(root)
        skipLabel["font"] = ft
        skipLabel["fg"] = "#333333"
        skipLabel["justify"] = "left"
        skipLabel["text"] = "Skip converting"
        skipLabel["anchor"] = "w"
        skipLabel.place(x=20,y=310,width=93,height=30)

        self.skipMats = tk.BooleanVar()
        checkSkipMaterials=tk.Checkbutton(root)
        checkSkipMaterials["font"] = ft
        checkSkipMaterials["fg"] = "#333333"
        checkSkipMaterials["justify"] = "left"
        checkSkipMaterials["text"] = "Materials"
        checkSkipMaterials["variable"] = self.skipMats
        checkSkipMaterials.place(x=130,y=310,width=76,height=30)
        checkSkipMaterials["offvalue"] = False
        checkSkipMaterials["onvalue"] = True

        self.skipModels = tk.BooleanVar()
        checkSkipModels=tk.Checkbutton(root)
        checkSkipModels["font"] = ft
        checkSkipModels["fg"] = "#333333"
        checkSkipModels["justify"] = "center"
        checkSkipModels["text"] = "Models"
        checkSkipModels["variable"] = self.skipModels
        checkSkipModels.place(x=262,y=310,width=78,height=30)
        checkSkipModels["offvalue"] = False
        checkSkipModels["onvalue"] = True
    
    def changeSetting(self, key, value):
        settings[key] = value
        open("res/settings.json", "w").write(json.dumps(settings, indent=4))

    def popup(self):
        self.popupWindow=popupWindow(self)

    def setSteamDir(self, _dir=""):
        if _dir == "":
            dir = filedialog.askdirectory(title="Set your Steam directory")
        else:
            dir = _dir
        
        if dir is not None or dir != "":
            self.changeSetting("steamDir", dir)
            self.steamDirLabel["text"] = dir

    def setCurrentGame(self):
        self.changeSetting("currentGame", self.currentGame.get())
        gameName = gameDef[self.currentGame.get()]['gameName']
        self.currentGameLabel["text"] = gameName
        if gameName == "<none>":
            print("Warning: If you going to convert a map from a game that isn't included in the list, make sure you add all the VPK files and the directories of the game to the lists above.")

    def chooseVmfDialog_command(self):
        file = filedialog.askopenfile(mode="r", filetypes=[("Source Engine map file", "*.vmf")])
        if file is not None:
            self.vmfPath.delete(0, tkinter.constants.END)
            self.vmfPath.insert(0, file.name)

    def addVpkButton_command(self):
        file = filedialog.askopenfile(mode="r", filetypes=[("Valve pak file", "*.vpk"), ("Garry's Mod addon", "*.gma")])
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

    def aboutButton_command(self):
        alert.showinfo(
            title="About Corvid",
            message=f"Version: {version}\n\n"
            + "Author: Mehmet Yüce\n"
            + "Github: @myuce\n"
            + "Twitter: @myuce153\n\n"
            + "Icon file created by Freepik\n"
            + "https://www.flaticon.com/authors/freepik",
        )
    
    def saveConsoleLog(self):
        consoleLog = self.consoleTextBox.get(1.0, tkinter.constants.END)
        saveFile = filedialog.asksaveasfile(title="Save console log as", initialfile="Corvid-log-" + datetime.now().strftime("%d.%m.%Y_(%H.%M.%S)"), filetypes=[('Text files', '*.txt')], defaultextension=[('Text files', '*.txt')])
        if saveFile is None:
            return None
        open(saveFile.name, "w").write(consoleLog)

    def convertButton_command(self):
        # set the export directory
        outputDir = filedialog.askdirectory(title="Select a directory to export the converted map and its assets")
        if outputDir == "":
            alert.showwarning(title="Warning", message="Please select a directory to export the map!")
            exit()

        _game = self.currentGame.get()
        currentGame = gameDef[_game]

        # save the extra vpk files and directories in case the user needs them later
        vpkFiles = list(self.vpkList.get(0, self.vpkList.size() - 1))
        gameDirs = list(self.gameDirList.get(0, self.gameDirList.size() - 1))

        print(f"Corvid v{version}")
        print(f"Steam directory: {settings['steamDir']}")
        print(f"Game profile: {currentGame['gameName']}")

        def mountGame(game):
            # add the vpk files and the directories of the current game in the list
            for vpk in gameDef[game]["vpkFiles"]:
                for appDir in steamAppsDirs:
                    vpkPath = appDir + "/steamapps/common/" + gameDef[game]["gameRoot"] + "/" + vpk
                    if os.path.isfile(vpkPath):
                        vpkFiles.append(vpkPath)
                        break

            for dir in gameDef[game]["gameDirs"]:
                for appDir in steamAppsDirs:
                    dirPath = appDir + "/steamapps/common/" + gameDef[game]["gameRoot"] + "/" + dir
                    if os.path.isdir(dirPath):
                        gameDirs.append(dirPath)
                        break

        # add the vpk files and the directories of the current game in the list
        mountGame(_game)

        # if the current game profile is Garry's Mod, check for the mounted games
        if _game == "gmod":
            print("Checking for mounted games in Garry's Mod...")
            def getMounted():
                # try finding where Garry's Mod is installed
                gmodDir = ""
                for appDir in steamAppsDirs:
                    if exists(f"{appDir}/steamapps/common/GarrysMod/hl2.exe"):
                        gmodDir = f"{appDir}/steamapps/common/GarrysMod"
                
                if gmodDir == "":
                    print("Could not find Garry's Mod installation.")
                    return
                
                if not exists(f"{gmodDir}/garrysmod/cfg/mountdepots.txt"):
                    return

                mountData = parse_vdf(open(f"{gmodDir}/garrysmod/cfg/mountdepots.txt").read())

                if not "gamedepotsystem" in mountData:
                    return

                data = mountData["gamedepotsystem"]

                for game in data:
                    if data[game] == "1" and game in gameDef:
                        mountGame(game)

            getMounted()

        vmfPath = self.vmfPath.get()
        # check if the selected file is a valid VMF file
        if len(vmfPath) == "0":
            alert.showerror("Please select a VMF file!")
            exit()
        if not os.path.isfile(vmfPath):
            alert.showerror(title="Error", message="Please select a valid file!")
            exit()
        if not os.path.exists(vmfPath):
            alert.showerror(title="Error", message="VMF file does not exist.")
            exit()
        if os.path.splitext(vmfPath)[1].lower() != ".vmf":
            alert.showerror(title="Error", message="Please choose a VMF file")
            exit()
        
        # check vpks
        for vpk in vpkFiles:
            if not os.path.isfile(vpk):
                alert.showerror(title="Error", message=f"\"{vpk}\" is not a valid file!")
                exit()
            if not vpk.endswith((".vpk", ".gma")):
                alert.showerror(title="error", message=f"\"{vpk}\" is not a VPK or a GMA file!")
                exit()
        # check gamedirs
        for dir in gameDirs:
            if not os.path.isdir(dir):
                alert.showerror(title="Error", message=f"{dir} is not a valid directory.")
                exit()

        self.convertButton["state"] = "disabled"

        start = time.time()
        vmfName = os.path.splitext(os.path.basename(vmfPath))[0].lower()
        # read the map file and convert everything
        game = self.game.get()
        outputDir += f"/{vmfName}_{game}"
        print(f"Opening VMF file \"{vmfPath}\"...")
        vmfFile = open(vmfPath).read()
        print("Reading VMF file...")

        
        # prepare the necessary stuff to move and write files
        prefabDir = "prefabs" if game == "CoD4" or game == "CoD2" else "_prefabs"
        try:
            makedirs(f"{outputDir}/map_source")
            makedirs(f"{outputDir}/model_export/corvid")
            makedirs(f"{outputDir}/source_data")
            makedirs(f"{outputDir}/texture_assets/corvid")
            if game != "BO3":
                makedirs(f"{outputDir}/bin")
            else:
                makedirs(f"{outputDir}/map_source/{prefabDir}/{vmfName}")
        except:
            pass

        writePath = f"map_source/{prefabDir}/{vmfName}" if game == "BO3" else "map_source"
        print("Generating map data...")

        with open(f"{outputDir}/{writePath}/{vmfName}.map", "w") as file:
            exportMap(
                vmfFile, vpkFiles, gameDirs, game,
                self.skipMats.get(), self.skipModels.get(), vmfName, settings["convertBrush"],
                scale=Vector3(settings["scale"][0], settings["scale"][0], settings["scale"][1]), file=file
            )

        convertedDir = gettempdir() + "/corvid/converted"

        dirs = [
            "model_export/corvid",
            "source_data",
            "texture_assets/corvid"
        ]

        if game != "BO3":
            dirs.append("bin")

        print(f"Moving all converted assets to \"{outputDir}\"...")
        for folder in dirs:
            files = listdir(f"{convertedDir}/{folder}/.")
            for f in files:
                shutil.move(f"{convertedDir}/{folder}/{f}", f"{outputDir}/{folder}/{f}")

        end = time.time()
        total = ProperTime(round(end - start))
        print(f"Conversion finished in {total}")

        open(f"{outputDir}/log.txt", "w").write(self.consoleTextBox.get(1.0, tkinter.constants.END))

        self.convertButton["state"] = "active"
        exit()

    def convertButton_thread(self):
        self.conversionThread = threading.Thread(target=self.convertButton_command)
        self.conversionThread.daemon = True
        self.conversionThread.start()
        self.checkThread = threading.Thread(target=self.checkThreadFinished)
        self.checkThread.start()

    def checkThreadFinished(self):
        while self.conversionThread.is_alive():
            time.sleep(3) # we don't need to check it that often 
            pass
        # make sure the convert button is enabled even when the conversion thread fails
        self.convertButton["state"] = "active"

    def stopButton_command(self):
        pass

class TextRedirector(object):
    def __init__(self, widget, overall, current, overallLabel, currentLabel, tag="stdout"):
        self.widget = widget
        self.overall = overall
        self.current = current
        self.overallLabel = overallLabel
        self.currentLabel = currentLabel
        self.tag = tag
        self.eof = False

    def write(self, str: str):        
        # update the progress bars depending on the printed text
        # I'm not really a Python guy normally, so I'm not sure if this is the best way to do this
        overAllSteps = [
            "Opening VMF file",
            "Reading VMF file...",
            "Reading materials...",
            "Reading texture data...",
            "Extracting models...",
            "Reading model materials...",
            "Generating GDT file...",
            "Converting textures...",
            "Converting models...",
            "Generating .map file...",
            #"Converting decals...",
            "Moving all converted assets to",
            "Writing",
            "Conversion finished"
        ]
        totalSteps = len(overAllSteps)
        for i in range(totalSteps):
            if str.startswith(overAllSteps[i]):
                self.overall["value"] = ((i + 1) / totalSteps) * 100
                self.overallLabel["text"] = f"Total: {i + 1}/{totalSteps}"

        if str.endswith("|done"):
            tok = str.split("|")
            current = int(tok[0])
            total = int(tok[1])
            self.current["value"] = ((current + 1) / total) * 100
            self.currentLabel["text"] = f"Current: {current + 1}/{total}"
        else:
            if self.eof:
                self.eof = False
                self.widget.delete(1.0, "end")
            self.widget.insert("end", str, (self.tag,))
            self.widget.see("end")

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)

    # Find where Steam is installed from registry
    if settings["steamDir"] == "":
        try:
            hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\WOW6432Node\Valve\Steam")
            steamDir = winreg.QueryValueEx(hkey, "InstallPath")[0]
            steamDir = Path(steamDir).as_posix()
            app.setSteamDir(steamDir)
        except:
            pass

    # If we can't find where Steam is installed, ask the user to locate it
    while settings["steamDir"] == "":
        alert.showwarning(
            "Warning",
            message="It appears that this is your first time using Corvid.\n\n"
                        + "Please set your Steam directory in the next dialogue."
        )
        app.setSteamDir()
    
    if exists(f"{settings['steamDir']}/steamapps/libraryfolders.vdf"):
        libraryFolders = parse_vdf(open(f'{settings["steamDir"]}/steamapps/libraryfolders.vdf').read())["libraryfolders"]
        for key, value in libraryFolders.items():
            libraryDir = Path(value["path"]).as_posix()
            if libraryDir not in steamAppsDirs:
                steamAppsDirs.append(libraryDir)
    else:
        print("Cannot detect Steam libraries. Make sure your Steam directory is correct.")
    
    root.mainloop()