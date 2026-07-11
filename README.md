# WatchMaker-PC

A desktop application for creating and editing WatchMaker watch faces, built with PyQt6.

## Features

### Current Version (v0.4.0)

#### Canvas Layer Types
- **Fully Rendered Layers**: `ImageLayer`, `ImageCondLayer` (sprite/conditional images), `ShapeLayer` (square/circle/triangle/pentagon/hexagon/star/heart), `RoundedRectangleLayer`, `CurvedTextLayer`, `TextRingLayer` (Numbers dial), `MarkerLayer` (freeform marker dials), `TachymeterLayer`, and `SlideshowLayer` all now render live on the canvas instead of falling back to a generic placeholder
- **Tachymeter Layer**: real tachymeter speed-scale geometry (`angle = 21600 / speed`), major/minor tick marks with independent size/shape presets (Tiny–XLarge, Circle, Triangle), curved title text in the scale's start/end gap, and a `Custom speeds` field for user-defined speed lists
- **Slideshow Layer**: multi-photo cycling driven by a new per-second `LayerMixin.tick()` hook, a `Photo` field that now accepts a comma-separated list of paths (append-on-browse multi-file picker), and `Photo clip` (None/Circle/Corner 1/Corner 2) with crop-fill scaling so photo content is never distorted
- **Schema Cleanup**: `Display` mode, `Shape`, `Ring type`, and other previously single-option placeholder enums are now fully populated across layer types

#### Lua Sandbox & Base Script Support
- **Execution Sandbox**: dangerous globals (`io`, `os`, `debug`, `package`, `require`, the `python` bridge, etc.) are stripped before any user Lua runs
- **Timeout Watchdog**: a `debug.sethook`-based deadline aborts runaway/infinite Lua expressions and base-script extraction within a bounded time, returning a safe fallback instead of hanging the editor
- **Base Script Variables**: `var_*` globals and `tween` names defined in the Lua base script are now extracted and usable directly in per-field expressions
- **Editor Autocomplete**: added `tweens.*`, `wm_action()` string-argument, and `wm_anim_set()` second-argument completion

#### Watch Face Editor
- **Canvas**: Circular watch face preview with real-time layer rendering
- **Layer Management**: Object Explorer panel for viewing and reordering layers (Z-order drag)
- **Attribute Panel**: Per-layer property editing with field type-aware widgets (string, number, color, boolean, dropdown, font, file)
- **Day/Night Mode Toggle**: Live preview switching between day and night watch face modes
- **Undo/Redo**: Full undo/redo stack (`QUndoStack`) covering attribute changes and layer moves

#### Multi-Select & Group
- **Multi-select**: Click to select individual layers; Shift+Click or rubber-band drag to select multiple layers simultaneously
- **Multi-select Overlay**: Each selected item shows a highlight border; a union bounding box with a move handle appears at the top center for group dragging
- **Proportional Resize**: Shift+corner handle drag for proportional scaling on single-layer selection
- **Group Layer**: Drag one or more layers onto the Layer Picker panel to create a `CanvasGroupLayer`; group items can be collapsed/expanded in the Object Explorer
- **Rotation Zone**: 10 px outer ring beyond each corner handle for rotation gestures (Figma-style)

#### Lua Script Panel ↔ Watch Edit Area Integration
- **Expression Mode**: Each numeric/string attribute field opens a `LuaScriptPanel` in expression mode (`return <expr>`), with live evaluation updating the canvas in real time
- **Tag Autocomplete**: Type `{` in the Lua editor to trigger WatchMaker tag suggestions with descriptions
- **API Autocomplete**: ≥ 2 characters triggers WatchMaker API / easing / Lua keyword suggestions; Tab to confirm, Escape to dismiss
- **Debounce Apply**: Script changes are applied 400 ms after the last keystroke; `Ctrl+Enter` applies immediately
- **Periodic Refresh**: The editor re-evaluates time/date tags every second so the preview stays current
- **Syntax Panel**: Real-time Lua syntax validation with error highlighting in the editor gutter

