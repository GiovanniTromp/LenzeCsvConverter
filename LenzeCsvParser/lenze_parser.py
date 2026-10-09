from typing import Optional
from decimal import Decimal, InvalidOperation
from models import LenzeObjectParameter

def clean_text(value: str | None) -> str:
    """
    Converts None to an empty string and removes surrounding whitespace.
    """
    return "" if value is None else value.strip()


def parse_integer(value: str, field_name: str, line_num: int) -> int:
    """
    Parses decimal and hexadecimal integers.

    Examples:
        "900"    -> 900
        "-12"    -> -12
        "0x2860" -> 10336
    """
    text = clean_text(value)

    if not text:
        raise ValueError(
            f"Line {line_num}: field {field_name!r} may not be empty.")

    try:
        return int(text, 16) if text.lower().startswith(("0x", "+0x", "-0x")) else int(text, 10)
    except ValueError as exc:
        raise ValueError(
            f"Line {line_num}: invalid integer in {field_name!r}: {value!r}") from exc


def parse_optional_decimal(value: str, field_name: str, line_num: int) -> Optional[Decimal]:
    """
    Parses an optional decimal number.

    Supports decimal commas:
        "90,0" -> Decimal("90.0")

    Empty values and question marks are treated as unavailable.
    """
    text = clean_text(value)

    if not text or text == "?":
        return None

    normalized = text.replace(",", ".")

    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(
            f"Line {line_num}: invalid decimal in "
            f"{field_name!r}: {value!r}" ) from exc


def get_byte_size(parameter_type: str) -> int:
    """
    Returns the byte size for a given parameter type.
    """
    type_to_size = {
        "INTEGER_8": 1,
        "UNSIGNED_8": 1,
        "BITFIELD_8": 1,
        "INTEGER_16": 2,
        "UNSIGNED_16": 2,
        "BITFIELD_16": 2,
        "INTEGER_32": 4,
        "UNSIGNED_32": 4,
        "BITFIELD_32": 4,
        "INTEGER_64": 8,
        "UNSIGNED_64": 8,
        "BITFIELD_64": 8,
    }

    if parameter_type in ("VISIBLE_STRING", "ARRAY"):
        raise ValueError(
            f"{parameter_type} is not supported by this integer LASAL table; "
            "it requires string or array serialization."
        )
    if parameter_type not in type_to_size:
        raise ValueError(f"Unknown parameter type: {parameter_type}")

    return type_to_size[parameter_type]


def get_group_number(display_parameter: str | None) -> int:
    """
    Extracts the group number from a display parameter string.
    """

    if not display_parameter:
        return 0

    import re
    match = re.search(r"P(\d)", display_parameter)
    if match:
        return int(match.group(1))
    return 0

def get_group_name(group_number: int) -> str:
    """
    Returns the group name based on the group number.
    """
    group_names = {
        0: "Group 0 - Unknown",
        1: "Group 1 - Diagnostics",
        2: "Group 2 - Basic setting",
        3: "Group 3 - Motor control",
        4: "Group 4 - I/O setting",
        5: "Group 5 - Network setting",
        6: "Group 6 - Process controller",
        7: "Group 7 - Additional functions",
        8: "Group 8 - Sequencer",
    }
    return group_names.get(group_number, f"Unknown Group [{group_number}]")


def get_display_string(options : list[str]) -> str | None:
    """
    Returns the first element in the list which starts with a 'P'
    """
    for opt in options:
        if opt.startswith('P'):
            return opt
    return None

def get_display_parameter_from_fields(
    fields: list[str],
) -> str | None:
    for field in fields:
        text = field.strip().upper()

        if text.startswith("P"):
            return text

    return None

def parse_parameter_row( row: list[str], line_num: int) -> LenzeObjectParameter:
    """
    Parses one Lenze CSV row into a LenzeObjectParameter.

    Expected column order:
        0  Index
        1  Subindex
        2  Value
        3  Raw Value
        4  Raw Hex Value
        5  Parameter Type
        6  Text
        7  Unit
        8  Min.
        9  Max.
        10 Factory Setting
        11 Controller Inhibit
        12 Access
        13 Display Value
        14 Display Value Factory Setting
        15 Display parameter
        16 Display factor
    """
    expected_column_count = 17  #Some rows have more than 17 colums

    if len(row) < expected_column_count:
        raise ValueError(
            f"Line {line_num}: expected at least "
            f"{expected_column_count} columns, received {len(row)}.\n"
            f"Row contents: {row!r}"
        )

    return LenzeObjectParameter(
        index=parse_integer(
            row[0],
            field_name="Index",
            line_num=line_num,
        ),
        subindex=parse_integer(
            row[1],
            field_name="Subindex",
            line_num=line_num,
        ),
        value=clean_text(row[2]),
        raw_value=clean_text(row[3]),
        raw_hex_value=clean_text(row[4]),
        parameter_type=clean_text(row[5]).upper(),
        text=clean_text(row[6]),
        unit=clean_text(row[7]),
        minimum=clean_text(row[8]),
        maximum=clean_text(row[9]),
        factory_setting=clean_text(row[10]),
        controller_inhibit=clean_text(row[11]),
        access=clean_text(row[12]).upper(),
        display_value=clean_text(row[13]),
        display_value_factory_setting=clean_text(row[14]),
        display_parameter=(clean_text(row[15]).upper()
            or get_display_parameter_from_fields(row[17:])
        ),
        display_factor=clean_text(row[16]),
        extra_fields = row[17:],
    )
