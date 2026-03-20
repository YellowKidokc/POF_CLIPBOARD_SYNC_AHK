; ============================================================
; Module: Research Links — Quick-access URL repository
; ============================================================
; Add to manifest.ahk:  #include .\research_links.ahk
; Links stored in config\research_links.json
; ============================================================

#Requires AutoHotkey v2.0+

; ---- Register tab (hub mode only) ----
if IsSet(HUB_CORE_LOADED)
    RegisterTab("Research", Build_ResearchTab, 35)

; ---- State ----
global gResearchLinks := []
global RESEARCH_FILE := A_ScriptDir "\config\research_links.json"
global gEditingLinkIndex := 0

; ---- Default categories ----
global RESEARCH_CATEGORIES := [
    "Physics", "Theology", "Consciousness", "Mathematics",
    "AI / ML", "Databases", "Tools", "Journals",
    "Scripture", "Reference", "News", "Other"
]

Build_ResearchTab() {
    global gShell, DARK_TEXT, DARK_BG, DARK_CTRL, gResearchLinks, RESEARCH_CATEGORIES

    gShell.gui.SetFont("s10 Bold c" DARK_TEXT, "Segoe UI")

    ; --- LEFT: Add/Edit ---
    gShell.gui.Add("Text", "xm+15 ym+45", "Add Research Link")
    gShell.gui.SetFont("s9 Bold c" DARK_TEXT, "Segoe UI")

    gShell.gui.Add("Text", "xm+15 y+20 c" DARK_TEXT, "Category:")
    gShell.linkCatDDL := gShell.gui.Add("DropDownList", "x+10 w150 Choose1", RESEARCH_CATEGORIES)
    ApplyDarkTheme(gShell.linkCatDDL)
    ApplyInputTheme(gShell.linkCatDDL)

    gShell.gui.Add("Text", "xm+15 y+12 c" DARK_TEXT, "Name:")
    gShell.linkNameEdit := gShell.gui.Add("Edit", "x+40 w280", "")
    ApplyDarkTheme(gShell.linkNameEdit)
    ApplyInputTheme(gShell.linkNameEdit)

    gShell.gui.Add("Text", "xm+15 y+12 c" DARK_TEXT, "URL:")
    gShell.linkURLEdit := gShell.gui.Add("Edit", "x+50 w280", "")
    ApplyDarkTheme(gShell.linkURLEdit)
    ApplyInputTheme(gShell.linkURLEdit)

    gShell.gui.Add("Text", "xm+15 y+12 c" DARK_TEXT, "Notes:")
    gShell.linkNotesEdit := gShell.gui.Add("Edit", "x+35 w280 r2", "")
    ApplyDarkTheme(gShell.linkNotesEdit)
    ApplyInputTheme(gShell.linkNotesEdit)

    gShell.gui.Add("Text", "xm+15 y+12 c" DARK_TEXT, "Tags:")
    gShell.linkTagsEdit := gShell.gui.Add("Edit", "x+42 w280", "")
    ApplyDarkTheme(gShell.linkTagsEdit)
    ApplyInputTheme(gShell.linkTagsEdit)
    gShell.gui.Add("Text", "x+5 c888888", "(comma-separated)")

    gShell.btnSaveLink := gShell.gui.Add("Button", "xm+15 y+20 w90", "Add/Save")
    gShell.btnSaveLink.OnEvent("Click", (*) => SaveResearchLink())
    ApplyDarkTheme(gShell.btnSaveLink)

    gShell.btnNewLink := gShell.gui.Add("Button", "x+8 w70", "New")
    gShell.btnNewLink.OnEvent("Click", (*) => ClearLinkEditor())
    ApplyDarkTheme(gShell.btnNewLink)

    gShell.btnDeleteLink := gShell.gui.Add("Button", "x+8 w70", "Delete")
    gShell.btnDeleteLink.OnEvent("Click", (*) => DeleteResearchLink())
    ApplyDarkTheme(gShell.btnDeleteLink)

    gShell.btnOpenLink := gShell.gui.Add("Button", "x+8 w80", "Open URL")
    gShell.btnOpenLink.OnEvent("Click", (*) => OpenSelectedLink())
    ApplyDarkTheme(gShell.btnOpenLink)

    gShell.linkStatusTxt := gShell.gui.Add("Text", "xm+15 y+15 w390 c888888", "")

    gShell.gui.Add("Text", "xm+15 y+20 w400 h1 Background333333")
    gShell.gui.SetFont("s9 c888888", "Segoe UI")
    gShell.gui.Add("Text", "xm+15 y+10", "Paste URL from clipboard:")
    gShell.btnQuickAdd := gShell.gui.Add("Button", "x+10 w100", "Paste + Add")
    gShell.btnQuickAdd.OnEvent("Click", (*) => QuickAddLink())
    ApplyDarkTheme(gShell.btnQuickAdd)
    gShell.gui.SetFont("s9 Bold c" DARK_TEXT, "Segoe UI")

    ; --- RIGHT: Library ---
    gShell.gui.Add("Text", "x460 ym+45 c" DARK_TEXT, "Research Library")

    gShell.gui.Add("Text", "x460 y+10 c888888", "Filter:")
    filterCats := ["All"]
    for cat in RESEARCH_CATEGORIES
        filterCats.Push(cat)
    gShell.linkFilterDDL := gShell.gui.Add("DropDownList", "x+5 w120 Choose1", filterCats)
    gShell.linkFilterDDL.OnEvent("Change", (*) => RefreshLinksLV())
    ApplyDarkTheme(gShell.linkFilterDDL)
    ApplyInputTheme(gShell.linkFilterDDL)

    gShell.linkSearchEdit := gShell.gui.Add("Edit", "x+10 w150", "")
    gShell.linkSearchEdit.OnEvent("Change", (*) => RefreshLinksLV())
    ApplyDarkTheme(gShell.linkSearchEdit)
    ApplyInputTheme(gShell.linkSearchEdit)
    gShell.gui.Add("Text", "x+5 c888888", "Search")

    gShell.linksLV := gShell.gui.Add("ListView", "x460 y+10 w590 h380 -Multi +Grid",
        ["Category", "Name", "URL", "Notes", "Tags"])
    gShell.linksLV.OnEvent("Click", LinkLV_OnClick)
    gShell.linksLV.OnEvent("DoubleClick", LinkLV_OnDoubleClick)
    ApplyDarkListView(gShell.linksLV)

    gShell.gui.Add("Text", "x460 y+8 c888888", "Double-click to open in browser  |  Click to edit")

    LoadResearchLinks()
    RefreshLinksLV()
}

