# Lenze CSV to LASAL Table Converter

A small Python utility that converts parameter exports from Lenze drive software
into table entries that can be used in a LASAL project.

The converter reads a Lenze CSV export, extracts the relevant parameter
information, determines the corresponding parameter group, converts Lenze data
types to their LASAL byte sizes, and generates formatted LASAL table rows.

## Features

- Reads Lenze parameter CSV exports
- Automatically locates the parameter table inside exports that contain metadata
  before the CSV header
- Supports parameter index and subindex values
- Groups parameters by Lenze display parameter/group
- Converts Lenze parameter types to LASAL byte sizes
- Uses raw parameter values for LASAL output
- Generates readable comments including units, ranges and scaling information
- Produces aligned LASAL table entries
- Supports selecting the input CSV through a file dialog
- Desktop GUI with drag-and-drop file selection
- Scrollable parameter review table with multiple-row removal
- Invalid rows highlighted red with validation messages
- Selectable output filename and folder
- Modern light and dark appearance with a theme toggle
- Keyboard shortcuts and button hover hints
- Next-error navigation with additive selection
- Double-click cell editing with immediate revalidation

## Usage

### Executable

1. Start `LenzeCsvParser/LenzeCsvConverter.exe`.
2. Drag a Lenze CSV file onto the window, or click **Choose CSV file…** to browse.
   Drop another CSV anywhere in the review window to replace the loaded file.
3. Review the parameter table. Invalid rows appear in red; select a row to see
   its validation message. Categories match the TXT groups and can be expanded
   or collapsed using their arrows. A category turns red if it contains invalid
   rows, and shows how many. Selecting and removing a category excludes all its
   parameters. Use Ctrl/Shift to select multiple rows, then click
   **Remove selected rows** or press Delete. **Select invalid rows** selects all
   rows that cannot be converted. Removing rows does not modify the source CSV.
4. Choose the output filename and folder using **Browse…**, or edit **Save to**.
   By default, output is saved alongside the CSV as `lasal_<input name>.txt`.
5. Click **Create LASAL TXT**. Export becomes available when at least one row
   remains and all remaining rows are valid. Existing output files require
   confirmation before replacement.

Validation checks Index, Subindex, Raw Value and Parameter Type. Raw Value must
be an integer. UNSIGNED_32 and BITFIELD_32 support 0 to 4294967295, preserving
the unsigned 32-bit literals used by the existing LASAL table. Other numeric
types use the signed 32-bit range (-2147483648 to 2147483647). Index and
Subindex must fit UINT and USINT. Value is display text and is not validated:
hexadecimal, descriptive or empty display values do not invalidate a numeric
Raw Value. Strings and arrays require different serialization and cannot be
exported by this integer table, even if their contents look numeric. Unsupported
types and malformed rows are marked red. Optional metadata can be empty.
LASAL output uses Raw Value with the existing `$DINT` suffix. Unsigned bitfields
above the signed DINT maximum retain their original positive values; they are
not rewritten or truncated.

#### Optional
If you want to verify the executable run:
```powershell
Get-FileHash .\LenzeCsvParser\LenzeCsvConverter.exe -Algorithm SHA256
```
#### SHA-256
  See the hash of your local build with the command above; rebuilding changes it.

### Python

Run:

```powershell
python -m pip install -r LenzeCsvParser/requirements.txt
python LenzeCsvParser/main.py
```

The desktop window will open with the drag-and-drop area and file picker.

Example input

A Lenze CSV export may contain rows such as:

Index,Subindex,Value,Raw Value,Raw Hex Value,Parameter Type,Text,Unit,Min.,Max.,Factory Setting,Controller Inhibit,Access,Display Value,Display Value Factory Setting,Display parameter,Display factor
0xBC44,4,2600,2600,0x9896,UNSIGNED_16,Motor parameters: Rated speed,rpm,50,50000,1450,False,RW,,,P320:004,,
0xBC44,6,"0,25",25,0x0219,UNSIGNED_16,Motor parameters: Rated power,kW,"0,00","655,35",?,False,RW,,,P320:006,"1/100"
0xBC44,7,400,400,0x0111,UNSIGNED_16,Motor parameters: Rated voltage,V,0,65535,?,False,RW,,,P320:007,,

The Lenze export may contain additional metadata before the CSV header. The
converter searches for the parameter header automatically, so the parameter
table does not need to start on a fixed line. The values above are random.

