# AI-HUB v2 Setup For Friends

## Before You Zip It

- Do not share `config/settings.ini` as-is. It contains personal API keys.
- Keep `config/settings.example.ini` in the package.
- Remove any personal prompts, bookmarks, or clipboard history you do not want to share from `config/`.

## What They Need

- Windows 10 or 11
- [AutoHotkey v2](https://www.autohotkey.com/)
- Python 3.10+
- Microsoft Edge or Google Chrome

## Install Steps

1. Extract the folder anywhere they want.
2. Copy `config/settings.example.ini` to `config/settings.ini`.
3. Add their own API keys in `config/settings.ini`.
4. Run `AI-HUB.ahk`.

## What Starts Automatically

- The main AI-HUB window
- The local Python bridge server on `http://localhost:3456`
- The `POF 2828` prompt picker
- Research links
- BetterTTS

## First Checks

- Open the prompt picker and create a test prompt.
- Confirm it saves and is still there after refresh.
- Hit `Ctrl+Alt+P` to reopen prompts.
- Hit `Ctrl+Alt+S` to confirm the bridge server is running.

## Packaging Notes

- Zip the whole `AI-HUB-v2` folder.
- Exclude `.git/`.
- Exclude personal secrets from `config/settings.ini`.
- If you want a clean starter build, keep `config/settings.example.ini` and remove private data files from `config/`.
