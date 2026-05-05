"""
config.py — Disk geometry and system constants.

Defines the virtual disk layout: block size, total blocks, maximum
number of inodes, and the default disk image filename.
"""

# ---------------------------------------------------------------------------
# Disk Geometry
# ---------------------------------------------------------------------------
BLOCK_SIZE = 512          # bytes per block
TOTAL_BLOCKS = 2048       # total blocks on virtual disk  (1 MB disk)
MAX_INODES = 256          # maximum number of inodes

# ---------------------------------------------------------------------------
# File System Limits
# ---------------------------------------------------------------------------
MAX_FILENAME_LENGTH = 60  # characters
MAX_FILE_SIZE = BLOCK_SIZE * 16  # max blocks per file (8 KB)
INDEX_BLOCK_CAPACITY = BLOCK_SIZE // 4  # pointers per index block (4-byte ints)

# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
DEFAULT_DISK_IMAGE = "virtual_disk.img"

# ---------------------------------------------------------------------------
# Inode Types
# ---------------------------------------------------------------------------
INODE_TYPE_FILE = 0
INODE_TYPE_DIR = 1

# ---------------------------------------------------------------------------
# Default Permissions (octal style, stored as int)
# ---------------------------------------------------------------------------
DEFAULT_FILE_PERMS = 0o644
DEFAULT_DIR_PERMS = 0o755
