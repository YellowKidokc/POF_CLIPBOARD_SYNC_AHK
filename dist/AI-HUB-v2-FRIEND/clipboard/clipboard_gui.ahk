; ============================================================
; CLIPBOARD GUI — Skinny window near system tray
; Left toolbar: Pin, Tag, Delete, Edit, Up, Down, Top, Bottom
; ============================================================

; ---- Theme (matches AI Hub) ----
global CB_BG := "0f0f0f"
global CB_CTRL := "181818"
global CB_BORDER := "2a2a2a"
global CB_TEXT := "DDDDDD"
global CB_ACCENT := "3d5afe"
global CB_INPUT := "1a1a1a"

; ---- State ----
global cbGui := ""
global cbListView := ""
global cbAlwaysOnTop := false
global cbRememberPos := false
global cbSavedX := ""
global cbSavedY := ""
global cbSavedW := 380
global cbSavedH := 600
global cbCurrentSection := 1
global cbSectionLabel := ""
global CB_FAST_SLOTS := 15           ; Number of "fast clip" slots at top
global CB_CFG_FILE := A_ScriptDir "\config\clipboard_settings.ini"

; ---- Toolbar button size ----
global TB_W := 30
global TB_H := 30

CB_BuildGUI() {
    global cbGui, cbListView, cbAlwaysOnTop, cbRememberPos
    global cbSavedX, cbSavedY, cbSavedW, cbSavedH
    global cbSectionLabel, CB_TEXT, CB_BG, CB_INPUT
    global TB_W, TB_H

    CB_LoadSettings()
    CB_LoadClipSettings()

    opts := "+Resize -MaximizeBox"
    if cbAlwaysOnTop
        opts .= " +AlwaysOnTop"
    cbGui := Gui(opts, "Clipboard")
    cbGui.SetFont("s9", "Segoe UI")
    cbGui.BackColor := CB_BG
    cbGui.MarginX := 0
    cbGui.MarginY := 0

    ; Enable dark title bar
    if (VerCompare(A_OSVersion, "10.0.17763") >= 0) {
        DWMWA := 19
        if (VerCompare(A_OSVersion, "10.0.18985") >= 0)
            DWMWA := 20
        DllCall("dwmapi\DwmSetWindowAttribute", "Ptr", cbGui.Hwnd,
            "Int", DWMWA, "Int*", 1, "Int", 4)
    }

    ; ============================================================
    ; LEFT VERTICAL TOOLBAR — Compact icon buttons
    ; ============================================================
    tbX := 4
    tbY := 6

    cbGui.SetFont("s8", "Segoe UI")

    btnPin := cbGui.Add("Button", "x" tbX " y" tbY " w" TB_W " h" TB_H, "📌")
    btnPin.OnEvent("Click", (*) => CB_ActionPin())

    tbY += TB_H + 2
    btnTag := cbGui.Add("Button", "x" tbX " y" tbY " w" TB_W " h" TB_H, "🏷")
    btnTag.OnEvent("Click", (*) => CB_ActionTag())

    ; Separator gap
    tbY += TB_H + 10

    btnToTop := cbGui.Add("Button", "x" tbX " y" tbY " w" TB_W " h" TB_H, "⤒")
    btnToTop.OnEvent("Click", (*) => CB_ActionStickTop())

    tbY += TB_H + 2
    btnUp := cbGui.Add("Button", "x" tbX " y" tbY " w" TB_W " h" TB_H, "▲")
    btnUp.OnEvent("Click", (*) => CB_ActionMoveUp())

    tbY += TB_H + 2
    btnDown := cbGui.Add("Button", "x" tbX " y" tbY " w" TB_W " h" TB_H, "▼")
    btnDown.OnEvent("Click", (*) => CB_ActionMoveDown())

    tbY += TB_H + 2
    btnToBot := cbGui.Add("Button", "x" tbX " y" tbY " w" TB_W " h" TB_H, "⤓")
    btnToBot.OnEvent("Click", (*) => CB_ActionStickBottom())

    ; Separator gap
    tbY += TB_H + 10

    btnEdit := cbGui.Add("Button", "x" tbX " y" tbY " w" TB_W " h" TB_H, "✎")
    btnEdit.OnEvent("Click", (*) => CB_ActionEdit())

    tbY += TB_H + 2
    btnDel := cbGui.Add("Button", "x" tbX " y" tbY " w" TB_W " h" TB_H, "✕")
    btnDel.OnEvent("Click", (*) => CB_ActionDelete())

    ; ============================================================
    ; MAIN LIST — Scrolling numbered clipboard slots
    ; ============================================================
    listX := TB_W + 10
    listW := cbSavedW - listX - 8

    cbGui.SetFont("s9 c" CB_TEXT, "Segoe UI")
    cbListView := cbGui.Add("ListView",
        "x" listX " y4 w" listW " h400 -Multi +Grid VScroll -Hdr Background" CB_INPUT " c" CB_TEXT,
        ["#", "P", "Clip", "Tag"])
    cbListView.OnEvent("DoubleClick", CB_LV_DoubleClick)

    ; Dark theme for ListView
    SendMessage(0x1036, 0, 0x1a1a1a, cbListView)
    SendMessage(0x1001, 0, 0x1a1a1a, cbListView)
    SendMessage(0x1024, 0, 0xDDDDDD, cbListView)

    ; ============================================================
    ; SEARCH BAR
    ; ============================================================
    global cbSearchEdit
    cbGui.SetFont("s8 c" CB_TEXT, "Segoe UI")
    cbSearchEdit := cbGui.Add("Edit", "x" listX " y+6 w" listW " h22 Background" CB_INPUT " c" CB_TEXT, "")
    cbSearchEdit.OnEvent("Change", (*) => CB_RefreshMainList())
    ; Placeholder hint via EM_SETCUEBANNER
    DllCall("SendMessage", "Ptr", cbSearchEdit.Hwnd, "UInt", 0x1501, "Int", 1, "Str", "Search clips...", "Ptr")

    ; ============================================================
    ; SCROLL TOGGLE — Switch between fast clips and full history
    ; ============================================================
    cbGui.SetFont("s9 Bold c" CB_TEXT, "Segoe UI")
    global cbScrollBtn
    cbScrollBtn := cbGui.Add("Button", "x" listX " y+4 w" listW " h26", "Show All History")
    cbScrollBtn.OnEvent("Click", (*) => CB_ToggleHistoryView())

    ; ============================================================
    ; SETTINGS SECTION
    ; ============================================================
    cbGui.SetFont("s8 c" CB_TEXT, "Segoe UI")
    cbGui.Add("Text", "x" listX " y+8 w" listW " h1 Background" CB_BORDER)

    chkOnTop := cbGui.Add("CheckBox", "x" listX " y+8 c" CB_TEXT, "On Top")
    chkOnTop.Value := cbAlwaysOnTop ? 1 : 0
    chkOnTop.OnEvent("Click", CB_ToggleOnTop)

    chkRemember := cbGui.Add("CheckBox", "x+15 c" CB_TEXT, "Remember Pos")
    chkRemember.Value := cbRememberPos ? 1 : 0
    chkRemember.OnEvent("Click", CB_ToggleRemember)

    ; ============================================================
    ; BOTTOM NAVIGATION — Section switcher
    ; ============================================================
    cbGui.Add("Text", "x" listX " y+6 w" listW " h1 Background" CB_BORDER)

    btnPrev := cbGui.Add("Button", "x" listX " y+4 w40 h24", "<")
    btnPrev.OnEvent("Click", (*) => CB_PrevSection())

    navW := listW - 90
    cbSectionLabel := cbGui.Add("Text", "x+2 w" navW " h24 Center c" CB_TEXT " 0x200", "Clips")

    btnNext := cbGui.Add("Button", "x+2 w40 h24", ">")
    btnNext.OnEvent("Click", (*) => CB_NextSection())

    ; ---- Events ----
    cbGui.OnEvent("Close", CB_OnClose)
    cbGui.OnEvent("Size", CB_OnSize)

    ; ---- Position near system tray (bottom right) ----
    showOpts := "w" cbSavedW " h" cbSavedH
    if cbRememberPos && cbSavedX != "" && cbSavedY != "" {
        showOpts .= " x" cbSavedX " y" cbSavedY
    } else {
        ; Default: bottom right, above taskbar
        MonitorGetWorkArea(, , , &monW, &monH)
        defaultX := monW - cbSavedW - 10
        defaultY := monH - cbSavedH - 10
        showOpts .= " x" defaultX " y" defaultY
    }
    cbGui.Show(showOpts)

    CB_RefreshMainList()
}

