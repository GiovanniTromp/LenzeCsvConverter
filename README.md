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

## Usage

### Executable

1. Start `LenzeCsvParser.exe`.
2. Select a Lenze parameter CSV export when prompted.
3. The application converts the supported parameters.
4. The generated LASAL table file is written to the configured output location.

### Python

Run:

```powershell
python main.py
```

A file selection dialog will open. Select the Lenze CSV file that should be
converted.

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

Install PyInstaller:

`pip install pyinstaller`

Build:

`pyinstaller --onefile main.py`

The resulting executable can be found in:

dist/

## Disclaimer

Generated parameter tables should be verified before use on real hardware.
Incorrect drive parameters can result in unexpected machine behaviour.

This project is not affiliated with or endorsed by Lenze or SIGMATEK.
