#Requires AutoHotkey v2.0+
#SingleInstance Force

; ============================================================
; CLIPBOARD MANAGER — Entry Point
; ============================================================
; Hotkey: Ctrl+Shift+V to toggle window
; Fast paste: Ctrl+Shift+1-0 = slots 1-10
;             Ctrl+Alt+1-0   = slots 11-20
; ============================================================

#include .\clipboard_core.ahk
#include .\clipboard_gui.ahk

; Load saved history
CB_LoadHistory()

; Build and show the GUI
CB_BuildGUI()

; ---- Global Hotkey: Toggle clipboard window ----
^+v:: {
    global cbGui
    if WinExist("ahk_id " cbGui.Hwnd) {
        if DllCall("IsWindowVisible", "Ptr", cbGui.Hwnd)
            cbGui.Hide()
        else
            cbGui.Show()
    }
}

; ============================================================
; FAST PASTE HOTKEYS — Ctrl+Shift+1-0 = slots 1-10
; ============================================================
^+1:: CB_PasteItem(1)
^+2:: CB_PasteItem(2)
^+3:: CB_PasteItem(3)
^+4:: CB_PasteItem(4)
^+5:: CB_PasteItem(5)
^+6:: CB_PasteItem(6)
^+7:: CB_PasteItem(7)
^+8:: CB_PasteItem(8)
^+9:: CB_PasteItem(9)
^+0:: CB_PasteItem(10)

; ============================================================
; FAST PASTE HOTKEYS — Ctrl+Alt+1-0 = slots 11-20
; ============================================================
^!1:: CB_PasteItem(11)
^!2:: CB_PasteItem(12)
^!3:: CB_PasteItem(13)
^!4:: CB_PasteItem(14)
^!5:: CB_PasteItem(15)
^!6:: CB_PasteItem(16)
^!7:: CB_PasteItem(17)
^!8:: CB_PasteItem(18)
^!9:: CB_PasteItem(19)
^!0:: CB_PasteItem(20)