; ---- View state ----
global cbShowFullHistory := false

CB_ToggleHistoryView() {
    global cbShowFullHistory, cbScrollBtn
    cbShowFullHistory := !cbShowFullHistory
    cbScrollBtn.Text := cbShowFullHistory ? "Fast Clips (Top 15)" : "Show All History"
    CB_RefreshMainList()
}

; ---- Refresh the main numbered list ----
CB_RefreshMainList() {
    global cbListView, cbHistory, CB_FAST_SLOTS, cbCurrentSection, cbShowFullHistory

    cbListView.Delete()

    ; Settings section shows settings in the list
    if cbCurrentSection = 4 {
        CB_ShowSettingsInList()
        return
    }

    ; Get search query
    searchQ := ""
    try searchQ := Trim(cbSearchEdit.Value)

    ; Determine how many to show
    if cbShowFullHistory {
        limit := cbHistory.Length
    } else {
        limit := cbHistory.Length < CB_FAST_SLOTS ? cbHistory.Length : CB_FAST_SLOTS
    }

    count := 0
    for i, item in cbHistory {
        ; Section filtering
        if cbCurrentSection = 2 && !item.pinned
            continue
        if cbCurrentSection = 3 && item.tag = ""
            continue

        ; Search filtering
        if searchQ != "" {
            if !InStr(item.text, searchQ) && !InStr(item.tag, searchQ)
                continue
        }

        count++
        if count > limit
            break

        preview := StrReplace(SubStr(item.text, 1, 50), "`n", " ")
        if StrLen(item.text) > 50
            preview .= "..."
        pin := item.pinned ? "P" : ""
        tag := item.tag != "" ? item.tag : ""

        ; Visual separator after fast slots
        if !cbShowFullHistory || i <= CB_FAST_SLOTS {
            cbListView.Add("", i, pin, preview, tag)
        } else {
            if count = CB_FAST_SLOTS + 1 {
                ; Add separator row
                cbListView.Add("", "", "", "--- history ---", "")
            }
            cbListView.Add("", i, pin, preview, tag)
        }
    }
    cbListView.ModifyCol(1, 25)
    cbListView.ModifyCol(2, 20)
    cbListView.ModifyCol(3, 220)
    cbListView.ModifyCol(4, 55)
}

