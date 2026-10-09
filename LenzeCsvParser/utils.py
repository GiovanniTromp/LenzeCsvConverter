HEADER_HEADS = "\t//Index          Subindex            Length            Value"
HEADER_OUTLINE = "//-------------------------------------------------------------------------------------------------"

import csv
import os
import tempfile
import re
from decimal import Decimal, localcontext
from fractions import Fraction
from dataclasses import dataclass
import lenze_parser
import tkinter as tk
from tkinter import filedialog

from pathlib import Path
from models import LasalParameter, LenzeObjectParameter


@dataclass
class ReviewRow:
    line_number: int
    fields: list[str]
    parameter: LasalParameter | None
    error: str = ""


def review_parameter_fields(fields: list[str], line_number: int) -> ReviewRow:
    """Validate imports and edited cells through the same conversion path."""
    try:
        source = lenze_parser.parse_parameter_row(fields, line_number)
        return ReviewRow(line_number, fields, convert_to_lasal(source))
    except ValueError as exc:
        return ReviewRow(line_number, fields, None, str(exc))


def edit_parameter_fields(fields: list[str], column: int, value: str, line_number: int) -> ReviewRow:
    """Synchronize the scaled, raw and hexadecimal representations after editing."""
    updated = fields.copy()
    updated.extend([""] * max(0, 17 - len(updated)))
    updated[column] = value
    if column not in (2, 3, 4):
        return review_parameter_fields(updated, line_number)
    previous_value = updated[2].strip()
    # Invalid edits must not leave a stale number displayed as their equivalent.
    for dependent in (2, 3, 4):
        if dependent != column:
            updated[dependent] = ""
    try:
        kind = updated[5].strip().upper()
        bits = lenze_parser.get_byte_size(kind) * 8
        signed = kind.startswith("INTEGER_")
        lower = -(2 ** (bits - 1)) if signed else 0
        upper = 2 ** (bits - 1) - 1 if signed else 2**bits - 1
        factor_text = clean_factor(updated[16]).replace(",", ".") or "1"
        try:
            factor = Fraction(factor_text)
            if factor == 0:
                raise ValueError
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError("Display factor must be a nonzero number or fraction.") from exc
        def parse_hex(text):
            match = re.fullmatch(r"(?:0x)?([0-9a-f]+)h?", text.strip(), re.IGNORECASE)
            if not match:
                raise ValueError("Raw Hex Value must contain hexadecimal digits, optionally with 0x or h.")
            encoded = int(match[1], 16)
            if encoded >= 2**bits:
                raise ValueError(f"Hexadecimal value must fit the {bits}-bit parameter.")
            return encoded - 2**bits if signed and encoded >= 2**(bits - 1) else encoded

        if column == 3:
            raw = lenze_parser.parse_integer(value, "Raw Value", line_number)
        elif column == 4:
            raw = parse_hex(value)
        else:
            text = value.strip()
            try:
                displayed = Fraction(parse_hex(text)) if text.lower().startswith("0x") or text.lower().endswith("h") else Fraction(text.replace(",", "."))
            except (ValueError, ZeroDivisionError) as exc:
                raise ValueError("Value must contain a finite number or a valid hexadecimal value.") from exc
            unscaled = displayed / factor
            if unscaled.denominator != 1:
                raise ValueError("Value does not map to an exact integer Raw Value with this display factor.")
            raw = unscaled.numerator
        if not lower <= raw <= upper:
            raise ValueError(f"Raw Value must fit {kind} ({lower} to {upper}).")
        hex_value = f"0x{raw & (2**bits - 1):0{bits // 4}X}"
        if previous_value.lower().startswith("0x") and factor == 1:
            display = hex_value
        else:
            scaled = raw * factor
            denominator = scaled.denominator
            twos = fives = 0
            while denominator % 2 == 0:
                denominator //= 2
                twos += 1
            while denominator % 5 == 0:
                denominator //= 5
                fives += 1
            normalized = previous_value.replace(",", ".")
            old_places = len(normalized.split(".")[1]) if "." in normalized else 0
            places = max(old_places, twos, fives) if denominator == 1 else max(old_places, 12)
            with localcontext() as context:
                context.prec = max(50, len(str(abs(scaled.numerator))) + places + 5)
                display = format(Decimal(scaled.numerator) / Decimal(scaled.denominator), f".{places}f")
            if "," in previous_value and "." not in previous_value:
                display = display.replace(".", ",")
        updated[2], updated[3], updated[4] = display, str(raw), hex_value
    except ValueError as exc:
        return ReviewRow(line_number, updated, None, str(exc))
    return review_parameter_fields(updated, line_number)


def read_review_csv(file_path: Path) -> list[ReviewRow]:
    """Keep source rows available for review, including malformed rows."""
    rows = []
    with open(file_path, "r", encoding="utf-8-sig", newline="") as file:
        for header_line, line in enumerate(file, start=1):
            if line.strip().startswith("Index,"):
                break
        else:
            raise ValueError("Could not find parameter table header starting with 'Index,'")
        reader = csv.reader(file)
        for fields in reader:
            if not fields or not any(field.strip() for field in fields):
                continue
            line_number = header_line + reader.line_num
            rows.append(review_parameter_fields(fields, line_number))
    if not rows:
        raise ValueError("The CSV parameter table contains no rows.")
    return rows

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

    # Replace only after the complete table has been written successfully.
    destination = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent,
            prefix=".lasal_", suffix=".tmp", delete=False,
        ) as file:
            temporary = Path(file.name)
            file.write(HEADER_HEADS + "\n")
            for key in sorted(output_groups):
                for line in build_group_header(key):
                    file.write(line + "\n")
                for param in output_groups[key]:
                    file.write(str(param) + "\n")
                file.write("\n")
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

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
    if not 0 <= source.index <= 65535:
        raise ValueError("Index must be between 0 and 65535.")
    if not 0 <= source.subindex <= 255:
        raise ValueError("Subindex must be between 0 and 255.")
    # Value is display text (it can be hexadecimal or descriptive).
    # Only Raw Value is emitted into the LASAL table.
    byte_size = lenze_parser.get_byte_size(source.parameter_type)
    raw_text = str(source.raw_value).strip()
    if not raw_text:
        raise ValueError("Raw Value is empty; the LASAL table requires an integer.")
    try:
        raw_value = lenze_parser.parse_integer(raw_text, "Raw Value", 0)
    except ValueError as exc:
        raise ValueError("Raw Value is not an integer; it cannot be written as DINT.") from exc
    # Preserve the unsigned 32-bit literals accepted by the user's LASAL table.
    # Do not reinterpret high-bit bitfields as negative signed values.
    unsigned_32 = source.parameter_type in ("UNSIGNED_32", "BITFIELD_32")
    minimum = 0 if unsigned_32 else -(2**31)
    maximum = 2**32 - 1 if unsigned_32 else 2**31 - 1
    if not minimum <= raw_value <= maximum:
        raise ValueError(
            f"Raw Value {raw_value} is outside the supported range for "
            f"{source.parameter_type} ({minimum} to {maximum})."
        )
    g_number = lenze_parser.get_group_number(source.display_parameter)
    g_name = lenze_parser.get_group_name(group_number=g_number)

    return LasalParameter(
        index=source.index,
        subindex=source.subindex,
        byte_size=byte_size,
        raw_value=raw_value,
        comment=build_comment(source),
        group_number=g_number,
        group_name=g_name,
        source_display_parameter=source.display_parameter,
    )
