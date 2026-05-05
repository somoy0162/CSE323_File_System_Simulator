"""
test_storage.py — Unit tests for the Storage Layer.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from storage import StorageManager
from config import BLOCK_SIZE, TOTAL_BLOCKS


class TestStorageManager(unittest.TestCase):
    def setUp(self):
        self.sm = StorageManager(total_blocks=64, block_size=128)

    # ------------------------------------------------------------------
    # Block I/O
    # ------------------------------------------------------------------
    def test_read_write_block(self):
        data = b"Hello, File System!"
        self.sm.bitmap[5] = False  # simulate allocation
        self.sm.write_block(5, data)
        result = self.sm.read_block(5)
        self.assertEqual(result[: len(data)], data)
        self.assertEqual(len(result), 128)

    def test_write_block_too_large(self):
        with self.assertRaises(ValueError):
            self.sm.write_block(1, b"x" * 200)

    def test_invalid_block_number(self):
        with self.assertRaises(IndexError):
            self.sm.read_block(999)

    # ------------------------------------------------------------------
    # Bitmap allocation
    # ------------------------------------------------------------------
    def test_allocate_single_block(self):
        blk = self.sm.allocate_block()
        self.assertIsNotNone(blk)
        self.assertFalse(self.sm.bitmap[blk])

    def test_allocate_contiguous(self):
        blocks = self.sm.allocate_contiguous(4)
        self.assertIsNotNone(blocks)
        self.assertEqual(len(blocks), 4)
        # Check they are contiguous
        for i in range(1, len(blocks)):
            self.assertEqual(blocks[i], blocks[i - 1] + 1)

    def test_allocate_contiguous_fails_when_fragmented(self):
        # Fragment the disk by allocating every other block
        for i in range(0, 64, 2):
            self.sm.bitmap[i] = False
        result = self.sm.allocate_contiguous(4)
        self.assertIsNone(result)

    def test_allocate_blocks_non_contiguous(self):
        blocks = self.sm.allocate_blocks(5)
        self.assertIsNotNone(blocks)
        self.assertEqual(len(blocks), 5)

    def test_allocate_blocks_not_enough(self):
        self.sm.bitmap = [False] * 64
        result = self.sm.allocate_blocks(1)
        self.assertIsNone(result)

    def test_free_block(self):
        blk = self.sm.allocate_block()
        self.assertFalse(self.sm.bitmap[blk])
        self.sm.free_block(blk)
        self.assertTrue(self.sm.bitmap[blk])

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------
    def test_free_and_used_counts(self):
        initial_free = self.sm.free_block_count()
        self.sm.allocate_block()
        self.assertEqual(self.sm.free_block_count(), initial_free - 1)
        self.assertEqual(self.sm.used_block_count(), 64 - self.sm.free_block_count())

    # ------------------------------------------------------------------
    # Bitmap serialization
    # ------------------------------------------------------------------
    def test_bitmap_round_trip(self):
        self.sm.allocate_blocks(10)
        original = list(self.sm.bitmap)
        packed = self.sm.serialize_bitmap()
        self.sm.bitmap = [True] * 64  # reset
        self.sm.deserialize_bitmap(packed)
        self.assertEqual(self.sm.bitmap, original)


if __name__ == "__main__":
    unittest.main()
