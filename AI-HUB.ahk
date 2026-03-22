#Requires AutoHotkey v2.0+
#SingleInstance Force
#Warn

; ============================================================
; AI-HUB v2 — Entry Point
; ============================================================
; Three processes, three tray icons:
;   1. AI-HUB (this)     — main GUI with tabs [shell32 icon]
;   2. ClipSync Bridge    — clipboard + hotkeys [notepad icon]
;   3. BetterTTS          — TTS with normalizer [GHOSTY icon]
;
; On startup also launches:
;   - sync_server.py (serves HTML panels)
;   - Prompt Picker HTML
;   - Research Links HTML
; ============================================================

#include .\hub_core.ahk
#include .\modules\manifest.ahk

; Boot the application (defined in hub_core.ahk)
Hub_Boot()

; Hardcode always-on-top + remember-pos ON (INI already saves these but apply them directly)
SetTimer(TTS_ForceWindowBehavior, -1500)
TTS_ForceWindowBehavior() {
    global gShell, gAlwaysOnTop, gRememberPos
    gAlwaysOnTop := true
    gRememberPos := true
    try WinSetAlwaysOnTop(1, "ahk_id " gShell.gui.Hwnd)
    try {
        gShell.chkAlwaysOnTop.Value := 1
        gShell.chkAlwaysOnTop.Text  := "ON"
        gShell.chkRememberPos.Value := 1
        gShell.chkRememberPos.Text  := "ON"
    }
}

; --- SUBPROCESS 1: ClipSync Bridge server (Python, direct launch, no .bat) ---
; Launch pythonw directly to avoid CMD flash from .bat wrapper
try {
    pyW := "C:\Users\lowes\AppData\Local\Programs\Python\Python312\pythonw.exe"
    pyC := "C:\Users\lowes\AppData\Local\Programs\Python\Python312\python.exe"
    bridgeScript := A_ScriptDir "\clipsync-bridge\sync_server.py"
    if FileExist(pyW)
        Run('"' pyW '" "' bridgeScript '"', , "Hide")
    else if FileExist(pyC)
        Run('"' pyC '" "' bridgeScript '"', , "Hide")
}

; --- SUBPROCESS 2: ClipSync hotkeys/UI bridge (AHK) ---
; Disabled here because the bridge is already loaded through modules\manifest.ahk.
; Running it again creates duplicate timers/hotkeys and extra tray noise.
; try Run(A_ScriptDir "\clipsync-bridge\clipsync_bridge.ahk")

; --- SUBPROCESS 3: BetterTTS (AHK, own tray icon) ---
; DISABLED - TTS now embedded in hub TTS tab
; try Run(A_ScriptDir "\BetterTTS\BetterTTS.ahk")

; --- SUBPROCESS 4: Clipboard Manager ---
; DISABLED — Clipboard.ahk does not exist in clipboard\ folder
; try Run(A_ScriptDir "\clipboard\Clipboard.ahk")

; --- HTML PANELS: Launch after server has time to start ---
SetTimer(LaunchStartupPanels, -3000)

LaunchStartupPanels() {
    try LaunchHtmlPanel("http://localhost:3456/prompts", "POF-Prompts")
    Sleep(500)
    try LaunchHtmlPanel("http://localhost:3456/links", "POF-Links")
}

; Clipboard ingestion now lives in Python (sync_server.py).
; Keep AHK focused on GUI, hotkeys, and OS-level actions.
