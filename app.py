import os
import sys
from typing import List

# When running as a windowed PyInstaller app, stdout/stderr are None
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

if os.name == "nt":
    import winreg
else:
    pass

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
from sys import stderr, stdout
from os.path import exists
from tempfile import gettempdir
from datetime import datetime
from time import gmtime, strftime
from pathlib import Path
from PIL import Image, ImageTk
from modules.MapExporter import exportMap
from modules.Progress import Progress
from glm import vec3
from modules.vdfutils import parse_vdf

# global settings
with open("res/settings.json", encoding="utf-8") as f:
    settings = json.loads(f.read())
with open("res/gameDef.json", encoding="utf-8") as f:
    gameDef = json.loads(f.read())
with open("res/version.txt", encoding="utf-8") as f:
    version = f.read().split("\n")[0]
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

def get_steam_dir() -> str | None:
    if os.name == "nt":
        try:
            hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\WOW6432Node\\Valve\\Steam")
            steamDir = winreg.QueryValueEx(hkey, "InstallPath")[0]
            steamDir = Path(steamDir).as_posix()
            return steamDir
        except:
            return None
    else:
        home = Path.home()
        paths = [
            f"{home}/.steam/steam",
            f"{home}/.local/share/Steam",
            f"{home}/.var/app/com.valvesoftware.Steam/data/Steam"
        ]
        for p in paths:
            if exists(p):
                return p
        return f"{home}/.steam/steam"

def load_library_folders_data(steam_dir: str | None) -> List[str] | None:
    if steam_dir is None or steam_dir == "":
        steam_dir = get_steam_dir()
    
    if steam_dir is None:
        return None

    library_folders_path = f"{steam_dir}/steamapps/libraryfolders.vdf"
    if not exists(library_folders_path):
        return None

    try:
        with open(library_folders_path, "r", encoding="utf-8", errors="replace") as file:
            data = parse_vdf(file.read(), allowRepeats=True)
        
        if data is None or "libraryfolders" not in data:
            return None

        folders: dict = data["libraryfolders"]
        paths = []
        for folder in folders.values():
            if isinstance(folder, dict) and "path" in folder:
                 paths.append(Path(folder["path"]).as_posix())
        
        return list(set(paths))
    except Exception as e:
        print(f"Error loading library folders: {e}")
        return None

class popupWindow:
    def __init__(self, app: 'App'):
        self.app = app
        top = self.top = tk.Toplevel(app.root)
        top.title("Set export scale")
        top.resizable(0, 0)
        top.wm_transient()
        top.grab_set_global()
        top.bind("<Escape>", lambda x: top.destroy())
        top.bind("<Return>", lambda x: self.okCommand())
        top.focus_force()
        top.transient(app.root)

        ft = app.font
        top.columnconfigure(1, weight=1)
        top["padx"] = 10
        top["pady"] = 10

        self.text = tk.Label(top, text="Please enter the scale value", font=ft)
        self.text.grid(row=0, column=0, columnspan=2, pady=(0, 8))

        self.textXY = tk.Label(top, text="X/Y", font=ft, anchor="w")
        self.textXY.grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 4))
        self.scaleXY = tk.Entry(top, font=ft, width=16)
        self.scaleXY.focus_force()
        self.scaleXY.insert(0, settings["scale"][0])
        self.scaleXY.grid(row=1, column=1, sticky="ew", pady=(0, 4))

        self.textZ = tk.Label(top, text="Z", font=ft, anchor="w")
        self.textZ.grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        self.scaleZ = tk.Entry(top, font=ft, width=16)
        self.scaleZ.insert(0, settings["scale"][1])
        self.scaleZ.grid(row=2, column=1, sticky="ew", pady=(0, 8))

        buttons = tk.Frame(top)
        buttons.grid(row=3, column=0, columnspan=2, sticky="ew")
        buttons.columnconfigure((0, 1), weight=1, uniform="buttons")
        self.ok = tk.Button(buttons, text="OK", font=ft, command=self.okCommand)
        self.ok.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        self.cancel = tk.Button(buttons, text="Cancel", font=ft, command=top.destroy)
        self.cancel.grid(row=0, column=1, sticky="ew", padx=(3, 0))

        # center over the main window
        top.update_idletasks()
        x = app.root.winfo_rootx() + (app.root.winfo_width() - top.winfo_reqwidth()) // 2
        y = app.root.winfo_rooty() + (app.root.winfo_height() - top.winfo_reqheight()) // 2
        top.geometry(f"+{x}+{y}")

    def okCommand(self):
        xy = z = None
        try:
            xy, z = float(self.scaleXY.get()), float(self.scaleZ.get())
        except ValueError:
            alert.showwarning(title="Error", message="Please enter a proper number.")
            return
        else:
            if xy is not None and z is not None:
                self.app.changeSetting("scale", [xy, z])
                self.top.destroy()

