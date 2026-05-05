"""
storage.py — Storage Layer.

Manages fixed-size disk blocks backed by a bytearray representing the
virtual disk.  Provides a free-space bitmap for allocation / deallocation
and raw block-level read/write primitives.
"""

from __future__ import annotations

import struct
from typing import List, Optional

from config import BLOCK_SIZE, TOTAL_BLOCKS


class StorageManager:
    """Low-level block storage with a free-space bitmap."""

    def __init__(self, total_blocks: int = TOTAL_BLOCKS, block_size: int = BLOCK_SIZE):
        self.total_blocks = total_blocks
        self.block_size = block_size
        self.disk = bytearray(total_blocks * block_size)
        # bitmap: True → free, False → allocated
        self.bitmap: List[bool] = [True] * total_blocks
        # Reserve block 0 for the superblock
        self.bitmap[0] = False

    # ------------------------------------------------------------------
    # Block I/O
    # ------------------------------------------------------------------
    def read_block(self, block_num: int) -> bytes:
        """Return a copy of the data stored in *block_num*."""
        self._validate_block(block_num)
        start = block_num * self.block_size
        return bytes(self.disk[start : start + self.block_size])

    def write_block(self, block_num: int, data: bytes) -> None:
        """Write *data* into *block_num*, zero-padding if shorter than block size."""
        self._validate_block(block_num)
        if len(data) > self.block_size:
            raise ValueError(
                f"Data size ({len(data)}) exceeds block size ({self.block_size})."
            )
        padded = data.ljust(self.block_size, b"\x00")
        start = block_num * self.block_size
        self.disk[start : start + self.block_size] = padded

    def clear_block(self, block_num: int) -> None:
        """Zero-fill a block."""
        self.write_block(block_num, b"\x00" * self.block_size)

    # ------------------------------------------------------------------
    # Free-space bitmap operations
    # ------------------------------------------------------------------
    def allocate_block(self) -> Optional[int]:
        """Allocate a single free block.  Returns block number or None."""
        for i, free in enumerate(self.bitmap):
            if free:
                self.bitmap[i] = False
                self.clear_block(i)
                return i
        return None

    def allocate_contiguous(self, count: int) -> Optional[List[int]]:
        """Allocate *count* contiguous free blocks.  Returns list or None."""
        run_start = 0
        run_len = 0
        for i, free in enumerate(self.bitmap):
            if free:
                if run_len == 0:
                    run_start = i
                run_len += 1
                if run_len == count:
                    blocks = list(range(run_start, run_start + count))
                    for b in blocks:
                        self.bitmap[b] = False
                        self.clear_block(b)
                    return blocks
            else:
                run_len = 0
        return None

    def allocate_blocks(self, count: int) -> Optional[List[int]]:
        """Allocate *count* (possibly non-contiguous) free blocks."""
        free_blocks = [i for i, free in enumerate(self.bitmap) if free]
        if len(free_blocks) < count:
            return None
        allocated = free_blocks[:count]
        for b in allocated:
            self.bitmap[b] = False
            self.clear_block(b)
        return allocated

    def free_block(self, block_num: int) -> None:
        """Mark a block as free."""
        self._validate_block(block_num)
        self.bitmap[block_num] = True

    def free_blocks(self, block_nums: List[int]) -> None:
        """Mark multiple blocks as free."""
        for b in block_nums:
            self.free_block(b)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------
    def free_block_count(self) -> int:
        return sum(self.bitmap)

    def used_block_count(self) -> int:
        return self.total_blocks - self.free_block_count()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _validate_block(self, block_num: int) -> None:
        if not 0 <= block_num < self.total_blocks:
            raise IndexError(
                f"Block {block_num} out of range [0, {self.total_blocks})."
            )

    # ------------------------------------------------------------------
    # Serialization helpers (used by FileSystem for persistence)
    # ------------------------------------------------------------------
    def serialize_bitmap(self) -> bytes:
        """Pack bitmap into bytes (1 bit per block)."""
        ba = bytearray((self.total_blocks + 7) // 8)
        for i, free in enumerate(self.bitmap):
            if free:
                ba[i // 8] |= 1 << (i % 8)
        return bytes(ba)

    def deserialize_bitmap(self, data: bytes) -> None:
        """Restore bitmap from packed bytes."""
        for i in range(self.total_blocks):
            self.bitmap[i] = bool(data[i // 8] & (1 << (i % 8)))
