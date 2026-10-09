"""Per-user appearance preferences, independent of the executable location."""
import json
import os
from pathlib import Path
import tempfile


def default_settings_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".config")
    return base / "LenzeCsvConverter" / "settings.json"


def load_theme(path: Path) -> str:
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
        theme = settings.get("theme") if isinstance(settings, dict) else None
        return theme if theme in ("light", "dark") else "light"
    except (OSError, ValueError):
        return "light"


def save_theme(path: Path, theme: str) -> None:
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".settings_", suffix=".tmp", delete=False) as file:
            temporary = Path(file.name)
            json.dump({"theme": theme}, file)
            file.write("\n")
        os.replace(temporary, path)
    except OSError:
        # A read-only preference directory must not prevent using the converter.
        pass
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
