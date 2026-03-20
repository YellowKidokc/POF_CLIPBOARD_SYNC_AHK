; ============================================================
; MODULE MANIFEST
; Add new modules here. Each module can:
;  - RegisterTab(name, buildFn, order)
;  - Add hotkeys/hotstrings
;  - Add helper functions/classes
; ============================================================

; Utilities: quick toggles (Always On Top, Remember Position) and mini scripts
#include utilities_tab.ahk

; Auto-Clicker: multi-slot coordinate clicker with sequential mode
#include autoclicker.ahk

; Quick Prompt Invoker: "/" slash commands for fast prompt paste
#include quick_prompt.ahk

; Hotkey Menu: Ctrl+Shift+Z prompt menu (select text → AI process)
#include hotkey_menu.ahk

; Research Links: URL repository with categories, search, click-to-open
#include research_links.ahk

; Overnight Operations: Ollama YAML enrichment, batch analytics, knowledge graphs
#include overnight_ops.ahk

; ClipSync Bridge: Dynamic hotkeys, HTML interfaces (Ctrl+Alt+P/L/S)
#include ..\clipsync-bridge\clipsync_bridge.ahk

; BetterTTS: TTS status and controls tab (process runs separately)
#include bettertts_tab.ahk

; NOTE: Clipboard Manager now lives in .\clipboard\ as a standalone app