SaveResearchLink(*) {
    global gShell, gResearchLinks, gEditingLinkIndex
    name := Trim(gShell.linkNameEdit.Value)
    url := Trim(gShell.linkURLEdit.Value)
    cat := gShell.linkCatDDL.Text
    notes := gShell.linkNotesEdit.Value
    tags := gShell.linkTagsEdit.Value

    if name = "" || url = "" {
        gShell.linkStatusTxt.Text := "Name and URL required"
        return
    }
    if !RegExMatch(url, "^https?://")
        url := "https://" url

    link := {
        category: cat,
        name: name,
        url: url,
        notes: notes,
        tags: tags,
        added: FormatTime(A_Now, "yyyy-MM-dd HH:mm")
    }

    if gEditingLinkIndex > 0 {
        gResearchLinks[gEditingLinkIndex] := link
        gEditingLinkIndex := 0
    } else {
        gResearchLinks.Push(link)
    }

    PersistResearchLinks()
    RefreshLinksLV()
    ClearLinkEditor()
    gShell.linkStatusTxt.Text := "Saved: " name
    SetTimer(() => (gShell.linkStatusTxt.Text := ""), -2000)
}

DeleteResearchLink(*) {
    global gShell, gResearchLinks, gEditingLinkIndex
    row := gShell.linksLV.GetNext()
    if row <= 0 {
        gShell.linkStatusTxt.Text := "Select a link to delete"
        return
    }
    idx := GetFilteredLinkIndex(row)
    if idx <= 0
        return
    if MsgBox("Delete this link?", "Confirm", "YesNo Icon!") = "Yes" {
        gResearchLinks.RemoveAt(idx)
        gEditingLinkIndex := 0
        PersistResearchLinks()
        RefreshLinksLV()
        ClearLinkEditor()
        gShell.linkStatusTxt.Text := "Deleted"
    }
}

OpenSelectedLink(*) {
    global gShell, gResearchLinks
    row := gShell.linksLV.GetNext()
    if row <= 0
        return
    idx := GetFilteredLinkIndex(row)
    if idx > 0
        Run(gResearchLinks[idx].url)
}

ClearLinkEditor(*) {
    global gShell, gEditingLinkIndex
    gEditingLinkIndex := 0
    gShell.linkNameEdit.Value := ""
    gShell.linkURLEdit.Value := ""
    gShell.linkNotesEdit.Value := ""
    gShell.linkTagsEdit.Value := ""
}

QuickAddLink(*) {
    global gShell
    url := Trim(A_Clipboard)
    if !RegExMatch(url, "^https?://") {
        gShell.linkStatusTxt.Text := "Clipboard doesn't look like a URL"
        SetTimer(() => (gShell.linkStatusTxt.Text := ""), -2000)
        return
    }
    gShell.linkURLEdit.Value := url
    if RegExMatch(url, "https?://(?:www\.)?([^/]+)", &m)
        gShell.linkNameEdit.Value := m[1]
    gShell.linkNameEdit.Focus()
    gShell.linkStatusTxt.Text := "URL pasted — add a name and save"
}

