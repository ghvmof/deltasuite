# Editing the model setup

The **Setup** tab in the DeltaSuite workspace is a lightweight key/value
editor for the project's main configuration file. Two formats are
supported:

| Extension | Source kernel | Notes                                  |
| --------- | ------------- | -------------------------------------- |
| `.mdu`    | D-Flow FM     | INI-style, `[Section]` headers         |
| `.mdf`    | Delft3D 4     | Flat key/value, `#…#` strings, comments|

The editor reads the file with a lossless parser: order, blank lines,
inline comments and unrecognised lines are preserved on save. Every
value is exposed as a single-line text field; the inline comment (if
any) is shown as a hint next to it.

## Workflow

1. Open a project (e.g. `File → Browse Models in Folder…`).
2. The Setup tab is auto-populated from `meta.main_input_file`
   (typically the `.mdf` for Delft3D 4 or the `.mdu` for D-Flow FM).
3. Edit values in place. The **Save** button is disabled while the
   document has no pending changes.
4. **Reload** discards every local edit and re-reads the file from disk
   (asks for confirmation if the editor is dirty).

## Programmatic access

```python
from deltasuite.core import ConfigDocument

doc = ConfigDocument.load("case.mdu")
doc.set("Numerics", "CFLMax", "0.95")
doc.save()
```
