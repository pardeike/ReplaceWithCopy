# Replace With Copy

Replace a whole selection of objects with a clean copy of a template in one click.  
The add-on keeps parents, collections, visibility, modifiers, and even Geometry Nodes object links intact so the new object drops right into the same place the old one occupied.

## Highlights
- **Template-first workflow** – pick the template first, then Shift-click the targets; the menu entry keeps you informed about the current mode.
- **Unique or linked data** – by default each replacement gets its own mesh/data block; hold <kbd>Alt</kbd> while choosing the menu item to keep the copy linked to the template instead.
- **Reference remapping** – boolean cutters, constraints, node inputs, and other object references automatically point to the freshly created copy.
- **Hierarchy aware** – parents, bone parenting, collection membership, visibility flags, selection state, and child objects are all preserved.
- **Undo friendly** – every run is a single undo step so you can experiment freely.

## How to Use
1. In Object Mode select the template object first.
2. Shift-click one or more target objects that should be replaced.
3. Open `Object ▸ Replace With Copy` in the 3D Viewport menu.
4. (Optional) Hold <kbd>Alt</kbd> while opening or activating the menu entry to perform a linked-data replacement instead of creating unique copies.

The menu text updates to tell you exactly what will happen, e.g. *“Replace 3 objects with a copy of Hull”* or *“…with a reference to Hull”*.

## Operator Options
After running the operator (or from the Adjust Last Operation panel) you can fine-tune:

- **Make Unique Mesh/Data** – keep enabled for independent meshes, or disable to share the template’s data. Holding <kbd>Alt</kbd> in the menu toggles this before execution.
- **Active Is Template** – advanced mode that uses the active (last selected) object as the template, useful if you work “targets first, template last”.
- **Also Match Scale** – when enabled, the new copy inherits each target’s scale instead of the template’s scale.

These settings are stored per Blender session, so the next run picks up where you left off.

## Installation
- **Blender Extensions:** search for “Replace With Copy” inside the official extension browser and click *Install*.
- **Manual install:** download the repository as a `.zip`, then use `Edit ▸ Preferences ▸ Add-ons ▸ Install…` and choose the archive.

The add-on targets Blender 4.2+ and is released under the GPLv3 license.

## Feedback & Contributions
Bug reports, ideas, and pull requests are welcome. Open an issue on the GitHub repository or reach out to the maintainer listed in the manifest. Happy blending!
