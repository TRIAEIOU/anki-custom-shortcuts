#Python 3.7.0
from aqt import mw
from aqt.qt import *
from anki.hooks import runHook
from aqt.utils import showWarning
from aqt.toolbar import Toolbar
from aqt.editor import Editor,EditorWebView
from aqt.reviewer import Reviewer
from anki.utils import json
from bs4 import BeautifulSoup
import warnings


#TODO: Change the main page highlight & editor toolbar to reflect changed keys

#Gets config.json as config
config = mw.addonManager.getConfig(__name__)
config_scuts = {}
CS_CONFLICTSTR = "Custom Shortcut Conflicts: \n\n"


#There is a weird interaction with QShortcuts wherein if there are 2 (or more)
#QShortcuts mapped to the same key and function and both are enabled,
#the shortcut doesn't work

#Part of this code exploits that by adding QShortcuts mapped to the defaults
#and activating/deactivating them to deactivate/activate default shortcuts

#There isn't an obvious way to get the original QShortcut objects, as
#The addons executes after the setup phase (which creates QShortcut objects)

def cs_traverseKeys(Rep, D):
    ret = {}
    for key in D:
        if isinstance(D[key],dict):
            ret[key] = cs_traverseKeys(Rep,D[key])
        elif D[key] not in Rep:
            ret[key] = D[key]
        else:
            ret[key] = Rep[D[key]]
    return ret


def cs_translateKeys():
    global config_scuts
    Qt_functions = {"Qt.Key_Enter":Qt.Key_Enter, 
                    "Qt.Key_Return":Qt.Key_Return,
                    "Qt.Key_Escape":Qt.Key_Escape,
                    "Qt.Key_Space":Qt.Key_Space,
                    "Qt.Key_Tab":Qt.Key_Tab,
                    "Qt.Key_Backspace":Qt.Key_Backspace,
                    "Qt.Key_Delete":Qt.Key_Delete}
    config_scuts = cs_traverseKeys(Qt_functions,config)

#Default shortcuts
mw.inversionSet =  [
    "Ctrl+:",
    "d",
    "s",
    "a",
    "b",
    "t",
    "y"
]

#List of "inverter" QShortcut objects that negate the defaults
mw.inverters = []

#Creates and inserts the inverter QShortcut objects
def cs_applyInverters():
    qshortcuts = []
    globalShortcuts = [
        ("Ctrl+:", mw.onDebug),
        ("d", lambda: mw.moveToState("deckBrowser")),
        ("s", mw.onStudyKey),
        ("a", mw.onAddCard),
        ("b", mw.onBrowse),
        ("t", mw.onStats),
        ("y", mw.onSync)
    ]
    for key, fn in globalShortcuts:
        scut = QShortcut(QKeySequence(key), mw, activated=fn)
        scut.setAutoRepeat(False)
        qshortcuts.append(scut)
        mw.inverters.append(scut)
    return qshortcuts

#Modified AnkiQt applyShortcuts to work around inverter shortcuts
#TODO: Be able to swap shortcut functions around
#Unsure if this is possible
def _applyShortcuts(shortcuts):
    qshortcuts = []
    for key, fn in shortcuts:
        if key not in mw.inversionSet:
            scut = QShortcut(QKeySequence(key), mw, activated=fn)
            scut.setAutoRepeat(False)
            qshortcuts.append(scut)
        else:
            mw.inverters[mw.inversionSet.index(key)].setEnabled(False)
    return qshortcuts

#Initialize custom keys
def cs_initKeys():
    cuts = [
        config_scuts["main debug"],
        config_scuts["main deckbrowser"],
        config_scuts["main study"],
        config_scuts["main add"],
        config_scuts["main browse"],
        config_scuts["main stats"],
        config_scuts["main sync"]
    ]
    functions =  [
        mw.onDebug,
        lambda: mw.moveToState("deckBrowser"),
        mw.onStudyKey,
        mw.onAddCard,
        mw.onBrowse,
        mw.onStats,
        mw.onSync
    ]
    globalShortcuts = list(zip(cuts,functions))
    _applyShortcuts(globalShortcuts)
    mw.keys = cuts
    mw.stateShortcuts = []

