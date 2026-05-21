"""
clean.py — Clear all generated files from test-cases folder
Usage:
    python clean.py              # clears ./test-cases/
    python clean.py ./my-folder  # clears custom folder
"""

import sys
import shutil
from pathlib import Path

TARGET = sys.argv[1] if len(sys.argv) > 1 else "./test-cases"
folder = Path(TARGET)

if not folder.exists():
    print(f"Folder not found: {TARGET}")
    sys.exit(0)

EXTENSIONS = ["*.md", "*.png", "*.txt", "*.yaml", "*.yml", "*.html", "*.htm", "*.json"]

files   = [f for ext in EXTENSIONS for f in folder.rglob(ext)]
subdirs = [d for d in folder.iterdir() if d.is_dir()]
total   = len(files) + len(subdirs)

if total == 0:
    print(f"Nothing to clean in {TARGET}")
    sys.exit(0)

# Count by extension
from collections import Counter
counts = Counter(f.suffix for f in files)

print(f"Will delete from {TARGET}:")
for ext, n in sorted(counts.items()):
    print(f"  {n} {ext} files")
if subdirs:
    print(f"  {len(subdirs)} subfolders")
print()

confirm = input("Confirm? (y/n): ").strip().lower()
if confirm != "y":
    print("Cancelled.")
    sys.exit(0)

# Delete subfolders
for d in subdirs:
    shutil.rmtree(d)

# Delete all matching files in root
for ext in EXTENSIONS:
    for f in folder.glob(ext):
        f.unlink()

print(f"Done. {TARGET} is clean.")
