HEADER_HEADS = "\t//Index          Subindex            Length            Value"
HEADER_OUTLINE = "//-------------------------------------------------------------------------------------------------"

import csv
import lenze_parser
import tkinter as tk
from tkinter import filedialog

from pathlib import Path
from models import LasalParameter, LenzeObjectParameter

def select_input_file() -> Path | None:
    root = tk.Tk()
    root.withdraw()

    chosenOne =filedialog.askopenfilename(
        title="Select a Lenze Csv file",
        filetypes=[("Csv Files", "*.csv"),],
    )

    root.destroy()

    if not chosenOne:
        return None

    return Path(chosenOne)

def read_parameter_csv(file_path: str) -> list[LenzeObjectParameter]:
    """
    Reads a csv file from `file_path` and returns a list of LenzeObjectParameter

    """

    parameters = []
    with open(file_path, "r", encoding="utf-8-sig", newline="") as file:

        # Search for the start of the parameter table; skip Metadata
        for line_num, line in enumerate(file, start=1):
            if line.strip().startswith("Index,"):
                print(f"Found parameter table at line {line_num}")
                break
        else:
            raise ValueError(
                "Could not find parameter table header starting with 'Index,'"
            )

        reader = csv.reader(file)

        for row in reader:
            line_num += 1

            if not row:
                continue

            parameter = lenze_parser.parse_parameter_row(
                row,
                line_num,
            )

            parameters.append(parameter)

    return parameters

def write_output(path: str, output: str) -> None:
    """
    Writes the given output string to a file at the specified path.
    """
    # print(f"Writing output to {path}")
    with open(path, mode='a', encoding='utf-8') as file:
        file.write(output)
        file.write('\n')  # Ensure each output is on a new line

def build_group_header(group: str)-> list[str]:
    header = []
    header.append(HEADER_OUTLINE)
    header.append(f"//\t{group}")
    header.append(HEADER_OUTLINE)

    return header

def clear_output_file(path: str) -> None:
    with open(path, mode='w', encoding='utf-8'):
        pass

def build_output_file(
        output_groups: dict[ str, list[LasalParameter]],
        path:str
    ):

    clear_output_file(path)

    write_output(path, HEADER_HEADS)

    for key in sorted(output_groups):
        header = build_group_header(key)
        for line in header:
            write_output(path, line)
        for param in output_groups[key]:
            write_output(path, str(param))
        write_output(path, "")

def clean_factor(value: str | None) -> str:
    """
    Cleans values such as:
        '"1/100"'
        '\"\"\"1/100\"\"\"'
        '1/100'

    into:
        '1/100'
    """
    if not value:
        return ""

    return value.strip().strip('"').strip()


def clean_number_text(value: str | None) -> str:
    """
    Makes numeric text more readable without forcing it to be numeric.

    Examples:
        '0,00'       -> '0.00'
        '125,0000'   -> '125.0000'
        '0:00:00:00' -> '0:00:00:00'
    """
    if not value:
        return ""

    return value.strip().replace(",", ".")

def build_comment(parameter: LenzeObjectParameter) -> str:
    """
    Builds a readable LASAL table comment from a Lenze parameter.

    Example:
        Motor parameters: Rated power in 1/100 kW (0.00 - 655.35 kW)
    """

    comment = parameter.text.strip()

    factor = clean_factor(parameter.display_factor)
    minimum = clean_number_text(parameter.minimum)
    maximum = clean_number_text(parameter.maximum)
    unit = parameter.unit.strip()

    # Add scaling information.
    if factor and factor != "1":
        if unit:
            comment += f" in {factor} {unit}"
        else:
            comment += f" in {factor}"

    elif unit:
        comment += f" in {unit}"

    # Add range information.
    if minimum and maximum:
        comment += f" ({minimum} - {maximum}"

        if unit:
            comment += f" {unit}"

        comment += ")"

    return comment

def convert_to_lasal( source: LenzeObjectParameter) -> LasalParameter:
    g_number = lenze_parser.get_group_number(source.display_parameter)
    g_name = lenze_parser.get_group_name(group_number=g_number)

    return LasalParameter(
        index=source.index,
        subindex=source.subindex,
        byte_size=lenze_parser.get_byte_size(source.parameter_type),
        raw_value=source.raw_value,
        comment=build_comment(source),
        group_number=g_number,
        group_name=g_name,
        source_display_parameter=source.display_parameter,
    )