Example output
//-------------------------------------------------------------------------------------------------
// Group 3: Motor control
//-------------------------------------------------------------------------------------------------
 16#BC44$UINT,       004$USINT,          2$USINT,          2600$DINT,                     // Motor parameters: Rated speed in rpm (50 - 50000 rpm)
 16#BC44$UINT,       006$USINT,          2$USINT,          25$DINT,                       // Motor parameters: Rated power in 1/100 kW (0.00 - 655.35 kW)
 16#BC44$UINT,       007$USINT,          2$USINT,          400$DINT,                      // Motor parameters: Rated voltage in V (0 - 65535 V)

## Notes
Not every Lenze parameter can currently be converted automatically.

Some parameters:

- do not have a display parameter
- contain non-numeric or device-specific values
- use special data types
- may require manual verification

Unsupported parameters should be skipped or reported instead of being silently
converted incorrectly.

## Building the executable

From the repository root, install dependencies and build:

```powershell
python -m pip install -r LenzeCsvParser/requirements.txt
./build.ps1
```

For a virtual environment, pass its interpreter to the build script:

```powershell
./build.ps1 -Python ./.venv/Scripts/python.exe
```

The build includes the native drag-and-drop libraries and runs without a console
window. The executable is created in `dist/LenzeCsvConverter.exe` and copied to
`LenzeCsvParser/LenzeCsvConverter.exe`. Python is not needed to run the EXE.

Run the conversion and GUI workflow tests:

```powershell
cd LenzeCsvParser
python -m unittest -v test_converter
```

## Keyboard shortcuts and editing

The fast cleanup workflow is **Ctrl+E → Delete → Ctrl+S**: select all invalid
rows, remove them from the output, then create the LASAL TXT.

| Shortcut | Action |
| --- | --- |
| Ctrl+O | Open another CSV in the file browser |
| Ctrl+E | Select every invalid parameter row, including rows inside collapsed categories |
| Delete | Remove selected rows or categories from the output |
| Ctrl+S | Export the remaining valid parameters to the selected TXT location |
| F4 | Jump to and select the next invalid row; wrap after the last error |
| Shift+F4 or Ctrl+F4 | Keep the current selection and add the next invalid row; do not select intervening rows |
| Shift+click or Ctrl+click on **Next error** | Add the next invalid row to the selection |
| Enter while editing a cell | Apply the edit and revalidate the row |
| Escape while editing a cell | Cancel the edit |

Hover over a button to see its action and shortcut. Delete retains its normal
text-editing behavior when the save-path field or a cell editor has focus.

Double-click a parameter cell to edit its source value. Applying an edit or
leaving the cell updates validation, category highlighting, counts, and export
availability immediately. CSV line numbers, validation messages, and category
headings are generated and cannot be edited. Editing **Display parameter** can
move the row to another category. Edits affect the generated TXT only; the
source CSV stays unchanged.

Editing **Value**, **Raw Value**, or **Raw Hex Value** updates all three cells. Hexadecimal
output uses the parameter's byte width and two's complement for negative signed
values. Value uses `Raw Value × Display factor` (or factor 1 when blank), retaining
decimal commas and hexadecimal display formatting where applicable. Repeating
fractional results are displayed to at least 12 decimal places; the exported raw
integer remains exact. Invalid raw edits clear the derived cells and highlight
the row rather than showing stale equivalents. Value edits divide by the display
factor and must produce an exact integer; values are never silently rounded.
Raw Hex Value accepts hexadecimal digits with an optional `0x` prefix or `h`
suffix, and decodes signed two's-complement values using the parameter's byte
width. Both types of edit update the Raw Value used in the exported TXT.

Use **Dark mode / Light mode** in the header to change appearance. The loaded
rows, edits, removals, category expansion, selection, and output path are
preserved when switching themes. The last selected theme is saved automatically
in `%LOCALAPPDATA%/LenzeCsvConverter/settings.json` and restored on startup, even
if the EXE is moved or replaced. Missing or invalid preferences default to light
mode. File dialogs and message boxes use the Windows appearance.

## Disclaimer

Generated parameter tables should be verified before use on real hardware.
Incorrect drive parameters can result in unexpected machine behaviour.

This project is not affiliated with or endorsed by Lenze or SIGMATEK.