; ---- Settings displayed in ListView ----
CB_ShowSettingsInList() {
    global cbListView, cbAggregateMode, cbAggregateWindow, cbAggregateSeparator
    global CB_MAX_HISTORY, CB_MAX_DISPLAY

    cbListView.ModifyCol(1, 0)
    cbListView.ModifyCol(2, 0)
    cbListView.ModifyCol(3, 260)
    cbListView.ModifyCol(4, 60)

    cbListView.Add("", "", "", "Aggregate Copy", cbAggregateMode ? "ON" : "OFF")
    cbListView.Add("", "", "", "Aggregate Window (ms)", cbAggregateWindow)
    cbListView.Add("", "", "", "Aggregate Separator", cbAggregateSeparator = "`n" ? "newline" : cbAggregateSeparator)
    cbListView.Add("", "", "", "Max History", CB_MAX_HISTORY)
    cbListView.Add("", "", "", "Display Items", CB_MAX_DISPLAY)
    cbListView.Add("", "", "", "---", "---")
    cbListView.Add("", "", "", "Clear All History", "click E")
    cbListView.Add("", "", "", "Export History", "click E")
}

; ---- Toggle settings on double-click ----
CB_ToggleSettingByRow(row) {
    global cbAggregateMode, cbAggregateWindow, CB_MAX_HISTORY, CB_MAX_DISPLAY
    global cbGui, CB_BG, CB_TEXT, CB_INPUT

    if row = 1 {
        cbAggregateMode := !cbAggregateMode
        CB_RefreshMainList()
        CB_SaveClipSettings()
        ToolTip("Aggregate Copy: " (cbAggregateMode ? "ON" : "OFF"))
        SetTimer(() => ToolTip(), -1500)
    } else if row = 2 {
        ; Edit aggregate window
        editGui := Gui("+Owner" cbGui.Hwnd " +AlwaysOnTop", "Aggregate Window")
        editGui.BackColor := CB_BG
        editGui.SetFont("s9 c" CB_TEXT, "Segoe UI")
        editGui.Add("Text", , "Time window for stacking copies (ms):")
        editBox := editGui.Add("Edit", "w150 Number Background" CB_INPUT " c" CB_TEXT, cbAggregateWindow)
        btn := editGui.Add("Button", "w80", "Save")
        btn.OnEvent("Click", (*) => (cbAggregateWindow := Integer(editBox.Value), CB_SaveClipSettings(), CB_RefreshMainList(), editGui.Destroy()))
        editGui.Show()
    } else if row = 4 {
        editGui := Gui("+Owner" cbGui.Hwnd " +AlwaysOnTop", "Max History")
        editGui.BackColor := CB_BG
        editGui.SetFont("s9 c" CB_TEXT, "Segoe UI")
        editGui.Add("Text", , "Maximum history items (1-5000):")
        editBox := editGui.Add("Edit", "w150 Number Background" CB_INPUT " c" CB_TEXT, CB_MAX_HISTORY)
        btn := editGui.Add("Button", "w80", "Save")
        btn.OnEvent("Click", (*) => (CB_MAX_HISTORY := Integer(editBox.Value), CB_SaveClipSettings(), CB_RefreshMainList(), editGui.Destroy()))
        editGui.Show()
    } else if row = 5 {
        editGui := Gui("+Owner" cbGui.Hwnd " +AlwaysOnTop", "Display Items")
        editGui.BackColor := CB_BG
        editGui.SetFont("s9 c" CB_TEXT, "Segoe UI")
        editGui.Add("Text", , "Items shown in main list (1-100):")
        editBox := editGui.Add("Edit", "w150 Number Background" CB_INPUT " c" CB_TEXT, CB_MAX_DISPLAY)
        btn := editGui.Add("Button", "w80", "Save")
        btn.OnEvent("Click", (*) => (CB_MAX_DISPLAY := Integer(editBox.Value), CB_SaveClipSettings(), editGui.Destroy()))
        editGui.Show()
    } else if row = 7 {
        if MsgBox("Clear ALL clipboard history?", "Confirm", "YesNo Icon!") = "Yes" {
            cbHistory := []
            CB_SaveHistory()
            CB_RefreshMainList()
        }
    }
}

