; ============================================================
; CLIPBOARD MONITOR — Headless bridge to ClipSync
; ============================================================
; Watches system clipboard → pushes to Python server
; Fast paste hotkeys read from server
; GUI is HTML (localhost:3456/clipboard)
;
; Hotkeys:
;   Ctrl+Shift+V      = Open clipboard HTML
;   Ctrl+Shift+1-0    = Fast paste slots 1-10
;   Ctrl+Alt+1-0      = Fast paste slots 11-20
; ============================================================

#Requires AutoHotkey v2.0+

global CB_BRIDGE_URL := "http://localhost:3456"
global CB_LAST_CLIP := ""
global CB_AGG_MODE := true
global CB_AGG_WINDOW := 2000        ; ms
global CB_AGG_BUFFER := ""
global CB_AGG_COUNT := 0
global CB_AGG_LAST := 0
global CB_CLIP_CACHE := []          ; Local cache for fast paste

; ---- Clipboard monitoring ----
OnClipboardChange(CB_Bridge_OnChange)
SetTimer(CB_PollClipboard, 800)

CB_Bridge_OnChange(dataType) {
    if dataType != 1
        return
    text := A_Clipboard
    CB_Bridge_HandleText(text)
}

CB_PollClipboard() {
    global CB_LAST_CLIP
    text := A_Clipboard
    if text = "" || text = CB_LAST_CLIP
        return
    CB_Bridge_HandleText(text)
}

CB_Bridge_HandleText(text) {
    global CB_LAST_CLIP
    global CB_AGG_MODE, CB_AGG_WINDOW, CB_AGG_BUFFER, CB_AGG_COUNT, CB_AGG_LAST

    if text = "" || text = CB_LAST_CLIP
        return

    if CB_AGG_MODE {
        now := A_TickCount
        elapsed := now - CB_AGG_LAST
        CB_AGG_LAST := now

        if elapsed < CB_AGG_WINDOW && CB_AGG_BUFFER != "" {
            CB_AGG_BUFFER .= "`n" . text
            CB_AGG_COUNT++
            A_Clipboard := CB_AGG_BUFFER
            CB_LAST_CLIP := CB_AGG_BUFFER
            ToolTip("⚡ Aggregated: " CB_AGG_COUNT " clips")
            SetTimer(() => ToolTip(), -1500)
            CB_PushToServer(CB_AGG_BUFFER, "aggregate")
            return
        } else {
            CB_AGG_BUFFER := text
            CB_AGG_COUNT := 1
        }
    }

    CB_LAST_CLIP := text
    CB_PushToServer(text, "clipboard")
}

CB_PushToServer(text, source) {
    global CB_BRIDGE_URL
    try {
        whr := ComObject("WinHttp.WinHttpRequest.5.1")
        whr.Open("POST", CB_BRIDGE_URL "/api/clips", true)
        whr.SetRequestHeader("Content-Type", "application/json")

        ; Build JSON manually (escape special chars)
        escaped := text
        escaped := StrReplace(escaped, "\", "\\")
        escaped := StrReplace(escaped, "`"", "\`"")
        escaped := StrReplace(escaped, "`n", "\n")
        escaped := StrReplace(escaped, "`r", "\r")
        escaped := StrReplace(escaped, "`t", "\t")

        json := '{"content":"' escaped '","source":"' source '"}'
        whr.Send(json)
        whr.WaitForResponse(2)
    } catch {
        ; Server offline — that's fine, keep going
    }
}

; ---- Refresh local cache for fast paste ----
CB_RefreshCache() {
    global CB_BRIDGE_URL, CB_CLIP_CACHE
    try {
        whr := ComObject("WinHttp.WinHttpRequest.5.1")
        whr.Open("GET", CB_BRIDGE_URL "/api/clips?limit=20", true)
        whr.Send()
        whr.WaitForResponse(2)
        if whr.Status = 200 {
            ; Parse simple JSON array of clips
            CB_CLIP_CACHE := CB_ParseClipArray(whr.ResponseText)
        }
    } catch {
        ; Server offline
    }
}

CB_ParseClipArray(jsonStr) {
    results := []
    pos := 1
    while pos := InStr(jsonStr, '"content":', , pos) {
        ; Find the content value
        valStart := InStr(jsonStr, '"', , pos + 10)
        if valStart = 0
            break
        valStart++  ; skip opening quote

        ; Find end of string (handle escapes)
        valEnd := valStart
        Loop {
            valEnd := InStr(jsonStr, '"', , valEnd)
            if valEnd = 0
                break
            ; Check if escaped
            bs := 0
            check := valEnd - 1
            while check >= valStart && SubStr(jsonStr, check, 1) = "\" {
                bs++
                check--
            }
            if Mod(bs, 2) = 0
                break  ; Not escaped, this is the real end
            valEnd++
        }

        if valEnd > valStart {
            val := SubStr(jsonStr, valStart, valEnd - valStart)
            val := StrReplace(val, "\n", "`n")
            val := StrReplace(val, "\r", "`r")
            val := StrReplace(val, "\t", "`t")
            val := StrReplace(val, "\`"", "`"")
            val := StrReplace(val, "\\", "\")
            results.Push(val)
        }

        pos := valEnd + 1
    }
    return results
}

CB_FastPaste(slot) {
    global CB_CLIP_CACHE
    if slot < 1 || slot > CB_CLIP_CACHE.Length
        return
    A_Clipboard := CB_CLIP_CACHE[slot]
    ClipWait(0.5)
    Send("^v")
    ToolTip("📋 Slot " slot)
    SetTimer(() => ToolTip(), -1000)
}

; ============================================================
; HOTKEYS
; ============================================================

; Open clipboard HTML
^+v:: {
    global CB_BRIDGE_URL

    ; Check if already open
    if WinExist("Clipboard v2") || WinExist("POF 2828 — Clipboard v2") {
        WinActivate()
        return
    }

    edgePath := "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if !FileExist(edgePath)
        edgePath := "C:\Program Files\Microsoft\Edge\Application\msedge.exe"

    url := CB_BRIDGE_URL "/clipboard2"

    if FileExist(edgePath) {
        Run('"' edgePath '" --app="' url '" --window-size=820,780')
    } else {
        Run(url)
    }
}

; Fast paste: Ctrl+Shift+1-0 = slots 1-10
^+1:: CB_FastPaste(1)
^+2:: CB_FastPaste(2)
^+3:: CB_FastPaste(3)
^+4:: CB_FastPaste(4)
^+5:: CB_FastPaste(5)
^+6:: CB_FastPaste(6)
^+7:: CB_FastPaste(7)
^+8:: CB_FastPaste(8)
^+9:: CB_FastPaste(9)
^+0:: CB_FastPaste(10)

; Fast paste: Ctrl+Alt+1-0 = slots 11-20
^!1:: CB_FastPaste(11)
^!2:: CB_FastPaste(12)
^!3:: CB_FastPaste(13)
^!4:: CB_FastPaste(14)
^!5:: CB_FastPaste(15)
^!6:: CB_FastPaste(16)
^!7:: CB_FastPaste(17)
^!8:: CB_FastPaste(18)
^!9:: CB_FastPaste(19)
^!0:: CB_FastPaste(20)

; ---- Refresh cache periodically ----
CB_RefreshCache()
SetTimer(CB_RefreshCache, 5000)
