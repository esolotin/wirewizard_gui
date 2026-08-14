# Windows release build

The build produces three x64 artifacts:

- `dist/WireWizardGUI/` — the PyInstaller `onedir` application used by the installer;
- `dist/WireWizardGUI-<version>-windows-x64-portable.zip` — the portable release;
- `dist/WireWizardGUI-<version>-windows-x64-setup.exe` — the per-user Inno Setup installer.

The build must run on 64-bit Windows. PyInstaller does not cross-compile Windows
executables from Linux.

## Prerequisites

1. Install a 64-bit CPython in the supported range `>=3.10.1,<3.15`. Python
   3.13 x64 is recommended and matches CI:

   ```powershell
   winget install --exact --id Python.Python.3.13 --architecture x64
   py -3.13 --version
   ```

   Close and reopen VS Code after installation. The presence of `py.exe` alone
   is not sufficient: the launcher must report an installed interpreter.

2. Prepare the project-local virtual environment. The helper chooses a
   supported 64-bit interpreter, creates `.venv`, installs the pinned
   dependencies and runs `pip check`:

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packaging\windows\prepare.ps1
   ```

3. By default, the build downloads the official Graphviz 15.1.0 x64 Windows
   ZIP, verifies its pinned SHA-256, and caches/extracts it below
   `packaging/windows`. To prepare an offline build manually, extract Graphviz
   into `packaging/windows/vendor/graphviz` so this file exists:

   ```text
   packaging/windows/vendor/graphviz/bin/dot.exe
   ```

   The archive's additional top-level directory is also detected automatically.
   Alternatively, pass any extracted Graphviz directory with `-GraphvizRoot`.

4. Install Inno Setup 7 or Inno Setup 6.3+ only if the Setup EXE is required.
   It is not needed for the portable ZIP:

   ```powershell
   winget install --exact --id JRSoftware.InnoSetup --source winget --interactive
   ```

   `ISCC.exe` may be on `PATH` or in its standard Program Files location.
   Visual Studio/Build Tools, CMake, Node.js, a system WireViz and a system
   Graphviz are not required.

In VS Code, `Ctrl+Shift+B` offers the portable and installer builds. Both
tasks run `prepare.ps1` first; neither task is configured as the default.

## Build

From the repository root:

```powershell
.\packaging\windows\build.ps1 -Version 0.1.0
```

`-Version` must match both `pyproject.toml` and `wirewizard_gui.metadata`.

Use an external Graphviz tree (and do not access the network):

```powershell
.\packaging\windows\build.ps1 -Version 0.1.0 -GraphvizRoot C:\Tools\Graphviz
```

Build only the onedir application and portable ZIP:

```powershell
.\packaging\windows\build.ps1 -Version 0.1.0 -SkipInstaller
```

The portable ZIP contains `portable.flag` beside `WireWizardGUI.exe`; the
installer source deliberately does not. The application uses this marker to
select portable data and log locations.

The script uses the shared PyInstaller spec and shared icon/version generators.
It validates the operating system, release version, 64-bit project virtual
environment, Python dependencies, Graphviz checksum and executable, PyInstaller
output, portable marker, bundled EPL-2.0 license, portable archive, and installer
output. It never modifies the system `PATH`; the bundled Graphviz directory is
added only to the application's process environment.