#### Lua Script Editor
- **Syntax Highlighting**: Full Lua syntax highlighting with dark theme
- **WatchMaker API Autocomplete**: `wm_schedule`, `wm_action`, `wm_tag`, `wm_vibrate`, `wm_sfx`, and all callback functions
- **Tag Autocomplete**: Date/Time, Battery, Weather, Health & Fitness tags, and more
- **Output Panel**: Real-time syntax error and warning feedback

#### Panel Layout System
- **Tabbed Split Panels**: VS Code-style draggable tab splitting and merging (`TabWidgetManager`)
- **Recently Closed Tabs**: Restore up to 20 recently closed tabs from View > Recently Closed Tabs
- **Flow Layout**: Attribute fields of the same type share rows; group-type fields occupy a full row (`AttrFlowLayout`)

#### My Watches
- Browse, create, rename, and delete saved watch faces
- Thumbnail preview cards with last-modified timestamps

---

### Planned Features
- **3D layer rendering** (`layer3D`/Photo Cube, `model3d`) — next release's main focus
- Animation attribute support
- Full WatchMaker `.pxml` import/export
- Watch face preview on-device sync

## Requirements

- Python 3.10+
- PyQt6 ≥ 6.11
- lupa ≥ 2.8 (Lua runtime for tag evaluation)
- Pillow (image processing)
- pytest + pytest-qt (development/testing)
- `luaparser` with `antlr4` *(optional — full ANTLR4 Lua syntax checking; falls back to bracket/block balance check if not installed)*

## Installation

1. Clone the repository.
2. Create and activate a virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   pip install PyQt6 lupa Pillow pytest pytest-qt
   # Optional: full Lua syntax checking
   pip install luaparser
   ```
4. Run the application:
   ```powershell
   python main.py
   ```

## Running Tests

```powershell
# All tests
python -m pytest all_test/

# Single file
python -m pytest all_test/test_main.py

