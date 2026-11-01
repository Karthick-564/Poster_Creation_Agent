#!/usr/bin/env python3
"""VectorCraft Font Installer & Auditor.

Scans assets/fonts/ for TTF/OTF fonts and installs them to VectorCraft's shared
Fonts directory without external network downloads.

Usage:
  python scripts/install_fonts.py         # Inspect source & target folders
  python scripts/install_fonts.py --copy  # Copy fonts to VectorCraft Fonts dir
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from poster_agent.renderer.vectorcraft_renderer import get_vectorcraft_fonts_dir


def main():
    parser = argparse.ArgumentParser(description="Install local fonts into VectorCraft shared Fonts folder")
    parser.add_argument("--copy", action="store_true", help="Perform copy of font files from assets/fonts/ to target")
    args = parser.parse_args()

    fonts_src = PROJECT_ROOT / "assets" / "fonts"
    target_dir = get_vectorcraft_fonts_dir()

    print("=" * 70)
    print("VECTORCRAFT SHARED FONT INSTALLER")
    print("=" * 70)
    print(f"Source Folder      : {fonts_src}")
    print(f"Destination Folder : {target_dir}")
    print("=" * 70)

    found_fonts = []
    if fonts_src.is_dir():
        for ext in ("*.ttf", "*.otf", "*.woff", "*.woff2"):
            found_fonts.extend(list(fonts_src.glob(ext)))

    print(f"\nDiscovered {len(found_fonts)} font file(s) in {fonts_src.name}/:")
    for f in sorted(found_fonts):
        print(f"  • {f.name} ({f.stat().st_size / 1024:.1f} KB)")

    if not found_fonts:
        print("\n[!] assets/fonts/ is empty. To use editorial fonts, drop the following OFL fonts manually:")
        print("  1. Outfit (Display): https://fonts.google.com/specimen/Outfit")
        print("  2. Inter (Sans/Body): https://fonts.google.com/specimen/Inter")
        print("  3. JetBrains Mono (Code): https://www.jetbrains.com/lp/mono/")
        print("  4. Syne (Display Alternative): https://fonts.google.com/specimen/Syne")
        return

    if args.copy:
        target_dir.mkdir(parents=True, exist_ok=True)
        copied = 0
        for f in found_fonts:
            dest = target_dir / f.name
            shutil.copy2(f, dest)
            copied += 1
            print(f"  [COPIED] -> {dest.name}")
        print(f"\nSuccessfully installed {copied} font(s) into {target_dir}")
    else:
        print("\nDry run complete. Run with '--copy' to install font files to the destination directory.")


if __name__ == "__main__":
    main()