LinkLV_OnClick(lv, row) {
    global gShell, gResearchLinks, gEditingLinkIndex
    if row <= 0
        return
    idx := GetFilteredLinkIndex(row)
    if idx <= 0
        return
    link := gResearchLinks[idx]
    gEditingLinkIndex := idx
    gShell.linkCatDDL.Text := link.category
    gShell.linkNameEdit.Value := link.name
    gShell.linkURLEdit.Value := link.url
    gShell.linkNotesEdit.Value := link.HasProp("notes") ? link.notes : ""
    gShell.linkTagsEdit.Value := link.HasProp("tags") ? link.tags : ""
}

LinkLV_OnDoubleClick(lv, row) {
    global gResearchLinks
    if row <= 0
        return
    idx := GetFilteredLinkIndex(row)
    if idx > 0
        Run(gResearchLinks[idx].url)
}

GetFilteredLinkIndex(filteredRow) {
    global gShell, gResearchLinks
    filterCat := gShell.linkFilterDDL.Text
    searchTerm := gShell.linkSearchEdit.Value
    count := 0
    for i, link in gResearchLinks {
        if filterCat != "All" && link.category != filterCat
            continue
        if searchTerm != "" {
            haystack := link.name " " link.url " " (link.HasProp("notes") ? link.notes : "") " " (link.HasProp("tags") ? link.tags : "")
            if !InStr(haystack, searchTerm)
                continue
        }
        count++
        if count = filteredRow
            return i
    }
    return 0
}

RefreshLinksLV(*) {
    global gShell, gResearchLinks
    gShell.linksLV.Delete()
    filterCat := gShell.linkFilterDDL.Text
    searchTerm := gShell.linkSearchEdit.Value
    for link in gResearchLinks {
        if filterCat != "All" && link.category != filterCat
            continue
        if searchTerm != "" {
            haystack := link.name " " link.url " " (link.HasProp("notes") ? link.notes : "") " " (link.HasProp("tags") ? link.tags : "")
            if !InStr(haystack, searchTerm)
                continue
        }
        urlPreview := StrLen(link.url) > 40 ? SubStr(link.url, 1, 40) "..." : link.url
        notes := link.HasProp("notes") ? link.notes : ""
        notesPreview := StrLen(notes) > 25 ? SubStr(notes, 1, 25) "..." : notes
        tags := link.HasProp("tags") ? link.tags : ""
        gShell.linksLV.Add("", link.category, link.name, urlPreview, notesPreview, tags)
    }
    gShell.linksLV.ModifyCol(1, 80)
    gShell.linksLV.ModifyCol(2, 140)
    gShell.linksLV.ModifyCol(3, 180)
    gShell.linksLV.ModifyCol(4, 100)
    gShell.linksLV.ModifyCol(5, 80)
}

LoadResearchLinks() {
    global gResearchLinks, RESEARCH_FILE
    gResearchLinks := []
    if !FileExist(RESEARCH_FILE)
        return
    try {
        raw := FileRead(RESEARCH_FILE, "UTF-8")
        if raw = "" || raw = "[]"
            return
        pattern := '\{"category":"((?:[^"\\]|\\.)*)\".*?"name":"((?:[^"\\]|\\.)*)\".*?"url":"((?:[^"\\]|\\.)*)"'
        pos := 1
        while RegExMatch(raw, pattern, &m, pos) {
            objStart := m.Pos
            objEnd := InStr(raw, "}", , objStart)
            objStr := SubStr(raw, objStart, objEnd - objStart + 1)
            notes := ""
            if RegExMatch(objStr, '"notes"\s*:\s*"((?:[^"\\]|\\.)*)"', &nm)
                notes := UnescapeJSON(nm[1])
            tags := ""
            if RegExMatch(objStr, '"tags"\s*:\s*"((?:[^"\\]|\\.)*)"', &tm)
                tags := UnescapeJSON(tm[1])
            added := ""
            if RegExMatch(objStr, '"added"\s*:\s*"([^"]*)"', &am)
                added := am[1]
            gResearchLinks.Push({
                category: UnescapeJSON(m[1]),
                name: UnescapeJSON(m[2]),
                url: UnescapeJSON(m[3]),
                notes: notes,
                tags: tags,
                added: added
            })
            pos := objEnd + 1
        }
    }
}

PersistResearchLinks() {
    global gResearchLinks, RESEARCH_FILE
    jsonStr := "["
    for i, link in gResearchLinks {
        jsonStr .= "`n  {"
        jsonStr .= '"category":"' EscapeJSON(link.category) '", '
        jsonStr .= '"name":"' EscapeJSON(link.name) '", '
        jsonStr .= '"url":"' EscapeJSON(link.url) '", '
        jsonStr .= '"notes":"' EscapeJSON(link.HasProp("notes") ? link.notes : "") '", '
        jsonStr .= '"tags":"' EscapeJSON(link.HasProp("tags") ? link.tags : "") '", '
        jsonStr .= '"added":"' (link.HasProp("added") ? link.added : "") '"'
        jsonStr .= "}" (i < gResearchLinks.Length ? "," : "")
    }
    jsonStr .= "`n]"
    try FileDelete(RESEARCH_FILE)
    FileAppend(jsonStr, RESEARCH_FILE, "UTF-8")
}