; ---- Save/Load clip-specific settings ----
CB_SaveClipSettings() {
    global CB_CFG_FILE, cbAggregateMode, cbAggregateWindow, CB_MAX_HISTORY, CB_MAX_DISPLAY
    try {
        IniWrite(cbAggregateMode ? "1" : "0", CB_CFG_FILE, "Clipboard", "aggregateMode")
        IniWrite(cbAggregateWindow, CB_CFG_FILE, "Clipboard", "aggregateWindow")
        IniWrite(CB_MAX_HISTORY, CB_CFG_FILE, "Clipboard", "maxHistory")
        IniWrite(CB_MAX_DISPLAY, CB_CFG_FILE, "Clipboard", "maxDisplay")
    }
}

CB_LoadClipSettings() {
    global CB_CFG_FILE, cbAggregateMode, cbAggregateWindow, CB_MAX_HISTORY, CB_MAX_DISPLAY
    if !FileExist(CB_CFG_FILE)
        return
    try {
        cbAggregateMode := IniRead(CB_CFG_FILE, "Clipboard", "aggregateMode", "1") = "1"
        cbAggregateWindow := Integer(IniRead(CB_CFG_FILE, "Clipboard", "aggregateWindow", "2000"))
        CB_MAX_HISTORY := Integer(IniRead(CB_CFG_FILE, "Clipboard", "maxHistory", "1000"))
        CB_MAX_DISPLAY := Integer(IniRead(CB_CFG_FILE, "Clipboard", "maxDisplay", "20"))
    }
}

