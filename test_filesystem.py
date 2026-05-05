"""
test_filesystem.py — Unit tests for the File System Layer.

Tests all three allocation strategies: contiguous, linked, indexed.
"""

import sys
import os
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from filesystem import FileSystem
from config import INODE_TYPE_DIR, INODE_TYPE_FILE


class FileSystemTestBase:
    """Mixin providing common test methods, parameterised by strategy."""

    strategy: str = "indexed"

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".img")
        self.tmp.close()
        os.unlink(self.tmp.name)  # start fresh
        self.fs = FileSystem(alloc_strategy=self.strategy, disk_image=self.tmp.name)

    def tearDown(self):
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)

    # --- Directory tests ---
    def test_mkdir_and_ls(self):
        self.fs.mkdir("docs")
        entries = self.fs.ls()
        self.assertIn("docs/", entries)

    def test_cd_and_pwd(self):
        self.fs.mkdir("projects")
        self.fs.cd("projects")
        self.assertEqual(self.fs.pwd(), "/projects")

    def test_cd_parent(self):
        self.fs.mkdir("a")
        self.fs.cd("a")
        self.fs.cd("..")
        self.assertEqual(self.fs.pwd(), "/")

    def test_nested_directories(self):
        self.fs.mkdir("a")
        self.fs.cd("a")
        self.fs.mkdir("b")
        self.fs.cd("b")
        self.assertEqual(self.fs.pwd(), "/a/b")

    def test_mkdir_duplicate_raises(self):
        self.fs.mkdir("dup")
        with self.assertRaises(FileExistsError):
            self.fs.mkdir("dup")

    # --- File tests ---
    def test_touch_creates_file(self):
        self.fs.touch("hello.txt")
        entries = self.fs.ls()
        self.assertIn("hello.txt", entries)

    def test_write_and_read(self):
        self.fs.write_file("notes.txt", "Hello, World!")
        content = self.fs.read_file("notes.txt")
        self.assertEqual(content, "Hello, World!")

    def test_append(self):
        self.fs.write_file("log.txt", "line1\n")
        self.fs.append_file("log.txt", "line2\n")
        content = self.fs.read_file("log.txt")
        self.assertEqual(content, "line1\nline2\n")

    def test_overwrite(self):
        self.fs.write_file("f.txt", "old data")
        self.fs.write_file("f.txt", "new data")
        self.assertEqual(self.fs.read_file("f.txt"), "new data")

    def test_rm_file(self):
        self.fs.touch("temp.txt")
        self.fs.rm("temp.txt")
        entries = self.fs.ls()
        self.assertNotIn("temp.txt", entries)

    def test_rm_nonempty_dir_raises(self):
        self.fs.mkdir("full")
        self.fs.cd("full")
        self.fs.touch("child.txt")
        self.fs.cd("..")
        with self.assertRaises(OSError):
            self.fs.rm("full")

    def test_rm_empty_dir(self):
        self.fs.mkdir("empty")
        self.fs.rm("empty")
        self.assertNotIn("empty/", self.fs.ls())

    # --- Stat ---
    def test_stat(self):
        self.fs.write_file("info.txt", "data")
        info = self.fs.stat("info.txt")
        self.assertEqual(info["type"], "file")
        self.assertEqual(info["size"], 4)

    # --- Disk usage ---
    def test_df(self):
        info = self.fs.df()
        self.assertIn("total_blocks", info)
        self.assertIn("free_blocks", info)
        self.assertEqual(info["allocation_strategy"], self.strategy)

    # --- Persistence ---
    def test_save_and_reload(self):
        self.fs.mkdir("persist")
        self.fs.cd("persist")
        self.fs.write_file("saved.txt", "persistent data")
        self.fs.cd("/")
        self.fs.save()

        # Reload from the same disk image
        fs2 = FileSystem(alloc_strategy=self.strategy, disk_image=self.tmp.name)
        fs2.cd("persist")
        content = fs2.read_file("saved.txt")
        self.assertEqual(content, "persistent data")

    # --- Large-ish write ---
    def test_multiblock_write(self):
        big = "A" * 2000  # spans multiple blocks
        self.fs.write_file("big.txt", big)
        self.assertEqual(self.fs.read_file("big.txt"), big)

    # --- Path resolution ---
    def test_absolute_path(self):
        self.fs.mkdir("x")
        self.fs.cd("x")
        self.fs.mkdir("y")
        info = self.fs.stat("/x/y")
        self.assertEqual(info["type"], "directory")

    def test_not_found_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.fs.stat("nonexistent")


# ======================================================================
# Concrete test classes — one per allocation strategy
# ======================================================================
class TestContiguous(FileSystemTestBase, unittest.TestCase):
    strategy = "contiguous"


class TestLinked(FileSystemTestBase, unittest.TestCase):
    strategy = "linked"


class TestIndexed(FileSystemTestBase, unittest.TestCase):
    strategy = "indexed"


if __name__ == "__main__":
    unittest.main()
