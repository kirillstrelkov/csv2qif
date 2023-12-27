"""File utilities."""
import codecs
from pathlib import Path


def save_file(path: str, content: str) -> None:
    """Save text to file."""
    with codecs.open(path, "wb", "utf8") as f:
        f.write(content)


def get_files_and_subfiles(
    folder: str | Path,
    suffix: str,
    *,
    recursively: bool = True,
) -> list[Path]:
    """Get list of files inside folder."""
    pattern = "**/*" + suffix if recursively else "*" + suffix
    return list(Path(folder).glob(pattern))


def file_ends_with(path: str, suffix: str) -> bool:
    """Return True of file ends with suffix."""
    return path.endswith(suffix)
