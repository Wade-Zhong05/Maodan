# Maodan Desktop Pet

Maodan (毛蛋) is a silver tabby American Shorthair who lives on your desktop. Originally created as PROMIS's desktop companion, Maodan is now a standalone application that does not connect to PROMIS or require a server or network connection while running.

## Getting Started

Double-click **`Start Maodan.bat`** and Maodan will appear in the bottom-right corner of your screen.

- Nothing needs to be installed first. On the first launch, the script downloads its own copy of [Pixi](https://pixi.sh) (a pinned, checksum-verified release) into this folder and uses `pixi.lock` to build an isolated Python and Tk environment next to it. This one-time setup needs an internet connection (github.com and conda.anaconda.org) and takes a minute or two, but no administrator rights; nothing is installed system-wide or added to `PATH`, so deleting the folder removes everything. If setup cannot finish, the launcher falls back to an existing Python 3 with Tkinter, and running it again continues where it stopped.
- If you downloaded Maodan as a `.zip`, extract the whole folder before double-clicking the launcher.
- If Maodan is already running, double-clicking the launcher again brings him back to the screen—even after using *Hide for now*—instead of opening a second instance.

## Interactions

| Action | Response |
|---|---|
| Drag Maodan | Drag sideways to run, upward to jump, or downward to lie down; Maodan waves when released |
| Click Maodan | Meows and performs a random trick |
| Hover over Maodan | Follows the pointer with his eyes |
| Type anywhere | Studies alongside you; this can be disabled from the menu |
| Leave Maodan idle | Finds something to do after a while |

Right-click Maodan to open the menu:

- **Play with Maodan** — choose from eight animations
- **Size** — resize Maodan from 25% to 150%
- **Reduce motion** — limit animation
- **Study along while I type** — toggle typing-aware study mode
- **Hide for now** — temporarily hide Maodan
- **Quit Maodan** — close the application

Study mode asks Windows only whether a typing key is currently pressed. It does not record which key was pressed or send any information anywhere.

Size and study-mode preferences are stored in `%APPDATA%\Maodan\settings.json`. If Maodan exits unexpectedly, error details are written to `maodan.log` in the same directory.

## Development

```console
pixi run start                # Run with a console for easier debugging
pixi run test                 # Run the unit tests
pixi run -e art build-atlas   # Rebuild sprites from art/ using Pillow
```

## Project Structure

```text
maodan/
├── Start Maodan.bat      One-click Windows launcher
├── maodan.py             Desktop pet application using Python and Tkinter
├── instance.py           Enforces a single instance and wakes an existing one
├── assets/               Runtime animation manifests and sprite sheets
├── art/                  Source pose artwork used to generate sprite sheets
├── tools/build_atlas.py  Builds runtime sprite sheets from art/
├── tests/                Unit tests
└── pixi.toml, pixi.lock  Reproducible Python environment
```