class ConversionAborted(Exception):
    pass

class App:
    def __init__(self, root: tk.Tk):
        root.title(f"Corvid - v{version}")
        
        icon_path = "res/icon.ico"

        icon_img = ImageTk.PhotoImage(Image.open(icon_path).convert("RGBA"))
        root.iconphoto(True, icon_img)
        
        self.root = root
        self._abort = threading.Event()
        self.conversionThread = None
        self._conversionResult = None
        width=800
        height=640
        screenwidth = root.winfo_screenwidth()
        screenheight = root.winfo_screenheight()
        alignstr = '%dx%d+%d+%d' % (width, height, (screenwidth - width) / 2, (screenheight - height) / 2 - 30)
        root.geometry(alignstr)
        ft = self.font = tkFont.Font(family='Verdana',size=8)

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
            if gameDef[game]["gameName"] == "separator":
                currentGameMenu.add_separator()
            else:
                currentGameMenu.add_radiobutton(label=gameDef[game]["gameName"], variable=self.currentGame, value=game, command=self.setCurrentGame)

        settingsMenu.add_cascade(label="Select game profile", menu=currentGameMenu)
        settingsMenu.add_command(label="Change export scale", command=self.popup)
        settingsMenu.add_separator()
        settingsMenu.add_command(label="Set Steam directory", command=self.setSteamDir)
        settingsMenu.add_command(label="Detect Steam directory", command=self.detectSteamDir)

        helpMenu = tk.Menu(self.menuBar, tearoff=0)
        helpMenu.add_command(label="Corvid on GitHub", command=lambda: webbrowser.open("https://github.com/KILLTUBE/corvid"))
        helpMenu.add_command(label="Corvid wiki", command=lambda: webbrowser.open("https://github.com/KILLTUBE/corvid/wiki"))
        helpMenu.add_command(label="Video tutorial", command=lambda: webbrowser.open("https://www.youtube.com/watch?v=izALMNZjgkA"))
        #helpMenu.add_command(label="Check for new versions", command=lambda: print("Checking for new versions..."))
        helpMenu.add_separator()
        # helpMenu.add_command(label="Support me on Patreon", command=lambda: webbrowser.open("https://www.patreon.com/johndoe_"))
        helpMenu.add_command(label="About Corvid", command=self.aboutButton_command)
        self.menuBar.add_cascade(label="Help", menu=helpMenu)

        root.config(menu=self.menuBar)

        # Everything below is laid out with grid so it stays aligned at any font size and window size.
        # Columns 1-3 of the main frame hold the Browse/Add/Remove/Clear buttons.
        textColor = "#333333"

        def makeLabel(parent, text="", **kwargs):
            return tk.Label(parent, text=text, font=ft, fg=textColor, anchor="w", **kwargs)

        def makeButton(parent, text, command, **kwargs):
            return tk.Button(parent, text=text, command=command, font=ft, fg="#000000", **kwargs)

        def makeRow(parent, row, pady=(0, 10), weight=0):
            """Creates a frame that spans the whole width of the main frame."""
            frame = tk.Frame(parent)
            frame.grid(row=row, column=0, columnspan=4, sticky="nsew", pady=pady)
            frame.columnconfigure(0, weight=1)
            parent.rowconfigure(row, weight=weight)
            return frame

        def makeList(parent, row):
            """Creates a listbox with its scrollbars next to it, so they don't cover long paths."""
            frame = makeRow(parent, row, weight=1)
            frame.rowconfigure(0, weight=1)
            listbox = tk.Listbox(frame, selectmode=tk.EXTENDED, borderwidth=1, font=ft, fg=textColor, width=1, height=3)
            listbox.grid(row=0, column=0, sticky="nsew")
            scrollY = tk.Scrollbar(frame, orient=tk.VERTICAL, command=listbox.yview)
            scrollY.grid(row=0, column=1, sticky="ns")
            scrollX = tk.Scrollbar(frame, orient=tk.HORIZONTAL, command=listbox.xview)
            scrollX.grid(row=1, column=0, sticky="ew")
            listbox["yscrollcommand"] = scrollY.set
            listbox["xscrollcommand"] = scrollX.set
            return listbox

        def makeListHeader(parent, row, text, addCommand, removeCommand, clearCommand):
            makeLabel(parent, text).grid(row=row, column=0, sticky="w", pady=(0, 10))
            buttons = (("Add", addCommand), ("Remove", removeCommand), ("Clear", clearCommand))
            for column, (buttonText, command) in enumerate(buttons, 1):
                makeButton(parent, buttonText, command).grid(row=row, column=column, sticky="ew", padx=(10, 0), pady=(0, 10))

        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main = tk.Frame(root, padx=20, pady=15)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        for column in (1, 2, 3):
            main.columnconfigure(column, uniform="buttons", minsize=115)

        # VMF file
        vmfFrame = tk.Frame(main)
        vmfFrame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        vmfFrame.columnconfigure(1, weight=1)
        makeLabel(vmfFrame, "VMF file").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.vmfPath = tk.Entry(vmfFrame, borderwidth=1, font=ft, fg=textColor, width=1)
        self.vmfPath.grid(row=0, column=1, sticky="ew", ipady=4)
        makeButton(main, "Browse", self.chooseVmfDialog_command).grid(row=0, column=3, sticky="ew", padx=(10, 0), pady=(0, 10))

        # resource files and asset directories
        makeListHeader(main, 1, "Additional resource files (VPK, BSP, GMAD)", self.addVpkButton_command, self.deleteVpkButton_command, lambda: self.vpkList.delete(0, tk.END))
        self.vpkList = makeList(main, 2)
        makeListHeader(main, 3, "Asset directories", self.addGameDirButton_command, self.deleteDirButton_command, lambda: self.gameDirList.delete(0, tk.END))
        self.gameDirList = makeList(main, 4)

        # target game and things to skip share the same columns
        options = tk.Frame(main)
        options.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(0, 10))
        for column in range(1, 5):
            options.columnconfigure(column, weight=1, uniform="options")

        # decide what game the map is going to be converted for
        self.game = tk.StringVar()
        self.game.set(settings["game"])
        makeLabel(options, "Target game").grid(row=0, column=0, sticky="w", padx=(0, 20), pady=(0, 5))
        targets = (("Black Ops 3", "BO3"), ("WaW / Black Ops", "WaW"), ("CoD 4", "CoD4"), ("CoD 2", "CoD2"))
        for column, (text, value) in enumerate(targets, 1):
            tk.Radiobutton(
                options, text=text, value=value, variable=self.game, font=ft, fg=textColor,
                command=lambda value=value: self.changeSetting("game", value)
            ).grid(row=0, column=column, sticky="w", pady=(0, 5))

        makeLabel(options, "Skip converting").grid(row=1, column=0, sticky="w", padx=(0, 20))
        self.skipMats = tk.BooleanVar()
        tk.Checkbutton(options, text="Materials", variable=self.skipMats, onvalue=True, offvalue=False, font=ft, fg=textColor).grid(row=1, column=1, sticky="w")
        self.skipModels = tk.BooleanVar()
        tk.Checkbutton(options, text="Models", variable=self.skipModels, onvalue=True, offvalue=False, font=ft, fg=textColor).grid(row=1, column=2, sticky="w")

        # the convert and abort buttons take turns in the same cell
        self.convertButton = makeButton(main, "Convert", self.convertButton_thread)
        self.convertButton.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(0, 10), ipady=3)
        self.stopButton = makeButton(main, "Abort conversion", self.stopButton_command)
        self.stopButton.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(0, 10), ipady=3)
        self.stopButton.grid_remove()

        # progress bars
        progress = makeRow(main, 7, pady=(0, 5))
        progress.columnconfigure(0, weight=0, minsize=150)
        progress.columnconfigure(1, weight=1)
        self.overallLabel = makeLabel(progress, "Total: n/a")
        self.overallLabel.grid(row=0, column=0, sticky="w")
        self.progressOverall = Progressbar(progress)
        self.progressOverall.grid(row=0, column=1, sticky="ew", pady=(0, 3))
        self.progressOverall["value"] = 0
        self.currentLabel = makeLabel(progress, "Current: n/a")
        self.currentLabel.grid(row=1, column=0, sticky="w")
        self.progressCurrent = Progressbar(progress)
        self.progressCurrent.grid(row=1, column=1, sticky="ew")
        self.progressCurrent["value"] = 0

        # console
        consoleFrame = makeRow(main, 8, pady=(0, 5), weight=3)
        consoleFrame.rowconfigure(0, weight=1)
        self.consoleTextBox = tk.Text(consoleFrame, borderwidth=1, font=ft, fg=textColor, width=1, height=6)
        self.consoleTextBox.grid(row=0, column=0, sticky="nsew")
        sys.stdout = ConsoleWriter(self.consoleTextBox, self._abort, stdout)
        sys.stderr = ConsoleWriter(self.consoleTextBox, self._abort, stderr)
        self.consoleScrollbar = tk.Scrollbar(consoleFrame, orient=tk.VERTICAL, command=self.consoleTextBox.yview)
        self.consoleScrollbar.grid(row=0, column=1, sticky="ns")
        self.consoleTextBox["yscrollcommand"] = self.consoleScrollbar.set

        # status row; a width of 1 makes a long Steam path get cut off instead of pushing the game out
        status = makeRow(main, 9, pady=0)
        self.steamDirLabel = makeLabel(status, settings["steamDir"] if settings["steamDir"] != "" else "Steam directory not found!", width=1)
        self.steamDirLabel.grid(row=0, column=0, sticky="ew", padx=(0, 20))
        self.currentGameLabel = makeLabel(status, self._sourceGameText(gameDef[settings["currentGame"]]["gameName"] if settings["currentGame"] in gameDef else "<none>"))
        self.currentGameLabel.grid(row=0, column=1, sticky="e")

        root.update_idletasks()
        root.minsize(root.winfo_reqwidth(), root.winfo_reqheight())

    def _sourceGameText(self, gameName):
        return f"Source game: {gameName}"

    def changeSetting(self, key, value):
        settings[key] = value
        with open("res/settings.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(settings, indent=4))

    def popup(self):
        self.popupWindow=popupWindow(self)

    def setSteamDir(self, _dir="", refresh=True):
        """Set the Steam directory. Returns True if a directory was set."""
        if _dir == "":
            dir = filedialog.askdirectory(title="Set your Steam directory")
        else:
            dir = _dir

        if not dir:
            return False

        self.changeSetting("steamDir", dir)
        self.steamDirLabel["text"] = dir
        if refresh:
            self.refreshSteamLibraries()
        return True

    def detectSteamDir(self):
        steamDir = get_steam_dir()
        if not steamDir:
            alert.showwarning(
                title="Warning",
                message="Could not detect the Steam directory.\n\nPlease set it manually from Settings > Set Steam directory."
            )
            return
        self.setSteamDir(steamDir)

    def refreshSteamLibraries(self):
        """Re-read the Steam library folders for the current Steam directory."""
        library_paths = load_library_folders_data(settings["steamDir"])
        steamAppsDirs.clear()
        if library_paths:
            for path in library_paths:
                if path not in steamAppsDirs:
                    steamAppsDirs.append(path)
        else:
            print("Cannot detect Steam libraries. Make sure your Steam directory is correct.")

    def setCurrentGame(self):
        self.changeSetting("currentGame", self.currentGame.get())
        gameName = gameDef[self.currentGame.get()]['gameName']
        self.currentGameLabel["text"] = self._sourceGameText(gameName)
        if gameName == "<none>":
            print("Warning: If you are going to convert a map from a game that isn't included in the list, make sure you add all the VPK files and the directories of the game to the lists above.")

    def chooseVmfDialog_command(self):
        file = filedialog.askopenfilename(filetypes=[("Source Engine map file", "*.vmf")])
        if file:
            self.vmfPath.delete(0, tkinter.constants.END)
            self.vmfPath.insert(0, file)

    def addVpkButton_command(self):
        file = filedialog.askopenfilename(filetypes=[("Valve pak file", "*.vpk"), ("Garry's Mod addon", "*.gma"), ("BSP map file", "*.bsp")])
        if file:
            self.vpkList.insert(tk.END, file)

    def addGameDirButton_command(self):
        dir = filedialog.askdirectory()
        # askdirectory returns "" (or an empty tuple) when canceled
        if dir:
            self.gameDirList.insert(tk.END, dir)

    def deleteVpkButton_command(self):
        for file in reversed(self.vpkList.curselection()):
            self.vpkList.delete(file)

    def deleteDirButton_command(self):
        for dir in reversed(self.gameDirList.curselection()):
            self.gameDirList.delete(dir)

    def clearConsoleButton_command(self):
        self.consoleTextBox.delete(0.0, tkinter.constants.END)

    def aboutButton_command(self):
        alert.showinfo(
            title="About Corvid",
            message=f"Version: {version}\n\n"
            + "Author: Mehmet Yüce\n"
            + "GitHub: @myuce\n"
            + "Twitter: @myuce153\n\n"
            + "Icon file created by Freepik\n"
            + "https://www.flaticon.com/authors/freepik",
        )
    
    def saveConsoleLog(self):
        consoleLog = self.consoleTextBox.get(1.0, tkinter.constants.END)
        savePath = filedialog.asksaveasfilename(title="Save console log as", initialfile="Corvid-log-" + datetime.now().strftime("%d.%m.%Y_(%H.%M.%S)"), filetypes=[('Text files', '*.txt')], defaultextension='.txt')
        if not savePath:
            return
        with open(savePath, "w", encoding="utf-8") as f:
            f.write(consoleLog)

    def _prepareConversion(self):
        """Validate the user's input and collect everything the conversion needs.

        Runs on the main thread (shows dialogs). Returns None if the conversion should not start.
        """
        _game = self.currentGame.get()
        if _game not in gameDef:
            alert.showerror(title="Error", message="Please select a game profile from Settings > Select game profile.")
            return None

        vmfPath = self.vmfPath.get()
        # check if the selected file is a valid VMF file
        if len(vmfPath) == 0:
            alert.showerror(title="Error", message="Please select a VMF file!")
            return None
        if not os.path.exists(vmfPath):
            alert.showerror(title="Error", message="VMF file does not exist.")
            return None
        if not os.path.isfile(vmfPath):
            alert.showerror(title="Error", message="Please select a valid file!")
            return None
        if os.path.splitext(vmfPath)[1].lower() != ".vmf":
            alert.showerror(title="Error", message="Please choose a VMF file")
            return None

        # save the extra vpk files and directories in case the user needs them later
        vpkFiles = list(self.vpkList.get(0, self.vpkList.size() - 1))
        gameDirs = list(self.gameDirList.get(0, self.gameDirList.size() - 1))

        # check vpks
        for vpk in vpkFiles:
            if not os.path.isfile(vpk):
                alert.showerror(title="Error", message=f"\"{vpk}\" is not a valid file!")
                return None
            if not vpk.lower().endswith((".vpk", ".gma", ".bsp")):
                alert.showerror(title="Error", message=f"\"{vpk}\" is not a VPK, GMA or BSP file!")
                return None
        # check gamedirs
        for dir in gameDirs:
            if not os.path.isdir(dir):
                alert.showerror(title="Error", message=f"{dir} is not a valid directory.")
                return None

        # set the export directory
        outputDir = filedialog.askdirectory(title="Select a directory to export the converted map and its assets")
        if not outputDir:
            alert.showwarning(title="Warning", message="Please select a directory to export the map!")
            return None

        return {
            "profile": _game,
            "vmfPath": vmfPath,
            "outputDir": outputDir,
            "vpkFiles": vpkFiles,
            "gameDirs": gameDirs,
            "game": self.game.get(),
            "skipMats": self.skipMats.get(),
            "skipModels": self.skipModels.get(),
            "scale": list(settings["scale"]),
            "steamAppsDirs": list(steamAppsDirs),
        }

    def convertButton_command(self, params):
        """Runs on the worker thread. Must not touch Tk widgets or show dialogs;
        results are handed back to the main thread through self._conversionResult."""
        result = {"aborted": False, "error": None, "logPath": None}
        try:
            self._convert(params, result)
        except ConversionAborted:
            result["aborted"] = True
        except Exception as e:
            import traceback
            result["error"] = (e, traceback.format_exc())
        finally:
            self._conversionResult = result
            self._abort.clear()

    def _convert(self, params, result):
        _game = params["profile"]
        currentGame = gameDef[_game]
        vmfPath = params["vmfPath"]
        outputDir = params["outputDir"]
        vpkFiles = params["vpkFiles"]
        gameDirs = params["gameDirs"]
        appDirs = params["steamAppsDirs"]

        progress = self._create_progress()

        print(f"Corvid v{version}")
        print(f"Steam directory: {settings['steamDir']}")
        print(f"Game profile: {currentGame['gameName']}")

        def resolveGameRoot(appDir, gameRoot):
            """Resolve the game root directory case-insensitively on Linux."""
            commonDir = appDir + "/steamapps/common"
            if os.path.isdir(commonDir + "/" + gameRoot):
                return gameRoot
            # case-insensitive fallback
            try:
                for entry in os.listdir(commonDir):
                    if entry.lower() == gameRoot.lower():
                        return entry
            except OSError:
                pass
            return gameRoot

        def mountGame(game):
            gameRoot = gameDef[game]["gameRoot"]
            # add the vpk files and the directories of the current game in the list
            for vpk in gameDef[game]["vpkFiles"]:
                for appDir in appDirs:
                    resolved = resolveGameRoot(appDir, gameRoot)
                    vpkPath = appDir + "/steamapps/common/" + resolved + "/" + vpk
                    if os.path.isfile(vpkPath):
                        vpkFiles.append(vpkPath)
                        break

            for dir in gameDef[game]["gameDirs"]:
                for appDir in appDirs:
                    resolved = resolveGameRoot(appDir, gameRoot)
                    dirPath = appDir + "/steamapps/common/" + resolved + "/" + dir
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
                for appDir in appDirs:
                    if exists(f"{appDir}/steamapps/common/GarrysMod/hl2.exe"):
                        gmodDir = f"{appDir}/steamapps/common/GarrysMod"
                
                if gmodDir == "":
                    print("Could not find Garry's Mod installation.")
                    return
                
                if not exists(f"{gmodDir}/garrysmod/cfg/mountdepots.txt"):
                    return

                with open(f"{gmodDir}/garrysmod/cfg/mountdepots.txt", encoding="utf-8", errors="replace") as f:
                    mountData = parse_vdf(f.read())

                if not "gamedepotsystem" in mountData:
                    return

                data = mountData["gamedepotsystem"]

                for game in data:
                    if data[game] == "1" and game in gameDef:
                        mountGame(game)

            getMounted()

        start = time.time()
        vmfName = os.path.splitext(os.path.basename(vmfPath))[0].lower()
        # read the map file and convert everything
        game = params["game"]
        outputDir += f"/{vmfName}_{game}"
        progress.log(f"Opening VMF file \"{vmfPath}\"...")
        with open(vmfPath, encoding="utf-8", errors="replace") as f:
            vmfFile = f.read()
        progress.log("Reading VMF file...")

        # prepare the necessary stuff to move and write files
        prefabDir = "prefabs" if game == "CoD4" or game == "CoD2" else "_prefabs"
        os.makedirs(f"{outputDir}/map_source", exist_ok=True)
        os.makedirs(f"{outputDir}/model_export/corvid", exist_ok=True)
        os.makedirs(f"{outputDir}/source_data", exist_ok=True)
        os.makedirs(f"{outputDir}/texture_assets/corvid", exist_ok=True)
        if game != "BO3":
            os.makedirs(f"{outputDir}/bin", exist_ok=True)
        else:
            os.makedirs(f"{outputDir}/map_source/{prefabDir}/{vmfName}", exist_ok=True)

        writePath = f"map_source/{prefabDir}/{vmfName}" if game == "BO3" else "map_source"
        scale = params["scale"]

        with open(f"{outputDir}/{writePath}/{vmfName}.map", "w") as file:
            exportMap(
                vmfFile, vpkFiles, gameDirs, game,
                params["skipMats"], params["skipModels"], vmfName,
            scale=vec3(scale[0], scale[0], scale[1]), file=file,
            outputDir=outputDir, progress=progress
            )

        end = time.time()
        total = ProperTime(round(end - start))
        progress.log(f"Conversion finished in {total}")

        # the log is written by the main thread once the console has caught up
        result["logPath"] = f"{outputDir}/log.txt"

    def _create_progress(self):
        def on_log(message):
            if self._abort.is_set():
                raise ConversionAborted()
            self.consoleTextBox.after(0, self._append_console, message + "\n")

        def on_overall(step, total):
            if self._abort.is_set():
                raise ConversionAborted()
            value = (step / total) * 100
            text = f"Total: {step}/{total}"
            self.progressOverall.after(0, self._update_bar, self.progressOverall, value, self.overallLabel, text)

        def on_current(step, total):
            if self._abort.is_set():
                raise ConversionAborted()
            value = (step / total) * 100
            text = f"Current: {step}/{total}"
            self.progressCurrent.after(0, self._update_bar, self.progressCurrent, value, self.currentLabel, text)

        return Progress(on_log=on_log, on_overall=on_overall, on_current=on_current)

    def _append_console(self, text):
        self.consoleTextBox.insert("end", text)
        self.consoleTextBox.see("end")

    def _update_bar(self, bar, value, label, text):
        bar["value"] = value
        label["text"] = text

    def convertButton_thread(self):
        if self.conversionThread is not None and self.conversionThread.is_alive():
            return

        # all dialogs and validation happen here, on the main thread, before the worker starts
        params = self._prepareConversion()
        if params is None:
            return

        self._abort.clear()
        self._conversionResult = None
        self.conversionThread = threading.Thread(target=self.convertButton_command, args=(params,))
        self.conversionThread.daemon = True
        self.convertButton.grid_remove()
        self.stopButton.grid()
        self.conversionThread.start()
        self._pollThread()

    def _pollThread(self):
        if self.conversionThread.is_alive():
            self.root.after(200, self._pollThread)
        else:
            self.stopButton.grid_remove()
            self.convertButton.grid()
            # the worker clears the flag too; clear again in case Abort was clicked as it was finishing
            self._abort.clear()
            self._conversionFinished(self._conversionResult or {})

    def _conversionFinished(self, result):
        """Runs on the main thread after the worker has exited."""
        if result.get("aborted"):
            self._append_console("Conversion aborted by user.\n")
        elif result.get("error") is not None:
            e, tb = result["error"]
            self._append_console(tb)
            alert.showerror(title="Conversion failed", message=f"An error occurred during the conversion:\n\n{e}")
        elif result.get("logPath"):
            # give console writes still queued by the worker (via after(0)) time to land before saving the log
            self.root.after(250, self._writeLog, result["logPath"])

    def _writeLog(self, logPath):
        try:
            with open(logPath, "w", encoding="utf-8") as f:
                f.write(self.consoleTextBox.get(1.0, tkinter.constants.END))
        except OSError as e:
            self._append_console(f"Could not write log file: {e}\n")

    def stopButton_command(self):
        # aborting only makes sense while the worker is running
        if self.conversionThread is not None and self.conversionThread.is_alive():
            self._abort.set()

class ConsoleWriter(object):
    """Redirects stdout/stderr writes to a Tkinter Text widget (thread-safe)."""

    def __init__(self, widget, abort_event=None, tag="stdout"):
        self.widget = widget
        self.abort_event = abort_event
        self.tag = tag

    def flush(self):
        pass

    def _append(self, text):
        self.widget.insert("end", text, (self.tag,))
        self.widget.see("end")

    def write(self, text: str):
        # only abort the conversion (worker) thread; prints from the main thread must never raise
        if (self.abort_event is not None and self.abort_event.is_set()
                and threading.current_thread() is not threading.main_thread()):
            raise ConversionAborted()
        self.widget.after(0, self._append, text)

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)

    # Find where Steam is installed
    if settings["steamDir"] == "":
        steamDir = get_steam_dir()
        if steamDir:
            app.setSteamDir(steamDir, refresh=False)

    # If we can't find where Steam is installed, ask the user to locate it
    if settings["steamDir"] == "":
        alert.showwarning(
            title="Warning",
            message="It appears that this is your first time using Corvid.\n\n"
                        + "Please set your Steam directory in the next dialog."
        )
        while not app.setSteamDir(refresh=False):
            retry = alert.askretrycancel(
                title="Steam directory not set",
                message="No Steam directory was selected.\n\n"
                        + "Press Retry to choose it again, or Cancel to continue without it. "
                        + "You can set it later from Settings > Set Steam directory."
            )
            if not retry:
                break

    app.refreshSteamLibraries()

    # If temp folder already exists, delete it before we proceed as it causes issues
    temp_path = os.path.join(gettempdir(), 'corvid')
    if exists(temp_path):
        shutil.rmtree(temp_path)
    
    root.mainloop()
