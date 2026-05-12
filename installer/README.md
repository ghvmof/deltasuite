# DeltaSuite installer

Tools to produce binary distributions of DeltaSuite.

## Layout

```
installer/
├── build.py            # End-to-end orchestrator (icons → PyInstaller → ISCC).
├── deltasuite.spec     # PyInstaller spec (Windows + macOS + Linux).
├── deltasuite.iss      # Inno Setup script (Windows only).
├── entry.py            # PyInstaller entry point importing deltasuite.app.
└── branding/           # Generated icons (see scripts/make_icons.py).
```

The output goes to `installer/dist/`:

* `installer/dist/DeltaSuite/` — PyInstaller one-folder bundle (cross-platform).
* `installer/dist/installer/DeltaSuite-<version>-Setup.exe` — Inno Setup
  output, only on Windows.

## One-shot local build (Windows)

```powershell
.\.venv\Scripts\activate
pip install -e .[build]
python installer\build.py
```

The script auto-detects [Inno Setup 6](https://jrsoftware.org/isinfo.php)
and skips that step gracefully if it is not installed.

Useful flags:

| Flag                  | Effect                                         |
| --------------------- | ---------------------------------------------- |
| `--skip-icons`        | Reuse `branding/icon.ico` from a previous run. |
| `--skip-pyinstaller`  | Just (re)compile the Inno Setup installer.     |
| `--skip-iscc`         | Stop after PyInstaller; skip the .exe wrap.    |

## Per-platform notes

| Platform | Bundle type                                  | Notes                                                  |
| -------- | -------------------------------------------- | ------------------------------------------------------ |
| Windows  | `installer/dist/DeltaSuite/DeltaSuite.exe`   | Inno Setup turns the folder into an installer EXE.     |
| macOS    | `installer/dist/DeltaSuite.app`              | The spec emits a `BUNDLE`; sign with codesign yourself.|
| Linux    | `installer/dist/DeltaSuite/DeltaSuite`       | Wrap into AppImage / deb / rpm with your tool of choice.|

## CI

`.github/workflows/release.yml` performs the same three steps on
GitHub-hosted runners every time a `v*` tag is pushed. Artifacts are
attached to the GitHub Release.
