# WatchMaker-PC

A desktop application for creating and editing WatchMaker watch faces, built with PyQt5.

## Features

### Current Version

#### Lua Script Editor (New)
A fully-featured Lua script editor for WatchMaker watch face scripting:

- **Syntax Highlighting**: Full Lua syntax highlighting with dark theme support
- **WatchMaker API Autocomplete**: Built-in autocomplete for WatchMaker-specific functions:
  - `wm_schedule`, `wm_action`, `wm_tag`, `wm_vibrate`, `wm_sfx`, etc.
  - Callback functions: `on_hour`, `on_minute`, `on_second`, `on_millisecond`, etc.
- **Tag Autocomplete**: Type `{` to trigger WatchMaker tag autocomplete with descriptions
  - Date/Time tags, Battery tags, Weather tags, Health & Fitness tags, and more
- **Syntax Checking**: Real-time Lua syntax validation using luaparser
- **Code Formatting**: Basic Lua code formatting with proper indentation
- **Undo/Redo Support**: Full undo/redo history
- **API Reference Panel**: Quick reference for WatchMaker Lua API with examples
- **Output Panel**: Real-time feedback for syntax errors and warnings

**Note**: Currently, the Lua editor can only be launched via `script_view.py` directly. Integration with the main application will be completed in the next version.

#### Main Application
- Frameless window with custom title bar
- Dark theme UI
- Side navigation bar
- "My Watches" view for managing watch faces

### Planned Features (Next Version)
- Integration of Lua Script Editor with the main application
- Component button functionality implementation
- Watch face preview

## Requirements

- Python 3.8+
- PyQt5
- QScintilla
- luaparser (optional, for enhanced syntax checking)

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   ```
3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`
4. Install dependencies:
   ```bash
   pip install PyQt5 QScintilla luaparser
   ```

## Usage

### Running the Main Application
```bash
python app.py
```

### Running the Lua Script Editor (Standalone)
```bash
python script_view.py
```

## Keyboard Shortcuts (Lua Editor)

| Shortcut | Action |
|----------|--------|
| Ctrl+Z | Undo |
| Ctrl+Y / Ctrl+Shift+Z | Redo |
| Ctrl+S | Apply/Save script |
| Ctrl+Shift+C | Check syntax |
| Ctrl+Shift+F | Format code |
| Escape | Return to previous view |

## Project Structure

```
pre_watchmaker/
├── app.py                  # Main application entry point
├── script_view.py          # Lua Script Editor
├── lua_syntax_checker.py   # Lua syntax validation
├── edit_view.py            # Watch face editing view
├── my_watches_view.py      # Watch collection view
├── side_bar.py             # Side navigation
├── menu.py                 # Menu bar
├── tip_bar.py              # Status/tip bar
├── common.py               # Common utilities
├── components/             # UI components
├── style/                  # QSS stylesheets
│   ├── app.qss
│   └── script_view.qss
├── img/                    # Image assets
├── font/                   # Font files
└── saves/                  # Saved watch faces
```

## License

This project is currently in development.

## Changelog

### v0.2.0 (Current)
- Added Lua Script Editor with full syntax highlighting
- Implemented WatchMaker API autocomplete
- Added tag autocomplete system with descriptions
- Integrated luaparser-based syntax checking
- Added code formatting functionality
- Implemented undo/redo support
- Added API reference panel

### v0.1.0
- Initial release with basic UI framework
- Implemented frameless window with custom controls
- Added dark theme
- Created basic navigation structure
