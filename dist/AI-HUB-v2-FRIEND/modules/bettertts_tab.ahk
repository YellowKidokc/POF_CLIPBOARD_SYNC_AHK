; ============================================================
; Module: BetterTTS Tab — TTS Status & Controls
; ============================================================
; Provides in-hub status for the BetterTTS subprocess.
; The actual TTS runs as its own process with GHOSTY tray icon.
; This tab shows status, lets you toggle clean text, and
; provides a button to show/focus the TTS GUI.
; ============================================================

RegisterTab("TTS", Build_TTSTab, 200)

Build_TTSTab() {
    global gShell, DARK_TEXT, DARK_BG

    gShell.gui.SetFont("s11 cWhite", "Segoe UI")
    gShell.gui.AddText("xm+15 ym+50 w500", "🎙️ BetterTTS — Text-to-Speech Engine")

    gShell.gui.SetFont("s10 cDDDDDD", "Segoe UI")
    gShell.gui.AddText("xm+15 y+15 w700",
        "BetterTTS runs as a separate process with its own tray icon (ghost)."
        . "`nUse CapsLock hotkeys to capture and speak text. The normalizer pipeline"
        . "`nhandles: equation translation, table narration, Greek symbols, and cognitive pacing.")

    gShell.gui.AddText("xm+15 y+25 w500 cAAFFAA", "⌨️ Hotkeys:")
    gShell.gui.SetFont("s9 cBBBBBB", "Consolas")

    hotkeys := [
        ["CapsLock + X", "Capture screen text (OCR)"],
        ["CapsLock + A", "Read clipboard / OCR clipboard image"],
        ["CapsLock + C", "Copy selection and speak"],
        ["CapsLock + V", "Speak current text"],
        ["CapsLock + P", "Pause / Resume"],
        ["CapsLock + S", "Stop speaking"],
        ["CapsLock + R", "Refresh OCR capture"],
        ["CapsLock + Z", "Clear highlight"],
        ["CapsLock + ↑/↓", "Volume up / down"],
        ["CapsLock + →/←", "Speed up / down"],
    ]

    LV := gShell.gui.Add("ListView", "xm+15 y+10 w500 h240 Background1a1a1a cDDDDDD",
        ["Hotkey", "Action"])
    LV.Opt("+LV0x10000")

    for pair in hotkeys
        LV.Add(, pair[1], pair[2])

    LV.ModifyCol(1, 140)
    LV.ModifyCol(2, 340)

    gShell.gui.SetFont("s10 cDDDDDD", "Segoe UI")

    ; Show/Focus TTS button
    btnShow := gShell.gui.AddButton("xm+15 y+20 w200 h30", "🔊 Show BetterTTS Window")
    btnShow.OnEvent("Click", TTS_ShowWindow)

    ; Restart TTS button
    btnRestart := gShell.gui.AddButton("x+15 yp w200 h30", "🔄 Restart BetterTTS")
    btnRestart.OnEvent("Click", TTS_Restart)

    ; Status indicator
    gShell.gui.AddText("xm+15 y+20 w500 c888888",
        "Normalizer: FIXED master (878 equations) + Bridge (42 concepts) + Unicode math (15 patterns)")
}

TTS_ShowWindow(*) {
    try {
        DetectHiddenWindows(true)
        if WinExist("Better TTS")
            WinActivate("Better TTS")
        else
            TTS_Launch()
        DetectHiddenWindows(false)
    }
}

TTS_Restart(*) {
    try {
        DetectHiddenWindows(true)
        if WinExist("Better TTS") {
            WinClose("Better TTS")
            Sleep(500)
        }
        DetectHiddenWindows(false)
    }
    TTS_Launch()
}

TTS_Launch() {
    ttsPath := A_ScriptDir "\BetterTTS\BetterTTS.ahk"
    if FileExist(ttsPath)
        try Run(ttsPath)
}