; ---- Get real history index from selected row ----
CB_GetSelectedIndex() {
    global cbListView
    row := cbListView.GetNext()
    if row < 1
        return 0
    return Integer(cbListView.GetText(row, 1))
}

; ---- Action handlers ----
CB_ActionPin(*) {
    idx := CB_GetSelectedIndex()
    if idx > 0
        CB_TogglePin(idx)
}

CB_ActionTag(*) {
    global cbHistory, cbGui, CB_BG, CB_TEXT, CB_INPUT
    idx := CB_GetSelectedIndex()
    if idx < 1 || idx > cbHistory.Length
        return
    tagGui := Gui("+Owner" cbGui.Hwnd " +AlwaysOnTop", "Set Tag")
    tagGui.BackColor := CB_BG
    tagGui.SetFont("s9 c" CB_TEXT, "Segoe UI")
    tagGui.Add("Text", , "Tag for this clip:")
    tagEdit := tagGui.Add("Edit", "w200 Background" CB_INPUT " c" CB_TEXT, cbHistory[idx].tag)
    btnSave := tagGui.Add("Button", "w80", "Save")
    btnSave.OnEvent("Click", (*) => (CB_SetTag(idx, tagEdit.Value), tagGui.Destroy()))
    btnClear := tagGui.Add("Button", "x+10 w80", "Clear")
    btnClear.OnEvent("Click", (*) => (CB_SetTag(idx, ""), tagGui.Destroy()))
    tagGui.Show()
}

CB_ActionStickTop(*) {
    idx := CB_GetSelectedIndex()
    if idx > 0
        CB_StickToTop(idx)
}

CB_ActionStickBottom(*) {
    idx := CB_GetSelectedIndex()
    if idx > 0
        CB_StickToBottom(idx)
}

CB_ActionMoveUp(*) {
    idx := CB_GetSelectedIndex()
    if idx > 0
        CB_MoveUp(idx)
}

CB_ActionMoveDown(*) {
    idx := CB_GetSelectedIndex()
    if idx > 0
        CB_MoveDown(idx)
}

CB_ActionDelete(*) {
    idx := CB_GetSelectedIndex()
    if idx > 0
        CB_DeleteItem(idx)
}

CB_ActionEdit(*) {
    global cbHistory, cbGui, CB_BG, CB_TEXT, CB_INPUT
    idx := CB_GetSelectedIndex()
    if idx < 1 || idx > cbHistory.Length
        return
    editGui := Gui("+Owner" cbGui.Hwnd " +AlwaysOnTop", "Edit Clip")
    editGui.BackColor := CB_BG
    editGui.SetFont("s9 c" CB_TEXT, "Segoe UI")
    editGui.Add("Text", , "Edit clipboard item:")
    editBox := editGui.Add("Edit", "w400 r10 Background" CB_INPUT " c" CB_TEXT, cbHistory[idx].text)
    btnSave := editGui.Add("Button", "w100", "Save")
    btnSave.OnEvent("Click", (*) => (CB_EditItem(idx, editBox.Value), editGui.Destroy()))
    btnCancel := editGui.Add("Button", "x+10 w100", "Cancel")
    btnCancel.OnEvent("Click", (*) => editGui.Destroy())
    editGui.Show()
}

CB_LV_DoubleClick(lv, row) {
    global cbCurrentSection
    if cbCurrentSection = 4 {
        CB_ToggleSettingByRow(row)
        return
    }
    idx := CB_GetSelectedIndex()
    if idx > 0
        CB_PasteItem(idx)
}

