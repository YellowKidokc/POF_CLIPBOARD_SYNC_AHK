; ============================================================
; CLIPBOARD CORE — Data engine for clipboard management
; Supports: history, pins, tags, save/load
; ============================================================

global CB_MAX_HISTORY := 1000
global CB_MAX_DISPLAY := 20
global cbHistory := []         ; Array of {text, pinned, tag}
global CB_DATA_FILE := A_ScriptDir "\config\clipboard_data.json"

; ---- Aggregate Copy Mode ----
global cbAggregateMode := true        ; Enable aggregate copy
global cbAggregateWindow := 2000      ; ms window for stacking copies
global cbAggregateSeparator := "`n"   ; Separator between aggregated clips
global cbLastCopyTime := 0            ; Timestamp of last copy
global cbAggregateBuffer := ""        ; Current aggregate buffer
global cbAggregateCount := 0          ; How many copies in current aggregate

; ---- Clipboard monitoring ----
OnClipboardChange(CB_OnClipChange)

CB_OnClipChange(dataType) {
    global cbHistory, CB_MAX_HISTORY
    global cbAggregateMode, cbAggregateWindow, cbAggregateSeparator
    global cbLastCopyTime, cbAggregateBuffer, cbAggregateCount
    if dataType != 1
        return
    text := A_Clipboard
    if text = ""
        return

    ; ---- Aggregate copy logic ----
    if cbAggregateMode {
        now := A_TickCount
        elapsed := now - cbLastCopyTime
        cbLastCopyTime := now

        if elapsed < cbAggregateWindow && cbAggregateBuffer != "" {
            ; Append to aggregate buffer
            if text != SubStr(cbAggregateBuffer, -StrLen(text))  ; avoid re-appending same text
            {
                cbAggregateBuffer .= cbAggregateSeparator . text
                cbAggregateCount++
                A_Clipboard := cbAggregateBuffer
                ToolTip("Aggregated: " cbAggregateCount " clips")
                SetTimer(() => ToolTip(), -1500)
                ; Update the top item in history instead of adding new
                if cbHistory.Length > 0 {
                    cbHistory[1].text := cbAggregateBuffer
                    CB_SaveHistory()
                    try CB_RefreshMainList()
                }
                return
            }
            return
        } else {
            ; Start new aggregate
            cbAggregateBuffer := text
            cbAggregateCount := 1
        }
    }

    ; Don't add duplicates at top
    if cbHistory.Length > 0 && cbHistory[1].text = text
        return

    ; Remove if exists elsewhere (move to top, preserve pin/tag)
    idx := CB_FindInHistory(text)
    oldPin := false
    oldTag := ""
    if idx > 0 {
        oldPin := cbHistory[idx].pinned
        oldTag := cbHistory[idx].tag
        cbHistory.RemoveAt(idx)
    }

    ; Insert after pinned items (pinned stay at top)
    insertAt := 1
    if !oldPin {
        for i, item in cbHistory {
            if !item.pinned {
                insertAt := i
                break
            }
            insertAt := i + 1
        }
    }

    cbHistory.InsertAt(insertAt, {text: text, pinned: oldPin, tag: oldTag})

    ; Trim to max (only non-pinned)
    while cbHistory.Length > CB_MAX_HISTORY {
        ; Remove last non-pinned item
        removed := false
        i := cbHistory.Length
        while i > 0 {
            if !cbHistory[i].pinned {
                cbHistory.RemoveAt(i)
                removed := true
                break
            }
            i--
        }
        if !removed
            break
    }

    try CB_RefreshMainList()
    CB_SaveHistory()
}

CB_FindInHistory(text) {
    global cbHistory
    for i, item in cbHistory {
        if item.text = text
            return i
    }
    return 0
}

CB_TogglePin(index) {
    global cbHistory
    if index < 1 || index > cbHistory.Length
        return
    cbHistory[index].pinned := !cbHistory[index].pinned

    ; Re-sort: pinned items go to top
    if cbHistory[index].pinned {
        item := cbHistory[index]
        cbHistory.RemoveAt(index)
        cbHistory.InsertAt(1, item)
    }
    CB_SaveHistory()
    try CB_RefreshMainList()
}

CB_SetTag(index, tag) {
    global cbHistory
    if index < 1 || index > cbHistory.Length
        return
    cbHistory[index].tag := tag
    CB_SaveHistory()
    try CB_RefreshMainList()
}

