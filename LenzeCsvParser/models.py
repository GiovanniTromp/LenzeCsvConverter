from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

INDEX_WIDTH = 20
SUBINDEX_WIDTH = 20
BYTE_SIZE_WIDTH = 18
VALUE_WIDTH = 32

@dataclass(frozen=True)
class LenzeObjectParameter:
    """
    Represents one parameter row exported from a Lenze device.

    Source values that may contain descriptive text are kept as strings.
    Numeric configuration values are stored as Decimal to avoid floating-point
    rounding errors.
    """

    index: int
    subindex: int

    # Human-readable and raw values from Lenze
    value: str
    raw_value: int | str
    raw_hex_value: str

    parameter_type: str
    text: str
    unit: str

    minimum: str | None
    maximum: str | None
    factory_setting: str

    controller_inhibit: str
    access: str

    display_value: str
    display_value_factory_setting: str
    display_parameter: str
    display_factor: str
    extra_fields: list[str]

    def __str__(self) -> str:
        return (
            "LenzeObjectParameter(\n"
            f"  index                        = 0x{self.index:04X}\n"
            f"  subindex                     = {self.subindex}\n"
            f"  value                        = {self.value!r}\n"
            f"  raw_value                    = {self.raw_value}\n"
            f"  raw_hex_value                = {self.raw_hex_value!r}\n"
            f"  parameter_type               = {self.parameter_type!r}\n"
            f"  text                         = {self.text!r}\n"
            f"  unit                         = {self.unit!r}\n"
            f"  minimum                      = {self.minimum}\n"
            f"  maximum                      = {self.maximum}\n"
            f"  factory_setting              = {self.factory_setting}\n"
            f"  controller_inhibit           = {self.controller_inhibit}\n"
            f"  access                       = {self.access!r}\n"
            f"  display_value                = {self.display_value!r}\n"
            f"  display_value_factory_setting= "
            f"{self.display_value_factory_setting!r}\n"
            f"  display_parameter            = {self.display_parameter!r}\n"
            f"  display_factor               = {self.display_factor!r}\n"
            ")"
        )

@dataclass
class LasalParameter:
    """
    A class to represent the Lasal Output for in a Lasal Project TableClass
    """
    index: int
    subindex: int
    byte_size: int
    raw_value: int
    comment: str

    group_number: int
    group_name: str
    source_display_parameter: str

    def __str__(self) -> str:
        index_text = f"16#{self.index:04X}$UINT,"
        subindex_text = f"{self.subindex:03d}$USINT,"
        byte_size_text = f"{self.byte_size}$USINT,"
        raw_value_text = f"{self.raw_value}$DINT,"

        return (
            f" {index_text:<{INDEX_WIDTH}}"
            f"{subindex_text:<{SUBINDEX_WIDTH}}"
            f"{byte_size_text:<{BYTE_SIZE_WIDTH}}"
            f"{raw_value_text:<{VALUE_WIDTH}}"
            f"// {self.comment}"
        )

    def __repr__(self) -> str:
        return (
            "LasalParameter(\n"
            f"  index                        = 0x{self.index:04X}\n"
            f"  subindex                     = {self.subindex}\n"
            f"  byte_size                    = {self.byte_size}\n"
            f"  raw_value                    = {self.raw_value}\n"
            f"  comment                      = {self.comment!r}\n"
            f"  group_number                 = {self.group_number}\n"
            f"  group_name                   = {self.group_name!r}\n"
            f"  source_display_parameter     = {self.source_display_parameter!r}\n"
            ")"
        )