; ---- Settings toggles ----
CB_ToggleOnTop(ctrl, *) {
    global cbGui, cbAlwaysOnTop
    cbAlwaysOnTop := ctrl.Value ? true : false
    WinSetAlwaysOnTop(cbAlwaysOnTop ? 1 : 0, "ahk_id " cbGui.Hwnd)
    CB_SaveSettings()
}

CB_ToggleRemember(ctrl, *) {
    global cbRememberPos
    cbRememberPos := ctrl.Value ? true : false
    if cbRememberPos
        CB_SaveCurrentPos()
    CB_SaveSettings()
}

; ---- Section navigation ----
CB_SectionNames := ["Clips", "Pinned", "Tagged", "Settings"]

CB_PrevSection() {
    global cbCurrentSection, cbSectionLabel, CB_SectionNames
    cbCurrentSection := cbCurrentSection > 1 ? cbCurrentSection - 1 : CB_SectionNames.Length
    cbSectionLabel.Text := CB_SectionNames[cbCurrentSection]
    CB_RefreshMainList()
}

CB_NextSection() {
    global cbCurrentSection, cbSectionLabel, CB_SectionNames
    cbCurrentSection := cbCurrentSection < CB_SectionNames.Length ? cbCurrentSection + 1 : 1
    cbSectionLabel.Text := CB_SectionNames[cbCurrentSection]
    CB_RefreshMainList()
}

; ---- Window events ----
CB_OnClose(*) {
    global cbRememberPos
    if cbRememberPos
        CB_SaveCurrentPos()
    CB_SaveSettings()
    ExitApp()
}

CB_OnSize(guiObj, minMax, w, h) {
    global cbListView, cbSavedW, cbSavedH, TB_W
    if minMax = -1
        return
    cbSavedW := w
    cbSavedH := h
    listX := TB_W + 10
    try cbListView.Move(, , w - listX - 8, h - 200)
}

CB_SaveCurrentPos() {
    global cbGui, cbSavedX, cbSavedY, cbSavedW, cbSavedH
    try {
        cbGui.GetPos(&x, &y)
        cbGui.GetClientPos(, , &w, &h)
        cbSavedX := x
        cbSavedY := y
        cbSavedW := w
        cbSavedH := h
    }
}

; ---- Settings persistence ----
CB_SaveSettings() {
    global CB_CFG_FILE, cbAlwaysOnTop, cbRememberPos
    global cbSavedX, cbSavedY, cbSavedW, cbSavedH
    try {
        IniWrite(cbAlwaysOnTop ? "1" : "0", CB_CFG_FILE, "Window", "alwaysOnTop")
        IniWrite(cbRememberPos ? "1" : "0", CB_CFG_FILE, "Window", "rememberPos")
        IniWrite(cbSavedX, CB_CFG_FILE, "Window", "x")
        IniWrite(cbSavedY, CB_CFG_FILE, "Window", "y")
        IniWrite(cbSavedW, CB_CFG_FILE, "Window", "w")
        IniWrite(cbSavedH, CB_CFG_FILE, "Window", "h")
    }
}

CB_LoadSettings() {
    global CB_CFG_FILE, cbAlwaysOnTop, cbRememberPos
    global cbSavedX, cbSavedY, cbSavedW, cbSavedH
    if !FileExist(CB_CFG_FILE)
        return
    try {
        cbAlwaysOnTop := IniRead(CB_CFG_FILE, "Window", "alwaysOnTop", "0") = "1"
        cbRememberPos := IniRead(CB_CFG_FILE, "Window", "rememberPos", "0") = "1"
        cbSavedX := IniRead(CB_CFG_FILE, "Window", "x", "")
        cbSavedY := IniRead(CB_CFG_FILE, "Window", "y", "")
        cbSavedW := IniRead(CB_CFG_FILE, "Window", "w", "380")
        cbSavedH := IniRead(CB_CFG_FILE, "Window", "h", "600")
    }
}