#Governs the shortcuts on the main toolbar
def cs_mtShortcuts():
    m = mw.form
    m.actionExit.setShortcut(config_scuts["m_toolbox quit"])
    m.actionPreferences.setShortcut(config_scuts["m_toolbox preferences"])
    m.actionUndo.setShortcut(config_scuts["m_toolbox undo"])
    m.actionDocumentation.setShortcut(config_scuts["m_toolbox see documentation"])
    m.actionSwitchProfile.setShortcut(config_scuts["m_toolbox switch profile"])
    m.actionExport.setShortcut(config_scuts["m_toolbox export"])
    m.actionImport.setShortcut(config_scuts["m_toolbox import"])
    m.actionStudyDeck.setShortcut(config_scuts["m_toolbox study"])
    m.actionCreateFiltered.setShortcut(config_scuts["m_toolbox create filtered deck"])
    m.actionAdd_ons.setShortcut(config_scuts["m_toolbox addons"])

#Converts json shortcuts into functions for the reviewer
#sToF: shortcutToFunction
def review_sToF(self,scut):

    #"reviewer" is retained for copy-pastability, may be removed later
    # "self.mw.onEditCurrent" is exactly how it was in reviewer.py, DO NOT CHANGE
    sdict = {
        "reviewer edit current": self.mw.onEditCurrent,
        "reviewer flip card": self.onEnterKey,
        "reviewer flip card 1": self.onEnterKey,
        "reviewer flip card 2": self.onEnterKey,
        "reviewer flip card 3": self.onEnterKey,
        "reviewer options menu": self.onOptions,
        "reviewer record voice": self.onRecordVoice,
        "reviewer play recorded voice": self.onReplayRecorded,
        "reviewer play recorded voice 1": self.onReplayRecorded,
        "reviewer play recorded voice 2": self.onReplayRecorded,
        "reviewer delete note": self.onDelete,
        "reviewer suspend card": self.onSuspendCard,
        "reviewer suspend note": self.onSuspend,
        "reviewer bury card": self.onBuryCard,
        "reviewer bury note": self.onBuryNote,
        "reviewer mark card": self.onMark,
        "reviewer set flag 1": lambda: self.setFlag(1),
        "reviewer set flag 2": lambda: self.setFlag(2),
        "reviewer set flag 3": lambda: self.setFlag(3),
        "reviewer set flag 4": lambda: self.setFlag(4),
        "reviewer set flag 0": lambda: self.setFlag(0),
        "reviewer replay audio": self.replayAudio,
        "reviewer choice 1": lambda: self._answerCard(1),
        "reviewer choice 2": lambda: self._answerCard(2),
        "reviewer choice 3": lambda: self._answerCard(3),
        "reviewer choice 4": lambda: self._answerCard(4),
    }
    return sdict[scut]

#Governs the shortcuts on the review window
def review_shortcutKeys(self):
    dupes = []
    ret = [
        (config_scuts["reviewer edit current"], self.mw.onEditCurrent),
        (config_scuts["reviewer flip card 1"], self.onEnterKey),
        (config_scuts["reviewer flip card 2"], self.onEnterKey),
        (config_scuts["reviewer flip card 3"], self.onEnterKey),
        (config_scuts["reviewer replay audio 1"], self.replayAudio),
        (config_scuts["reviewer replay audio 2"], self.replayAudio),
        (config_scuts["reviewer set flag 1"], lambda: self.setFlag(1)),
        (config_scuts["reviewer set flag 2"], lambda: self.setFlag(2)),
        (config_scuts["reviewer set flag 3"], lambda: self.setFlag(3)),
        (config_scuts["reviewer set flag 4"], lambda: self.setFlag(4)),
        (config_scuts["reviewer set flag 0"], lambda: self.setFlag(0)),
        (config_scuts["reviewer mark card"], self.onMark),
        (config_scuts["reviewer bury note"], self.onBuryNote),
        (config_scuts["reviewer bury card"], self.onBuryCard),
        (config_scuts["reviewer suspend note"], self.onSuspend),
        (config_scuts["reviewer suspend card"], self.onSuspendCard),
        (config_scuts["reviewer delete note"], self.onDelete),
        (config_scuts["reviewer play recorded voice"], self.onReplayRecorded),
        (config_scuts["reviewer record voice"], self.onRecordVoice),
        (config_scuts["reviewer options menu"], self.onOptions),
        (config_scuts["reviewer choice 1"], lambda: self._answerCard(1)),
        (config_scuts["reviewer choice 2"], lambda: self._answerCard(2)),
        (config_scuts["reviewer choice 3"], lambda: self._answerCard(3)),
        (config_scuts["reviewer choice 4"], lambda: self._answerCard(4)),
    ]
    for scut in config_scuts["reviewer _duplicates"]:
        dupes.append((config_scuts["reviewer _duplicates"][scut],self.sToF(scut)))
    return dupes + ret

