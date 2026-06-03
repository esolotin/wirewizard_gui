# WireWizardGUI
This is GUI wrapper for WireViz project. You can create cable assemblies drawings using simple GUI with standard controls. You can preview result, save/load project, import/export YAML files in WireViz Syntax, and finally call WireViz to get resulting html drawing and bom.

Desktop-prototype editor for WireViz in Python + PySide6.

## What it can do
- Create and edit:
 - connectors
 - cables / bundles
 - ferrules
 - connection rows
- Show the final YAML for WireViz
- Try to render an SVG preview using the locally installed `wireviz`
- Save and load the **GUI project** in JSON
- Import an existing **WireViz YAML**
- Export the current project to **WireViz YAML**
- Check for common errors in connections:
 - unknown elements
 - incorrect connector/cable sequence
 - pin/wire out of range
 - shield `s` for cable without shield
 - mismatching lengths of parallel groups `[1,2]`

## What remains simplified
This is no longer a bare MVP, but it is not yet a complete WireViz visual CAD editor.

So far connections are edited by route strings of the form:
`X1:1 -> W1:1 -> F1 -> W2:1 -> X2:1`

There is a daisy-chain wizard, but there is no full-fledged tabular pin-mapping editor yet.

## Installation
Python 3.9+ is required.

To run on Win10:
in CMD:

1) cd <ProjectPath>\wirewizard_gui
2) python -m venv .venv
3) .venv\Scripts\activate.bat
4) python -m pip install -r requirements.txt
5) install Graphviz from here:  https://graphviz.org/download/
6) cd..
7) python -m wirewizard_gui.app

Further runs don't require rebuilding virtual environment.
Just do:
1) cd <ProjectPath>\wirewizard_gui
2) .venv\Scripts\activate.bat
3) python -m wirewizard_gui.app
