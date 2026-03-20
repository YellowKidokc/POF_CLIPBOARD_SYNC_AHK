#Requires AutoHotkey v2.0+

; ============================================================
; CLIPBOARD HISTORY — Searchable history window (~1000 items)
; ============================================================

global cbHistGui := ""
global cbHistLV := ""
global cbHistSearch := ""

CB_ShowHistory() {
    global cbHistGui, cbHistLV, cbHistSearch, cbGui
    global CB_BG, CB_TEXT, CB_INPUT, CB_BORDER

    ; Destroy existing if open
    try cbHistGui.Destroy()

    cbHistGui := Gui("+Resize +AlwaysOnTop", "Clipboard History")
    cbHistGui.SetFont("s9", "Segoe UI")
    cbHistGui.BackColor := CB_BG

    ; Enable dark title bar
    if (VerCompare(A_OSVersion, "10.0.17763") >= 0) {
        DWMWA := 19
        if (VerCompare(A_OSVersion, "10.0.18985") >= 0)
            DWMWA := 20
        DllCall("dwmapi\DwmSetWindowAttribute", "Ptr", cbHistGui.Hwnd,
            "Int", DWMWA, "Int*", 1, "Int", 4)
    }

    ; ---- Search bar (always visible, not in scroll area) ----
    cbHistGui.SetFont("s9 c" CB_TEXT, "Segoe UI")
    cbHistGui.Add("Text", "xm+5 ym+8 c" CB_TEXT, "Search:")
    cbHistSearch := cbHistGui.Add("Edit", "x+8 w450 Background" CB_INPUT " c" CB_TEXT, "")
    cbHistSearch.OnEvent("Change", (*) => CB_FilterHistory())

    btnClear := cbHistGui.Add("Button", "x+5 w60", "Clear")
    btnClear.OnEvent("Click", (*) => (cbHistSearch.Value := "", CB_FilterHistory()))

    ; ---- Separator ----
    cbHistGui.Add("Text", "xm+5 y+8 w570 h1 Background" CB_BORDER)

    ; ---- Scrolling history list ----
    cbHistLV := cbHistGui.Add("ListView", "xm+5 y+5 w570 h500 -Multi +Grid VScroll -Hdr Background" CB_INPUT " c" CB_TEXT, ["#", "Clip"])

    ; Dark theme for ListView
    SendMessage(0x1036, 0, 0x1a1a1a, cbHistLV)
    SendMessage(0x1001, 0, 0x1a1a1a, cbHistLV)
    SendMessage(0x1024, 0, 0xDDDDDD, cbHistLV)

    cbHistLV.OnEvent("DoubleClick", CB_HistLV_DoubleClick)

    ; ---- Bottom action bar ----
    cbHistGui.SetFont("s8 c" CB_TEXT, "Segoe UI")
    cbHistGui.Add("Text", "xm+5 y+8 w570 h1 Background" CB_BORDER)

    btnPaste := cbHistGui.Add("Button", "xm+5 y+8 w80", "Paste")
    btnPaste.OnEvent("Click", (*) => CB_HistPaste())

    btnCopyToClip := cbHistGui.Add("Button", "x+5 w80", "Copy")
    btnCopyToClip.OnEvent("Click", (*) => CB_HistCopy())

    btnDeleteHist := cbHistGui.Add("Button", "x+5 w80", "Delete")
    btnDeleteHist.OnEvent("Click", (*) => CB_HistDelete())

    btnToTop := cbHistGui.Add("Button", "x+5 w80", "To Top")
    btnToTop.OnEvent("Click", (*) => CB_HistToTop())

    countLabel := cbHistGui.Add("Text", "x+20 w150 c888888 0x200", cbHistory.Length " items")

    cbHistGui.OnEvent("Close", (*) => cbHistGui.Destroy())
    cbHistGui.OnEvent("Size", CB_HistOnSize)
    cbHistGui.Show("w590 h620")

    CB_PopulateHistory()
}

CB_PopulateHistory(filter := "") {
    global cbHistLV, cbHistory
    cbHistLV.Delete()
    for i, item in cbHistory {
        preview := StrReplace(SubStr(item.text, 1, 100), "`n", " ")
        if StrLen(item.text) > 100
            preview .= "..."
        if filter != "" {
            if !InStr(preview, filter) && !InStr(item.text, filter)
                continue
        }
        pin := item.pinned ? "[P]" : ""
        tag := item.tag != "" ? "[" item.tag "]" : ""
        display := pin . tag . (pin != "" || tag != "" ? " " : "") . preview
        cbHistLV.Add("", i, display)
    }
    cbHistLV.ModifyCol(1, 40)
    cbHistLV.ModifyCol(2, 510)
}

CB_FilterHistory() {
    global cbHistSearch
    CB_PopulateHistory(cbHistSearch.Value)
}

CB_HistGetSelectedIndex() {
    global cbHistLV
    row := cbHistLV.GetNext()
    if row < 1
        return 0
    return Integer(cbHistLV.GetText(row, 1))
}

CB_HistLV_DoubleClick(lv, row) {
    idx := CB_HistGetSelectedIndex()
    if idx > 0
        CB_PasteItem(idx)
}

CB_HistPaste() {
    idx := CB_HistGetSelectedIndex()
    if idx > 0
        CB_PasteItem(idx)
}

CB_HistCopy() {
    global cbHistory
    idx := CB_HistGetSelectedIndex()
    if idx > 0 && idx <= cbHistory.Length
        A_Clipboard := cbHistory[idx].text
}

CB_HistDelete() {
    idx := CB_HistGetSelectedIndex()
    if idx > 0 {
        CB_DeleteItem(idx)
        CB_PopulateHistory()
    }
}

CB_HistToTop() {
    idx := CB_HistGetSelectedIndex()
    if idx > 0 {
        CB_StickToTop(idx)
        CB_PopulateHistory()
    }
}

CB_HistOnSize(guiObj, minMax, w, h) {
    global cbHistLV
    if minMax = -1
        return
    try cbHistLV.Move(, , w - 20, h - 120)
}
