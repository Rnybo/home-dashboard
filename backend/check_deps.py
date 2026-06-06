"""
check_deps.py — Verify all required Python packages are installed.
Run at server startup to fail fast with a clear error message.
"""

REQUIRED = [
    # (import_name, pip_install_name, termux_pkg_name or None)
    ("fastapi",           "fastapi",                None),
    ("uvicorn",           "uvicorn",                None),
    ("requests",          "requests",               None),
    ("bs4",               "beautifulsoup4",         None),
    ("dotenv",            "python-dotenv",          None),
    ("icalendar",         "icalendar",              None),
    ("recurring_ical_events", "recurring-ical-events", None),
    ("zeroconf",          "zeroconf",               None),
    ("httpx",             "httpx",                  None),
    ("paho.mqtt",         "paho-mqtt",              None),
    ("websockets",        "websockets",             None),
    ("pychromecast",      "pychromecast",           None),
    ("qrcode",            "qrcode",                 None),
    ("PIL",               "Pillow",                 None),
    ("html2text",         "html2text",              None),
    ("cryptography",      "cryptography",           "python-cryptography"),
]


def check() -> list[str]:
    """Returns list of missing packages."""
    missing = []
    for import_name, pip_name, pkg_name in REQUIRED:
        try:
            __import__(import_name)
        except ImportError:
            missing.append((pip_name, pkg_name))
    return missing


def check_and_print() -> bool:
    """Check deps, print status. Returns True if all OK."""
    missing = check()
    if not missing:
        return True

    print("\n" + "=" * 60)
    print("  MANGLENDE PYTHON PAKKER")
    print("=" * 60)
    print("Installer med en af følgende kommandoer:\n")

    pip_pkgs = [p for p, _ in missing]
    print(f"  pip install --break-system-packages {' '.join(pip_pkgs)}\n")

    termux_pkgs = [t for _, t in missing if t]
    if termux_pkgs:
        print("  Eller via Termux pkg (til ARM/Android):")
        print(f"  pkg install {' '.join(termux_pkgs)}\n")

    print("Manglende pakker:")
    for pip_name, pkg_name in missing:
        note = f" (eller: pkg install {pkg_name})" if pkg_name else ""
        print(f"  - {pip_name}{note}")
    print("=" * 60 + "\n")
    return False


if __name__ == "__main__":
    import sys
    ok = check_and_print()
    sys.exit(0 if ok else 1)
