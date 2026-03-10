# Building the Cookie Clicker .exe with PyInstaller

## 1. Install dependencies

```bash
cd cookie_clicker_game
pip install pygame pyinstaller
```

## 2. (Optional) Add fonts

- **Roboto Bold** (recommended): Download from [Google Fonts](https://fonts.google.com/specimen/Roboto). Place `Roboto-Bold.ttf` in `cookie_clicker_game/fonts/`.
- **Press Start 2P** (pixel style): Download from [Google Fonts](https://fonts.google.com/specimen/Press+Start+2P). Place `PressStart2P-Regular.ttf` in `fonts/`.
- If custom fonts are missing, the game uses system bold fonts.

## 3. Build a single .exe

From the `cookie_clicker_game` folder (same folder as `cookie_clicker.py`):

```bash
pyinstaller --onefile --windowed --name "CookieClicker" --add-data "fonts;fonts" cookie_clicker.py
```

**Windows (if `;` doesn’t work for `--add-data`):**

```bash
pyinstaller --onefile --windowed --name "CookieClicker" --add-data "fonts;fonts" cookie_clicker.py
```

If your PyInstaller expects a colon for the path separator:

```bash
pyinstaller --onefile --windowed --name "CookieClicker" --add-data "fonts:fonts" cookie_clicker.py
```

**Without bundling the fonts folder** (game will use system font if the file isn’t found):

```bash
pyinstaller --onefile --windowed --name "CookieClicker" cookie_clicker.py
```

## 4. Output

- The executable is created at: `dist/CookieClicker.exe`
- Run `dist/CookieClicker.exe`; the game will create/read `cookie_save.json` in the same directory as the .exe.

## 5. Save file location

- **When running from source:** `cookie_save.json` is in the folder above the script (e.g. `C:\Users\Tony\cookie_save.json` if you run from `C:\Users\Tony`).
- **When running the .exe:** `cookie_save.json` is next to the .exe (e.g. `dist/cookie_save.json`).