#The function to setup shortcuts on the Editor
def _setupShortcuts(self):
    # if a third element is provided, enable shortcut even when no field selected
    cuts = [
        (config_scuts["editor card layout"], self.onCardLayout, True),
        (config_scuts["editor bold"], self.toggleBold),
        (config_scuts["editor italic"], self.toggleItalic),
        (config_scuts["editor underline"], self.toggleUnderline),
        (config_scuts["editor superscript"], self.toggleSuper),
        (config_scuts["editor subscript"], self.toggleSub),
        (config_scuts["editor remove format"], self.removeFormat),
        (config_scuts["editor foreground"], self.onForeground),
        (config_scuts["editor change col"], self.onChangeCol),
        (config_scuts["editor cloze"], self.onCloze),
        (config_scuts["editor cloze alt"], self.onCloze),
        (config_scuts["editor add media"], self.onAddMedia),
        (config_scuts["editor record sound"], self.onRecSound),
        (config_scuts["editor insert latex"], self.insertLatex),
        (config_scuts["editor insert latex equation"], self.insertLatexEqn),
        (config_scuts["editor insert latex math environment"], self.insertLatexMathEnv),
        (config_scuts["editor insert mathjax inline"], self.insertMathjaxInline),
        (config_scuts["editor insert mathjax block"], self.insertMathjaxBlock),
        (config_scuts["editor insert mathjax chemistry"], self.insertMathjaxChemistry),
        (config_scuts["editor html edit"], self.onHtmlEdit),
        (config_scuts["editor focus tags"], self.onFocusTags, True),
        (config_scuts["editor _extras"]["paste custom text"], self.customPaste)
    ]
    runHook("setupEditorShortcuts", cuts, self)
    for row in cuts:
        if len(row) == 2:
            keys, fn = row
            fn = self._addFocusCheck(fn)
        else:
            keys, fn, _ = row
        scut = QShortcut(QKeySequence(keys), self.widget, activated=fn)


#detects shortcut conflicts
#Ignores the Add-on (Ω) options
def cs_conflictDetect():
    if config["Ω enable conflict warning"].upper() != "Y":
        return
    ext_list = {}
    dupes = False
    for e in config:
        sub = e[0:(e.find(" "))]
        val = config[e]
        if sub in ext_list:
            if isinstance(val,dict):
                for key in val:
                    ext_list[sub][key + " in " + e] = val[key].upper()
            else:
                ext_list[sub][e] = val.upper()
        elif sub != "Ω":
            ext_list[sub] = {e:val.upper()}
    inv = {}
    conflictStr = CS_CONFLICTSTR
    for key in ext_list:
        inv = {}
        x = ext_list[key]
        for e in x:
            if x[e] not in inv:
                inv[x[e]] = [e]
            else:
                inv[x[e]].append(e)
        for k in inv:
            if(len(inv[k])) == 1:
                continue
            if k == "<NOP>":
                continue
            conflictStr += ", ".join(inv[k])
            conflictStr += "\nshare '" + k + "' as a shortcut\n\n"

    if(len(conflictStr) != len(CS_CONFLICTSTR)):
        conflictStr += "\nThese shortcuts will not work.\n"
        conflictStr += "Please change them in the config.json."
        showWarning(conflictStr)

#Mimics the style of other Anki functions, analogue of customPaste
#Note that the saveNow function used earler takes the cursor to the end of the line,
#as it is meant to save work before entering a new window
def cs_editor_custom_paste(self):
    self._customPaste()


#Mimics the style of other Anki functions, analogue of _customPaste
def cs_uEditor_custom_paste(self):
    html = config_scuts["Ω custom paste text"]
    with warnings.catch_warnings() as w:
        warnings.simplefilter('ignore', UserWarning)
        html = str(BeautifulSoup(html, "html.parser"))
    self.doPaste(html,True,True)

#Functions that execute on startup
cs_translateKeys()

Editor.setupShortcuts = _setupShortcuts
Editor.customPaste = cs_editor_custom_paste
Editor._customPaste = cs_uEditor_custom_paste
Reviewer._shortcutKeys = review_shortcutKeys
Reviewer.sToF = review_sToF

mw.applyShortcuts = _applyShortcuts

cs_applyInverters()
cs_initKeys()
cs_mtShortcuts()
cs_conflictDetect()
