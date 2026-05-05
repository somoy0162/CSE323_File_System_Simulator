"""
filesystem.py — File System Layer.

Implements inode-based metadata, hierarchical directory entries, three
disk-block allocation strategies (contiguous, linked, indexed), and
persistence to a single host file.
"""

from __future__ import annotations

import json
import os
import struct
import time
from typing import Any, Dict, List, Optional, Tuple

from config import (
    BLOCK_SIZE,
    DEFAULT_DIR_PERMS,
    DEFAULT_DISK_IMAGE,
    DEFAULT_FILE_PERMS,
    INDEX_BLOCK_CAPACITY,
    INODE_TYPE_DIR,
    INODE_TYPE_FILE,
    MAX_FILE_SIZE,
    MAX_FILENAME_LENGTH,
    MAX_INODES,
    TOTAL_BLOCKS,
)
from storage import StorageManager


# ======================================================================
# Inode
# ======================================================================
class Inode:
    """Metadata record for a single file or directory."""

    def __init__(
        self,
        inode_id: int,
        itype: int = INODE_TYPE_FILE,
        permissions: int = DEFAULT_FILE_PERMS,
    ):
        self.inode_id = inode_id
        self.itype = itype  # INODE_TYPE_FILE or INODE_TYPE_DIR
        self.size = 0  # bytes (for files)
        self.permissions = permissions
        self.created_at = time.time()
        self.modified_at = self.created_at
        # Allocation metadata — semantics depend on strategy
        self.blocks: List[int] = []  # data block numbers
        self.index_block: Optional[int] = None  # used by indexed allocation
        # Directory-specific
        self.children: Dict[str, int] = {}  # name → inode_id
        self.parent_inode: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inode_id": self.inode_id,
            "itype": self.itype,
            "size": self.size,
            "permissions": self.permissions,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "blocks": self.blocks,
            "index_block": self.index_block,
            "children": self.children,
            "parent_inode": self.parent_inode,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Inode":
        inode = cls(d["inode_id"], d["itype"], d["permissions"])
        inode.size = d["size"]
        inode.created_at = d["created_at"]
        inode.modified_at = d["modified_at"]
        inode.blocks = d["blocks"]
        inode.index_block = d.get("index_block")
        inode.children = d["children"]
        inode.parent_inode = d.get("parent_inode")
        return inode