# Single class or function
python -m pytest all_test/test_main.py::TestTitleBar::test_height
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Enter` | Apply Lua script immediately |
| `Ctrl+Z` | Undo |
| `Ctrl+Y` / `Ctrl+Shift+Z` | Redo |
| `Shift+Click` | Add layer to multi-selection |
| `Tab` | Confirm autocomplete suggestion |
| `Escape` | Dismiss autocomplete |

## Project Structure

```
pre_watchmaker/
├── main.py               # Entry point: MainWindow, TitleBar, platform scale filter
├── special_ui.py         # FlowLayout, Tab/TabWidget/TabWidgetManager, WidgetManager, DropOverlay, FontManager
├── special_ux.py         # DragManager, @drag_data decorator, @accept_drop decorator
├── watch_cabinet.py      # WatchCabinet (My Watches page), WatchCard, AddWatchCard
├── edit_watch.py         # Watch face edit page: PanelWidgetManager, four panels, attribute field cards
├── lua_script.py         # Lua script panel: LuaScriptPanel, LuaEditorPanel, SyntaxPanel, LuaHighlighter
├── crypter.py            # .pxml file decryptor (WatchMaker save format)
├── components/
│   ├── common.py         # Field type schemas for each layer type
│   ├── attributes.py     # Default values for each layer type
│   ├── utils.py          # summon_components(), Lua eval system (sandbox + timeout), Tag system, base script vars
│   └── layers.py         # LayerMixin, LayeredGraphicsScene, TextLayer/ImageLayer/ImageCondLayer/ShapeLayer/
│                         #   RoundedRectangleLayer/CurvedTextLayer/TextRingLayer/MarkerLayer/TachymeterLayer/
│                         #   SlideshowLayer, LayerEllipseItem, CanvasGroupLayer,
│                         #   _SelectionOverlay, _MultiSelectOverlay
├── lua/                  # wm_api.lua (WatchMaker API stubs), wm_sandbox.lua (dangerous-global blocklist)
├── saves/                # Saved watch faces (sort.json + preview .png per watch)
├── img/
│   ├── icon/             # TabWidgetManager DropOverlay direction icons
│   ├── my_watches/       # WatchCabinet toolbar icons
│   └── edit/             # Watch edit area icons (eye, day/night mode)
├── img/recolor.py        # Utility script for recoloring single-color images
└── all_test/             # All tests (pytest + pytest-qt)
```

## License

This project is currently in development.

## Changelog

### v0.4.0
- **Canvas Rendering for Stub Layer Types**: `ImageLayer`, `ImageCondLayer`, `ShapeLayer`, `RoundedRectangleLayer`, `CurvedTextLayer`, `TextRingLayer`, `MarkerLayer`, `TachymeterLayer`, and `SlideshowLayer` all gained real canvas rendering (previously schema-only or a generic placeholder circle)
- **Tachymeter Layer**: non-linear speed-scale geometry, major/minor tick marks with size/shape presets, curved title text, `Custom speeds` field
- **Slideshow Layer**: multi-photo cycling via a new `LayerMixin.tick()` per-second hook, multi-file `Photo` field (comma-separated, append-on-browse), `Photo clip` shapes (Circle/Corner 1/Corner 2) with crop-fill scaling
- **Schema Enum Completion**: `Display`, `Shape`, `Ring type`, `Major/Minor markers`, and other previously single-option stub fields now expose their full real option sets
- **Lua Sandbox**: blocks dangerous globals (`io`/`os`/`debug`/`package`/`require`/Python bridge) before running any user Lua
- **Lua Timeout Watchdog**: `debug.sethook`-based deadline aborts runaway/infinite Lua expressions and base-script extraction instead of hanging the editor
- **Base Script Variables**: `var_*` globals and `tween` names from the Lua base script are extracted and usable in per-field expressions
- **Lua Editor Autocomplete**: added `tweens.*`, `wm_action()` string-argument, and `wm_anim_set()` second-argument completion
- **Bug Fixes**: Lua expression text no longer silently discarded in numeric fields; Watch Setting vs. per-type Template attribute edits now route to distinct undo commands; day/night mode toggle now forces a full canvas refresh
- **Test Infrastructure**: added `test_lua_sandbox.py`/`test_lua_timeout.py`; shared `conftest.py` fixture disables the periodic refresh timer to eliminate test flakiness

### v0.3.7
- **Refactored to PyQt6**: Migrated the entire codebase from PyQt5 to PyQt6; updated all imports, signal/slot syntax, enum namespaces, and stylesheet handling accordingly
- **Multi-select & Group**: Implemented rubber-band and Shift+Click multi-selection; `_MultiSelectOverlay` shows per-item highlight borders and a union bounding-box move handle; `CanvasGroupLayer` groups items with collapsible Object Explorer nodes
- **Lua Panel ↔ Edit Area Integration**: Attribute fields open `LuaScriptPanel` in expression mode; canvas updates in real time as Lua expressions evaluate; debounce apply (400 ms) and `Ctrl+Enter` instant apply
- **Undo/Redo System**: `QUndoStack`-based undo/redo covering attribute changes (`_AttrChangeCommand`) and multi-layer moves (`_MoveMultiCommand`)
- **Selection Overlay**: Figma-style 8-handle resize overlay with rotation zone on corner handles; Shift+drag for proportional scale

### v0.3.0
- Integrated Lua Script Editor with the main application
- Established base component architecture for all UI elements
- Implemented component base classes and inheritance hierarchy
- Standardized component communication patterns
- Completed common attributes for all layer types
- Implemented partial attributes for TextLayer and ImageLayer

### v0.2.0
- Added Lua Script Editor with full syntax highlighting
- Implemented WatchMaker API autocomplete
- Added tag autocomplete system with descriptions
- Integrated luaparser-based syntax checking
- Added code formatting functionality
- Implemented undo/redo support for the Lua editor
- Added API reference panel

### v0.1.0
- Initial release with basic UI framework
- Implemented frameless window with custom controls
- Added dark theme
- Created basic navigation structure
