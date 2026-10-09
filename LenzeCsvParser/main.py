"""Desktop entry point, also used by the windowed executable."""
from gui import ConverterApp


def main() -> None:
    app = ConverterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
