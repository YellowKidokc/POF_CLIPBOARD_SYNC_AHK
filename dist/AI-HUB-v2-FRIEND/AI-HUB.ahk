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

; --- SUBPROCESS 1: ClipSync Bridge server (Python, silent) ---
try Run(A_ScriptDir "\clipsync-bridge\start_bridge_silent.bat", , "Hide")

; --- SUBPROCESS 2: ClipSync hotkeys/UI bridge (AHK) ---
try Run(A_ScriptDir "\clipsync-bridge\clipsync_bridge.ahk")

; --- SUBPROCESS 3: BetterTTS (AHK, own tray icon) ---
try Run(A_ScriptDir "\BetterTTS\BetterTTS.ahk")

; --- HTML PANELS: Launch after server has time to start ---
SetTimer(LaunchStartupPanels, -3000)

LaunchStartupPanels() {
    try LaunchHtmlPanel("http://localhost:3456/prompts", "POF-Prompts")
    Sleep(500)
    try LaunchHtmlPanel("http://localhost:3456/links", "POF-Links")
}

; Clipboard ingestion now lives in Python (sync_server.py).
; Keep AHK focused on GUI, hotkeys, and OS-level actions.
