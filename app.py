from os import makedirs, listdir, name
import os.path
import sys
from sys import stderr, stdout
import tkinter as tk
import tkinter.constants
import tkinter.messagebox as alert
import tkinter.font as tkFont
from tkinter import filedialog
from tkinter.ttk import Progressbar
import time 
from threading import *
import shutil
from tempfile import gettempdir, tempdir
import json
import webbrowser
from datetime import datetime
from modules.MapExporter import exportMap

# global settings
settings = json.loads(open("res/settings.json").read())
gameDef = json.loads(open("res/gameDef.json").read())
gameDefCustom = json.loads(open("res/gameDef.json").read())
version = open("res/version.txt").read().split("\n")[0]

class App:
    def __init__(self, root: tk.Tk):
        root.title(f"Corvid - v{version}")
        root.iconbitmap("res/icon.ico")
        width=800
        height=620
        screenwidth = root.winfo_screenwidth()
        screenheight = root.winfo_screenheight()
        alignstr = '%dx%d+%d+%d' % (width, height, (screenwidth - width) / 2, (screenheight - height) / 2 - 30)
        root.geometry(alignstr)
        root.resizable(width=False, height=False)
        ft = tkFont.Font(family='Verdana',size=8)

        # menu bar
        menuBar = tk.Menu(root)
        # file menu
        fileMenu = tk.Menu(menuBar, tearoff=0)
        fileMenu.add_command(label="Select VMF file", command=self.chooseVmfDialog_command)
        fileMenu.add_command(label="Clear console", command=self.clearConsoleButton_command)
        fileMenu.add_command(label="Save console log", command=self.saveConsoleLog)

        fileMenu.add_separator()
        fileMenu.add_command(label="Exit", command=root.quit)
        menuBar.add_cascade(label="File", menu=fileMenu)

        # edit menu
        settingsMenu = tk.Menu(menuBar, tearoff=0)
        menuBar.add_cascade(label="Settings", menu=settingsMenu)

        self.currentGame = tk.IntVar(value=settings["currentGame"] if settings["currentGame"] != -1 else len(gameDef) - 1)

        currentGameMenu = tk.Menu(menuBar, tearoff=0)
        for i in range(len(gameDef)):
            if gameDef[i]["gameName"] == "seperator":
                currentGameMenu.add_separator()
            else:
                currentGameMenu.add_radiobutton(label=gameDef[i]["gameName"], variable=self.currentGame, value=i, command=self.setCurrentGame)

        settingsMenu.add_cascade(label="Select game profile", menu=currentGameMenu)
        settingsMenu.add_separator()
        settingsMenu.add_command(label="Set Steam directory", command=self.setSteamDir)

        helpMenu = tk.Menu(menuBar, tearoff=0)
        helpMenu.add_command(label="Corvid on Github", command=lambda: webbrowser.open("https://github.com/KILLTUBE/corvid"))
        helpMenu.add_command(label="Corvid wiki", command=lambda: webbrowser.open("https://github.com/KILLTUBE/corvid/wiki"))
        helpMenu.add_command(label="Video tutorial", command=lambda: alert.showwarning(title="Warning", message="Video tutorial is not ready yet."))
        #helpMenu.add_command(label="Check for new versions", command=lambda: print("Checking for new versions..."))
        helpMenu.add_separator()
        helpMenu.add_command(label="About Corvid", command=self.aboutButton_command)
        menuBar.add_cascade(label="Help", menu=helpMenu)

        root.config(menu=menuBar)

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
        self.vmfPath.place(x=80,y=10,width=690,height=30)

        vpkLabel=tk.Label(root)
        vpkLabel["font"] = ft
        vpkLabel["fg"] = "#333333"
        vpkLabel["justify"] = "left"
        vpkLabel["text"] = "VPK files"
        vpkLabel["anchor"] = "w"
        vpkLabel.place(x=20,y=50,width=100,height=30)

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
        radioBO3.place(x=134,y=270,width=84,height=30)
        radioBO3["value"] = True

        radioOld=tk.Radiobutton(root, variable=self.BO3)
        radioOld["font"] = ft
        radioOld["fg"] = "#333333"
        radioOld["justify"] = "left"
        radioOld["text"] = "Cod 4/5/7"
        radioOld.place(x=270,y=270,width=80,height=30)
        radioOld["value"] = False
        
        radioBO3.select() # default value

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

        convertButton=tk.Button(root)
        convertButton["bg"] = "#f0f0f0"
        convertButton["font"] = ft
        convertButton["fg"] = "#000000"
        convertButton["justify"] = "center"
        convertButton["text"] = "Convert"
        convertButton.place(x=20,y=360,width=755,height=30)
        convertButton["command"] = self.convertButton_thread

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

        # if there are any vpk files saved in settings.json, add them to the lists
        for vpk in settings["vpkFiles"]:
            self.vpkList.insert(0, vpk)
        for gameDir in settings["gameDirs"]:
            self.gameDirList.insert(0, gameDir)

    def setSteamDir(self):
        dir = filedialog.askdirectory(title="Set your Steam directory")
        if dir is not None:
            settings["steamDir"] = dir
            open("res/settings.json", "w").write(json.dumps(settings, indent=4))
            self.steamDirLabel["text"] = dir

    def setCurrentGame(self):
        settings["currentGame"] = self.currentGame.get()
        open("res/settings.json", "w").write(json.dumps(settings, indent=4))
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
        # save the extra vpk files and directories in case the user needs them later
        vpkFiles = list(self.vpkList.get(0, self.vpkList.size() - 1))
        gameDirs = list(self.gameDirList.get(0, self.gameDirList.size() - 1))
        settings["vpkFiles"] = vpkFiles
        settings["gameDirs"] = gameDirs
        open("res/settings.json", "w").write(json.dumps(settings, indent=4))

        # add the vpk files and the directories of the current game in the list
        for vpk in gameDef[self.currentGame.get()]["vpkFiles"]:
            vpkFiles.append(settings["steamDir"] + "/steamapps/common/" + gameDef[self.currentGame.get()]["gameRoot"] + "/" + vpk)

        for dir in gameDef[self.currentGame.get()]["gameDirs"]:
            gameDirs.append(settings["steamDir"] + "/steamapps/common/" + gameDef[self.currentGame.get()]["gameRoot"] + "/" + dir)

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

        start = time.time()
        vmfName = os.path.splitext(os.path.basename(vmfPath))[0].lower()
        # read the map file and convert everything
        outputDir += f"/{vmfName}_converted"
        print(f"Opening VMF file \"{vmfPath}\"...")
        vmfFile = open(vmfPath)
        print("Reading VMF file...")
        BO3 = self.BO3.get()
        res = exportMap(vmfFile, vpkFiles, gameDirs, BO3, self.skipMats.get(), self.skipModels.get(), vmfName)
        # prepare the necessary stuff to move and write files
        try:
            makedirs(f"{outputDir}/map_source")
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
    def __init__(self, widget, overall, current, overallLabel, currentLabel, tag="stdout"):
        self.widget = widget
        self.overall = overall
        self.current = current
        self.overallLabel = overallLabel
        self.currentLabel = currentLabel
        self.tag = tag
        self.eof = False

    def write(self, str):        
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

    while settings["steamDir"] == "":
        alert.showwarning(
            "Warning",
            message="It appears that this is your first time using Corvid.\n\n"
                        + "Please set your Steam directory in the next dialogue."
        )
        app.setSteamDir()

    root.mainloop()
