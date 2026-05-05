"""
main.py — Entry point for the File System Simulator.

Usage:
    python main.py [--disk FILENAME] [--alloc STRATEGY]

Options:
    --disk   Path to the virtual disk image file (default: virtual_disk.img)
    --alloc  Allocation strategy: contiguous | linked | indexed (default: indexed)
"""

import argparse
import sys

from config import DEFAULT_DISK_IMAGE
from filesystem import FileSystem
from shell import Shell


def main() -> None:
    parser = argparse.ArgumentParser(
        description="File System Simulator — CSE 323 Operating Systems Design",
    )
    parser.add_argument(
        "--disk",
        default=DEFAULT_DISK_IMAGE,
        help="Virtual disk image file (default: %(default)s)",
    )
    parser.add_argument(
        "--alloc",
        default="indexed",
        choices=FileSystem.STRATEGIES,
        help="Block allocation strategy (default: %(default)s)",
    )
    args = parser.parse_args()

    try:
        fs = FileSystem(alloc_strategy=args.alloc, disk_image=args.disk)
    except Exception as e:
        print(f"Error initializing file system: {e}", file=sys.stderr)
        sys.exit(1)

    shell = Shell(fs)
    shell.run()


if __name__ == "__main__":
    main()
