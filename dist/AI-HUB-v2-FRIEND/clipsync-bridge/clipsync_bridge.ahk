; ============================================================
; Module: ClipSync Bridge — Dynamic Hotkey Registration
; ============================================================
; Polls http://localhost:3456/api/hotkeys every 30 seconds
; Dynamically registers/unregisters hotkeys based on prompt data
; 
; Static hotkeys:
;   Ctrl+Alt+P      = Open Prompt Picker
;   Ctrl+Alt+R      = Open Research Links
;   Ctrl+Alt+L      = Open Research Links (alias)
;   Ctrl+Alt+B      = Open Bookmarks
;   Ctrl+Alt+C      = Open Clipboard v2
;   Ctrl+Alt+S      = Check server status
;
; Dynamic hotkeys loaded from server (configured in HTML UI)
; ============================================================

#Requires AutoHotkey v2.0+

; Set distinct tray icon ONLY when running standalone (not #included by hub)
if InStr(A_ScriptName, "clipsync_bridge") {
    try TraySetIcon("shell32.dll", 55)
    A_IconTip := "ClipSync Bridge"
}

; ---- Configuration ----
global BRIDGE_URL := "http://localhost:3456"
global BRIDGE_POLL_INTERVAL := 30000  ; ms between hotkey refresh
global BRIDGE_REGISTERED_HOTKEYS := Map()

; ---- Static Hotkeys ----

; ---- Dynamic Hotkey System ----

LoadHotkeysFromServer() {
    global BRIDGE_URL, BRIDGE_REGISTERED_HOTKEYS

    try {
        ; Fetch hotkeys from server
        whr := ComObject("WinHttp.WinHttpRequest.5.1")
        whr.Open("GET", BRIDGE_URL "/api/hotkeys", true)
        whr.Send()
        whr.WaitForResponse(3)  ; 3 second timeout

        if (whr.Status != 200) {
            return
        }

        response := whr.ResponseText
        
        ; Simple JSON array parsing for hotkey objects
        ; Each object has: id, name, hotkey, content
        hotkeys := ParseHotkeyJSON(response)
        
        ; Unregister old dynamic hotkeys
        for hk, _ in BRIDGE_REGISTERED_HOTKEYS {
            try {
                Hotkey(hk, "Off")
            }
        }
        BRIDGE_REGISTERED_HOTKEYS := Map()
        
        ; Register new ones
        for _, item in hotkeys {
            hk := item["hotkey"]
            content := item["content"]
            name := item["name"]
            
            if (hk = "" || !hk)
                continue
            
            try {
                ; Create a closure that captures the content
                fn := CopyPromptFactory(content, name)
                Hotkey(hk, fn)
                BRIDGE_REGISTERED_HOTKEYS[hk] := name
            } catch as e {
                ; Invalid hotkey string — skip silently
            }
        }
        
    } catch as e {
        ; Server offline — keep existing hotkeys
    }
}

CopyPromptFactory(content, name) {
    return (*) => CopyPromptToClipboard(content, name)
}

CopyPromptToClipboard(content, name) {
    A_Clipboard := content
    ToolTip("📋 " name " → clipboard")
    SetTimer(() => ToolTip(), -1500)
}

; ---- Simple JSON Parsing for Hotkey Array ----
; Expects: [{"id":"...","name":"...","hotkey":"...","content":"..."},...]

ParseHotkeyJSON(jsonStr) {
    results := []
    
    ; Strip outer brackets
    jsonStr := Trim(jsonStr)
    if (SubStr(jsonStr, 1, 1) != "[")
        return results
    
    ; Split by },{ to get individual objects
    jsonStr := SubStr(jsonStr, 2, StrLen(jsonStr) - 2)  ; remove [ ]
    
    ; Simple state machine to split objects
    depth := 0
    current := ""
    
    Loop Parse jsonStr {
        ch := A_LoopField
        if (ch = "{")
            depth++
        else if (ch = "}")
            depth--
        
        current .= ch
        
        if (depth = 0 && current != "") {
            current := Trim(current, " ,`n`r`t")
            if (current != "") {
                obj := ParseSimpleObject(current)
                if (obj.Has("hotkey") && obj["hotkey"] != "")
                    results.Push(obj)
            }
            current := ""
        }
    }
    
    return results
}

ParseSimpleObject(objStr) {
    result := Map()
    
    ; Remove outer braces
    objStr := Trim(objStr)
    if (SubStr(objStr, 1, 1) = "{")
        objStr := SubStr(objStr, 2, StrLen(objStr) - 2)
    
    ; Match "key":"value" pairs (simple — doesn't handle nested objects)
    pos := 1
    while (pos := RegExMatch(objStr, '"(\w+)"\s*:\s*"((?:[^"\\]|\\.)*)"', &match, pos)) {
        key := match[1]
        val := match[2]
        ; Unescape basic JSON escapes
        val := StrReplace(val, "\\n", "`n")
        val := StrReplace(val, '\\"', '"')
        val := StrReplace(val, "\\\\", "\")
        result[key] := val
        pos := match.Pos + match.Len
    }
    
    ; Also match "key":null
    pos := 1
    while (pos := RegExMatch(objStr, '"(\w+)"\s*:\s*null', &match, pos)) {
        result[match[1]] := ""
        pos := match.Pos + match.Len
    }
    
    return result
}

; ---- Browser Helpers ----

OpenBridgePage(path) {
    global BRIDGE_URL
    url := BRIDGE_URL path
    
    ; Check if already open
    if WinExist("POF 2828") {
        WinActivate()
        return
    }
    
    ; Open in Edge app mode (no tabs, no address bar)
    edgePath := "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if !FileExist(edgePath)
        edgePath := "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    
    if FileExist(edgePath) {
        Run('"' edgePath '" --app="' url '" --window-size=700,800')
    } else {
        Run(url)  ; Fallback to default browser
    }
}

OpenBridgeClipboard() {
    ; Check if already open
    if WinExist("Clipboard v2") {
        WinActivate()
        return
    }

    ; Open clipboard2 via bridge server
    global BRIDGE_URL
    url := BRIDGE_URL "/clipboard2"

    ; Open in Edge app mode — wider for two-pane layout
    edgePath := "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if !FileExist(edgePath)
        edgePath := "C:\Program Files\Microsoft\Edge\Application\msedge.exe"

    ; Get work area for positioning
    MonitorGetWorkArea(, , , &monW, &monH)
    clipW := 820
    clipH := monH - 80
    clipX := monW - clipW - 10
    clipY := 10

    if FileExist(edgePath) {
        Run('"' edgePath '" --app="' url '" --window-size=' clipW ',' clipH ' --window-position=' clipX ',' clipY)
    } else {
        Run(url)
    }
}

ShowBridgeStatus() {
    global BRIDGE_URL, BRIDGE_REGISTERED_HOTKEYS
    
    try {
        whr := ComObject("WinHttp.WinHttpRequest.5.1")
        whr.Open("GET", BRIDGE_URL "/api/status", true)
        whr.Send()
        whr.WaitForResponse(3)
        
        if (whr.Status = 200) {
            msg := "✅ ClipSync Bridge ONLINE`n`n"
            msg .= "Server: " BRIDGE_URL "`n"
            msg .= "Dynamic hotkeys: " BRIDGE_REGISTERED_HOTKEYS.Count "`n`n"
            
            for hk, name in BRIDGE_REGISTERED_HOTKEYS {
                msg .= "  " hk " → " name "`n"
            }
            
            msg .= "`n--- Static ---`n"
            msg .= "  Ctrl+Alt+P → Prompt Picker`n"
            msg .= "  Ctrl+Alt+R → Research Links`n"
            msg .= "  Ctrl+Alt+L → Research Links`n"
            msg .= "  Ctrl+Alt+B → Bookmarks`n"
            msg .= "  Ctrl+Alt+C → Clipboard v2`n"
            msg .= "  Ctrl+Alt+S → This status`n"
            
            MsgBox(msg, "ClipSync Bridge Status", "Iconi")
        } else {
            MsgBox("⚠️ Server returned HTTP " whr.Status, "ClipSync Bridge", "Icon!")
        }
    } catch as e {
        MsgBox("❌ ClipSync Bridge server is OFFLINE`n`nStart it with: python sync_server.py", "ClipSync Bridge", "Icon!")
    }
}

; ---- Initialize ----

; Load hotkeys on startup
LoadHotkeysFromServer()

; Poll for changes periodically
SetTimer(LoadHotkeysFromServer, BRIDGE_POLL_INTERVAL)