# ======================================================================
# FileSystem
# ======================================================================
class FileSystem:
    """
    Virtual file system built on top of :class:`StorageManager`.

    Parameters
    ----------
    alloc_strategy : str
        One of ``"contiguous"``, ``"linked"``, ``"indexed"``.
    disk_image : str
        Host file used for persistence.
    """

    STRATEGIES = ("contiguous", "linked", "indexed")

    def __init__(
        self,
        alloc_strategy: str = "indexed",
        disk_image: str = DEFAULT_DISK_IMAGE,
    ):
        if alloc_strategy not in self.STRATEGIES:
            raise ValueError(
                f"Unknown allocation strategy '{alloc_strategy}'. "
                f"Choose from {self.STRATEGIES}."
            )
        self.alloc_strategy = alloc_strategy
        self.disk_image = disk_image
        self.storage = StorageManager()
        self.inodes: Dict[int, Inode] = {}
        self._next_inode_id = 0
        self.cwd_inode_id = 0  # current working directory

        if os.path.exists(disk_image):
            self._load()
        else:
            self._format()

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------
    def _format(self) -> None:
        """Create a fresh file system with a root directory."""
        root = self._alloc_inode(INODE_TYPE_DIR, DEFAULT_DIR_PERMS)
        root.parent_inode = root.inode_id  # root is its own parent
        self.cwd_inode_id = root.inode_id

    # ------------------------------------------------------------------
    # Inode helpers
    # ------------------------------------------------------------------
    def _alloc_inode(self, itype: int, perms: int) -> Inode:
        if len(self.inodes) >= MAX_INODES:
            raise OSError("No free inodes available.")
        inode = Inode(self._next_inode_id, itype, perms)
        self.inodes[self._next_inode_id] = inode
        self._next_inode_id += 1
        return inode

    def _get_inode(self, inode_id: int) -> Inode:
        if inode_id not in self.inodes:
            raise FileNotFoundError(f"Inode {inode_id} does not exist.")
        return self.inodes[inode_id]

    def _cwd(self) -> Inode:
        return self._get_inode(self.cwd_inode_id)

    # ------------------------------------------------------------------
    # Path resolution
    # ------------------------------------------------------------------
    def _resolve(self, path: str) -> Inode:
        """Resolve a path string to an inode."""
        if path == "/":
            return self._get_inode(0)

        if path.startswith("/"):
            current = self._get_inode(0)
            path = path.lstrip("/")
        else:
            current = self._cwd()

        parts = [p for p in path.split("/") if p]
        for part in parts:
            if current.itype != INODE_TYPE_DIR:
                raise NotADirectoryError(f"'{part}' is not a directory.")
            if part == ".":
                continue
            if part == "..":
                current = self._get_inode(
                    current.parent_inode if current.parent_inode is not None else 0
                )
                continue
            if part not in current.children:
                raise FileNotFoundError(f"'{part}' not found.")
            current = self._get_inode(current.children[part])
        return current

    def _resolve_parent(self, path: str) -> Tuple[Inode, str]:
        """Return (parent_inode, child_name) for the given path."""
        parts = [p for p in path.replace("\\", "/").split("/") if p]
        if not parts:
            raise ValueError("Empty path.")
        name = parts[-1]
        if len(parts) == 1:
            parent = self._cwd() if not path.startswith("/") else self._get_inode(0)
        else:
            parent_path = "/".join(parts[:-1])
            if path.startswith("/"):
                parent_path = "/" + parent_path
            parent = self._resolve(parent_path)
        if parent.itype != INODE_TYPE_DIR:
            raise NotADirectoryError("Parent is not a directory.")
        return parent, name

    # ------------------------------------------------------------------
    # Directory operations
    # ------------------------------------------------------------------
    def mkdir(self, path: str) -> None:
        parent, name = self._resolve_parent(path)
        if len(name) > MAX_FILENAME_LENGTH:
            raise ValueError(f"Name exceeds {MAX_FILENAME_LENGTH} characters.")
        if name in parent.children:
            raise FileExistsError(f"'{name}' already exists.")

        d = self._alloc_inode(INODE_TYPE_DIR, DEFAULT_DIR_PERMS)
        d.parent_inode = parent.inode_id
        parent.children[name] = d.inode_id
        parent.modified_at = time.time()

    def cd(self, path: str) -> None:
        target = self._resolve(path)
        if target.itype != INODE_TYPE_DIR:
            raise NotADirectoryError(f"'{path}' is not a directory.")
        self.cwd_inode_id = target.inode_id

    def ls(self, detailed: bool = False) -> List[str]:
        cwd = self._cwd()
        entries: List[str] = []
        for name, iid in sorted(cwd.children.items()):
            inode = self._get_inode(iid)
            if detailed:
                kind = "d" if inode.itype == INODE_TYPE_DIR else "-"
                perms = oct(inode.permissions)[2:]
                mod = time.strftime("%Y-%m-%d %H:%M", time.localtime(inode.modified_at))
                size = str(inode.size).rjust(8)
                entries.append(f"{kind}{perms}  {size}  {mod}  {name}")
            else:
                suffix = "/" if inode.itype == INODE_TYPE_DIR else ""
                entries.append(f"{name}{suffix}")
        return entries

    def pwd(self) -> str:
        parts: List[str] = []
        inode = self._cwd()
        while True:
            if inode.inode_id == 0:
                break
            # Find name in parent
            parent = self._get_inode(
                inode.parent_inode if inode.parent_inode is not None else 0
            )
            found = False
            for name, iid in parent.children.items():
                if iid == inode.inode_id:
                    parts.append(name)
                    found = True
                    break
            if not found:
                break
            inode = parent
        return "/" + "/".join(reversed(parts)) if parts else "/"

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------
    def touch(self, path: str) -> None:
        parent, name = self._resolve_parent(path)
        if len(name) > MAX_FILENAME_LENGTH:
            raise ValueError(f"Name exceeds {MAX_FILENAME_LENGTH} characters.")
        if name in parent.children:
            # Update timestamp of existing file
            self._get_inode(parent.children[name]).modified_at = time.time()
            return
        f = self._alloc_inode(INODE_TYPE_FILE, DEFAULT_FILE_PERMS)
        f.parent_inode = parent.inode_id
        parent.children[name] = f.inode_id
        parent.modified_at = time.time()

    def write_file(self, path: str, data: str) -> None:
        """Write (overwrite) text data to a file."""
        parent, name = self._resolve_parent(path)
        if name not in parent.children:
            self.touch(path)
        inode = self._get_inode(parent.children[name])
        if inode.itype != INODE_TYPE_FILE:
            raise IsADirectoryError(f"'{name}' is a directory.")

        raw = data.encode("utf-8")
        if len(raw) > MAX_FILE_SIZE:
            raise OSError(f"Data exceeds maximum file size ({MAX_FILE_SIZE} bytes).")

        # Free previously allocated blocks
        self._free_file_blocks(inode)

        # Allocate and write new blocks
        self._allocate_and_write(inode, raw)

    def append_file(self, path: str, data: str) -> None:
        """Append text data to an existing file."""
        inode = self._resolve(path)
        if inode.itype != INODE_TYPE_FILE:
            raise IsADirectoryError("Cannot append to a directory.")
        existing = self._read_raw(inode)
        new_data = existing + data.encode("utf-8")
        if len(new_data) > MAX_FILE_SIZE:
            raise OSError("Appended data would exceed maximum file size.")
        self._free_file_blocks(inode)
        self._allocate_and_write(inode, new_data)

    def read_file(self, path: str) -> str:
        inode = self._resolve(path)
        if inode.itype != INODE_TYPE_FILE:
            raise IsADirectoryError(f"'{path}' is a directory.")
        return self._read_raw(inode).decode("utf-8", errors="replace")

    def rm(self, path: str) -> None:
        parent, name = self._resolve_parent(path)
        if name not in parent.children:
            raise FileNotFoundError(f"'{name}' not found.")
        inode = self._get_inode(parent.children[name])
        if inode.itype == INODE_TYPE_DIR:
            if inode.children:
                raise OSError(f"Directory '{name}' is not empty.")
        else:
            self._free_file_blocks(inode)
        del parent.children[name]
        del self.inodes[inode.inode_id]
        parent.modified_at = time.time()

    def stat(self, path: str) -> Dict[str, Any]:
        inode = self._resolve(path)
        kind = "directory" if inode.itype == INODE_TYPE_DIR else "file"
        return {
            "inode": inode.inode_id,
            "type": kind,
            "size": inode.size,
            "permissions": oct(inode.permissions),
            "created": time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(inode.created_at)
            ),
            "modified": time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(inode.modified_at)
            ),
            "blocks": inode.blocks,
            "index_block": inode.index_block,
        }

    # ------------------------------------------------------------------
    # Disk usage
    # ------------------------------------------------------------------
    def df(self) -> Dict[str, Any]:
        total = self.storage.total_blocks
        used = self.storage.used_block_count()
        free = self.storage.free_block_count()
        return {
            "total_blocks": total,
            "used_blocks": used,
            "free_blocks": free,
            "block_size": self.storage.block_size,
            "total_bytes": total * self.storage.block_size,
            "used_bytes": used * self.storage.block_size,
            "free_bytes": free * self.storage.block_size,
            "allocation_strategy": self.alloc_strategy,
        }

    # ==================================================================
    # Allocation strategies
    # ==================================================================
    def _allocate_and_write(self, inode: Inode, raw: bytes) -> None:
        """Allocate blocks and write *raw* bytes using the current strategy."""
        blocks_needed = max(1, (len(raw) + self.storage.block_size - 1) // self.storage.block_size)

        if self.alloc_strategy == "contiguous":
            self._write_contiguous(inode, raw, blocks_needed)
        elif self.alloc_strategy == "linked":
            self._write_linked(inode, raw, blocks_needed)
        elif self.alloc_strategy == "indexed":
            self._write_indexed(inode, raw, blocks_needed)

        inode.size = len(raw)
        inode.modified_at = time.time()

    # --- Contiguous ----
    def _write_contiguous(self, inode: Inode, raw: bytes, count: int) -> None:
        blocks = self.storage.allocate_contiguous(count)
        if blocks is None:
            raise OSError("Not enough contiguous blocks available.")
        for i, blk in enumerate(blocks):
            start = i * self.storage.block_size
            chunk = raw[start : start + self.storage.block_size]
            self.storage.write_block(blk, chunk)
        inode.blocks = blocks

    # --- Linked --------
    def _write_linked(self, inode: Inode, raw: bytes, count: int) -> None:
        blocks = self.storage.allocate_blocks(count)
        if blocks is None:
            raise OSError("Not enough blocks available.")
        # Reserve last 4 bytes of each block for the next-block pointer
        usable = self.storage.block_size - 4
        for i, blk in enumerate(blocks):
            start = i * usable
            chunk = raw[start : start + usable]
            next_blk = blocks[i + 1] if i + 1 < len(blocks) else 0xFFFFFFFF
            data = chunk.ljust(usable, b"\x00") + struct.pack("<I", next_blk)
            self.storage.write_block(blk, data)
        inode.blocks = [blocks[0]]  # store head block only

    # --- Indexed -------
    def _write_indexed(self, inode: Inode, raw: bytes, count: int) -> None:
        if count > INDEX_BLOCK_CAPACITY:
            raise OSError("File too large for single index block.")
        idx_block = self.storage.allocate_block()
        if idx_block is None:
            raise OSError("No free block for index block.")
        data_blocks = self.storage.allocate_blocks(count)
        if data_blocks is None:
            self.storage.free_block(idx_block)
            raise OSError("Not enough blocks available.")
        # Write data blocks
        for i, blk in enumerate(data_blocks):
            start = i * self.storage.block_size
            chunk = raw[start : start + self.storage.block_size]
            self.storage.write_block(blk, chunk)
        # Write index block (array of 4-byte block pointers)
        idx_data = b"".join(struct.pack("<I", b) for b in data_blocks)
        self.storage.write_block(idx_block, idx_data)
        inode.blocks = data_blocks
        inode.index_block = idx_block

    # ------------------------------------------------------------------
    # Reading helpers
    # ------------------------------------------------------------------
    def _read_raw(self, inode: Inode) -> bytes:
        if inode.size == 0:
            return b""

        if self.alloc_strategy == "contiguous":
            return self._read_contiguous(inode)
        elif self.alloc_strategy == "linked":
            return self._read_linked(inode)
        elif self.alloc_strategy == "indexed":
            return self._read_indexed(inode)
        return b""

    def _read_contiguous(self, inode: Inode) -> bytes:
        data = b""
        for blk in inode.blocks:
            data += self.storage.read_block(blk)
        return data[: inode.size]

    def _read_linked(self, inode: Inode) -> bytes:
        data = b""
        usable = self.storage.block_size - 4
        current = inode.blocks[0] if inode.blocks else None
        while current is not None and current != 0xFFFFFFFF:
            block_data = self.storage.read_block(current)
            data += block_data[:usable]
            (next_blk,) = struct.unpack("<I", block_data[usable : usable + 4])
            current = next_blk if next_blk != 0xFFFFFFFF else None
        return data[: inode.size]

    def _read_indexed(self, inode: Inode) -> bytes:
        data = b""
        for blk in inode.blocks:
            data += self.storage.read_block(blk)
        return data[: inode.size]

    # ------------------------------------------------------------------
    # Free blocks for a file
    # ------------------------------------------------------------------
    def _free_file_blocks(self, inode: Inode) -> None:
        if self.alloc_strategy == "linked" and inode.blocks:
            # Walk the linked chain from head
            current = inode.blocks[0]
            usable = self.storage.block_size - 4
            while current is not None and current != 0xFFFFFFFF:
                block_data = self.storage.read_block(current)
                (next_blk,) = struct.unpack("<I", block_data[usable : usable + 4])
                self.storage.free_block(current)
                current = next_blk if next_blk != 0xFFFFFFFF else None
        else:
            self.storage.free_blocks(inode.blocks)

        if inode.index_block is not None:
            self.storage.free_block(inode.index_block)

        inode.blocks = []
        inode.index_block = None
        inode.size = 0

    # ==================================================================
    # Persistence
    # ==================================================================
    def save(self) -> None:
        """Persist the entire virtual file system to *self.disk_image*."""
        state = {
            "alloc_strategy": self.alloc_strategy,
            "next_inode_id": self._next_inode_id,
            "cwd_inode_id": self.cwd_inode_id,
            "inodes": {str(k): v.to_dict() for k, v in self.inodes.items()},
        }
        meta = json.dumps(state).encode("utf-8")
        bitmap = self.storage.serialize_bitmap()

        with open(self.disk_image, "wb") as f:
            # Header: meta_len (4 B) | bitmap_len (4 B) | meta | bitmap | disk
            f.write(struct.pack("<II", len(meta), len(bitmap)))
            f.write(meta)
            f.write(bitmap)
            f.write(self.storage.disk)

    def _load(self) -> None:
        """Restore the file system from *self.disk_image*."""
        with open(self.disk_image, "rb") as f:
            header = f.read(8)
            if len(header) < 8:
                self._format()
                return
            meta_len, bitmap_len = struct.unpack("<II", header)
            meta = json.loads(f.read(meta_len).decode("utf-8"))
            bitmap_data = f.read(bitmap_len)
            disk_data = f.read()

        self.alloc_strategy = meta["alloc_strategy"]
        self._next_inode_id = meta["next_inode_id"]
        self.cwd_inode_id = meta["cwd_inode_id"]
        self.inodes = {
            int(k): Inode.from_dict(v) for k, v in meta["inodes"].items()
        }
        self.storage.deserialize_bitmap(bitmap_data)
        if disk_data:
            self.storage.disk = bytearray(disk_data)
