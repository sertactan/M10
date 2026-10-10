"""Generate PyInstaller Windows PE version metadata from canonical release version."""
from pathlib import Path

from scripts.check_release_version import require_aligned


def render(root: Path) -> str:
    version = require_aligned(root)["release"]
    parts = version.split(".")
    if len(parts) not in (3, 4) or any(not part.isdecimal() or int(part) > 65535 for part in parts):
        raise ValueError("Windows PE version requires three or four uint16 components")
    numbers = tuple(map(int, parts)) + (0,) * (4 - len(parts))
    return (
        "VSVersionInfo(ffi=FixedFileInfo(filevers=" + repr(numbers) +
        ", prodvers=" + repr(numbers) + ", mask=0x3f, flags=0x0, "
        "OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)), "
        "kids=[StringFileInfo([StringTable('040904B0', ["
        "StringStruct('CompanyName', 'Tancodes'), "
        "StringStruct('FileDescription', 'S15.3 Research Terminal'), "
        f"StringStruct('FileVersion', '{version}.0'), "
        f"StringStruct('ProductVersion', '{version}.0'), "
        "StringStruct('ProductName', 'S15.3 Research Terminal')])]), "
        "VarFileInfo([VarStruct('Translation', [1033, 1200])])])"
    )
