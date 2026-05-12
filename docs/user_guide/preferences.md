# Preferences

Open the dialog from **Edit → Preferences** (or `Ctrl+,` once a shortcut
is bound). All values are persisted to ``settings.toml`` next to the
user's other application data and survive restarts.

## General

| Setting             | Default | Notes                                                        |
| ------------------- | ------- | ------------------------------------------------------------ |
| Theme               | `auto`  | `light` / `dark` / `auto` (follows the OS colour scheme).    |
| Language            | `en`    | Spanish translation planned for a future release.            |
| Open last on startup| on      | Re-open the most recent project automatically.               |
| Show welcome screen | on      | Display the welcome page when no project is open.            |
| Check for updates   | off     | Reserved; not yet wired to a release feed.                   |

The theme switch is applied **immediately** when *Apply* or *OK* is
pressed; no restart is required.

## Kernels

| Setting                | Notes                                                           |
| ---------------------- | --------------------------------------------------------------- |
| Preferred bin folder   | Forces detection to use this exact `install_*/bin` folder.      |
| Additional search paths| `;`-separated list scanned **before** the automatic discovery.  |

## Runner

| Setting                       | Default |
| ----------------------------- | ------- |
| Default processes (parallel)  | 1       |
| Keep simulation log files     | on      |
| Switch to results tab on success | on   |

## Recent

| Setting                  | Default |
| ------------------------ | ------- |
| Maximum recent projects  | 12      |

The *Clear recent list* button removes every entry from
``recent_projects.toml``.
