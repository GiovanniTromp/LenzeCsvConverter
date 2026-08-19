import lenze_parser

from pathlib import Path
from utils import (
    select_input_file,
    read_parameter_csv,
    convert_to_lasal,
    build_output_file
)
from models import LasalParameter

# ---------------------------------------------------
# Configuration
# ---------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

# from debug import (
#     GREEN, BLUE, RESET
# )

def main() -> None:
    print("Navigate to an input file.")
    input_path = select_input_file() 
    output_path = input_path.with_name(
        "lasal_" + input_path.stem + ".txt"
    )
    lenze_parameters = read_parameter_csv(input_path)

    lasal_params: list[LasalParameter] = []
    for param in lenze_parameters:
        lasparam = convert_to_lasal(param)
        lasal_params.append(lasparam)

    output_groups : dict[
        str,
        list[LasalParameter],
    ] = {}

    for p in lasal_params:
        key = p.group_name
        if key not in output_groups:
            output_groups[key] = []

        output_groups[key].append(p)

    build_output_file(output_groups, output_path)
    print(f"Output file created at: {output_path}.")

if __name__ == "__main__":
    try:
        main()

    except Exception as exc:
        print("\nConversion failed:")
        print(exc)

    input("Press Enter to exit...")