CB_StickToTop(index) {
    global cbHistory
    if index < 1 || index > cbHistory.Length
        return
    item := cbHistory[index]
    cbHistory.RemoveAt(index)
    cbHistory.InsertAt(1, item)
    CB_SaveHistory()
    try CB_RefreshMainList()
}

CB_StickToBottom(index) {
    global cbHistory
    if index < 1 || index > cbHistory.Length
        return
    item := cbHistory[index]
    cbHistory.RemoveAt(index)
    cbHistory.Push(item)
    CB_SaveHistory()
    try CB_RefreshMainList()
}

CB_MoveUp(index) {
    global cbHistory
    if index <= 1 || index > cbHistory.Length
        return
    temp := cbHistory[index]
    cbHistory[index] := cbHistory[index - 1]
    cbHistory[index - 1] := temp
    CB_SaveHistory()
    try CB_RefreshMainList()
}

CB_MoveDown(index) {
    global cbHistory
    if index < 1 || index >= cbHistory.Length
        return
    temp := cbHistory[index]
    cbHistory[index] := cbHistory[index + 1]
    cbHistory[index + 1] := temp
    CB_SaveHistory()
    try CB_RefreshMainList()
}

CB_DeleteItem(index) {
    global cbHistory
    if index < 1 || index > cbHistory.Length
        return
    cbHistory.RemoveAt(index)
    CB_SaveHistory()
    try CB_RefreshMainList()
}

CB_PasteItem(index) {
    global cbHistory
    if index < 1 || index > cbHistory.Length
        return
    A_Clipboard := cbHistory[index].text
    ClipWait(0.5)
    Send("^v")
}

CB_EditItem(index, newText) {
    global cbHistory
    if index < 1 || index > cbHistory.Length
        return
    cbHistory[index].text := newText
    CB_SaveHistory()
    try CB_RefreshMainList()
}

; ---- Save / Load (JSON with pin + tag) ----
CB_EscJSON(s) {
    s := StrReplace(s, "\", "\\")
    s := StrReplace(s, "`"", "\`"")
    s := StrReplace(s, "`n", "\n")
    s := StrReplace(s, "`r", "\r")
    s := StrReplace(s, "`t", "\t")
    return s
}

CB_UnescJSON(s) {
    s := StrReplace(s, "\n", "`n")
    s := StrReplace(s, "\r", "`r")
    s := StrReplace(s, "\t", "`t")
    s := StrReplace(s, "\`"", "`"")
    s := StrReplace(s, "\\", "\")
    return s
}

CB_SaveHistory() {
    global cbHistory, CB_DATA_FILE
    jsonStr := "["
    for i, item in cbHistory {
        jsonStr .= (i > 1 ? "," : "") "`n{"
        jsonStr .= "`"text`":`"" CB_EscJSON(item.text) "`","
        jsonStr .= "`"pinned`":" (item.pinned ? "true" : "false") ","
        jsonStr .= "`"tag`":`"" CB_EscJSON(item.tag) "`""
        jsonStr .= "}"
    }
    jsonStr .= "`n]"
    try {
        if FileExist(CB_DATA_FILE)
            FileDelete(CB_DATA_FILE)
        FileAppend(jsonStr, CB_DATA_FILE, "UTF-8")
    }
}

CB_LoadHistory() {
    global cbHistory, CB_DATA_FILE
    cbHistory := []
    if !FileExist(CB_DATA_FILE)
        return
    try {
        raw := FileRead(CB_DATA_FILE, "UTF-8")
        if raw = "" || raw = "[]"
            return
        ; Parse each object: {"text":"...","pinned":true/false,"tag":"..."}
        pos := 1
        while pos := InStr(raw, "{", , pos) {
            endPos := InStr(raw, "}", , pos)
            if endPos = 0
                break
            objStr := SubStr(raw, pos, endPos - pos + 1)

            ; Extract text
            text := ""
            if RegExMatch(objStr, '`"text`"\s*:\s*`"((?:[^`"\\]|\\.)*)`"', &m)
                text := CB_UnescJSON(m[1])

            ; Extract pinned
            pinned := false
            if RegExMatch(objStr, '`"pinned`"\s*:\s*(true|false)', &m2)
                pinned := (m2[1] = "true")

            ; Extract tag
            tag := ""
            if RegExMatch(objStr, '`"tag`"\s*:\s*`"((?:[^`"\\]|\\.)*)`"', &m3)
                tag := CB_UnescJSON(m3[1])

            if text != ""
                cbHistory.Push({text: text, pinned: pinned, tag: tag})

            pos := endPos + 1
        }
    }
}
