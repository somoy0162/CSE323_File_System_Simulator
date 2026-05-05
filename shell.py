"""
shell.py — User Interface Layer.

Provides an interactive command-line shell with familiar Unix-style
commands for navigating and manipulating the virtual file system.
"""

from __future__ import annotations

import shlex
from typing import List

from filesystem import FileSystem


class Shell:
    """Interactive command-line shell for the file system simulator."""

    HELP_TEXT = """
╔══════════════════════════════════════════════════════════════════╗
║                   File System Simulator — Help                  ║
╠══════════════════════════════════════════════════════════════════╣
║  mkdir <name>          Create a new directory                   ║
║  cd <path>             Change directory (supports .. and /)     ║
║  ls [-l]               List directory contents                  ║
║  pwd                   Print working directory                  ║
║  touch <name>          Create an empty file                     ║
║  write <name> <text>   Write text to a file (overwrites)        ║
║  append <name> <text>  Append text to a file                    ║
║  cat <name>            Display file contents                    ║
║  rm <name>             Remove a file or empty directory          ║
║  stat <name>           Show file/directory metadata              ║
║  df                    Show disk usage statistics                ║
║  alloc                 Show current allocation strategy          ║
║  help                  Show this help message                    ║
║  exit                  Save state and exit                       ║
╚══════════════════════════════════════════════════════════════════╝
"""

    def __init__(self, fs: FileSystem):
        self.fs = fs
        self.running = True

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self) -> None:
        print("=" * 64)
        print("  File System Simulator")
        print(f"  Allocation Strategy : {self.fs.alloc_strategy}")
        print(f"  Disk Image          : {self.fs.disk_image}")
        print("  Type 'help' for available commands.")
        print("=" * 64)

        while self.running:
            prompt = f"fs:{self.fs.pwd()}$ "
            try:
                line = input(prompt).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                self._cmd_exit([])
                break
            if not line:
                continue
            self._dispatch(line)

    # ------------------------------------------------------------------
    # Command dispatcher
    # ------------------------------------------------------------------
    def _dispatch(self, line: str) -> None:
        try:
            tokens = shlex.split(line)
        except ValueError:
            tokens = line.split()

        cmd = tokens[0].lower()
        args = tokens[1:]

        commands = {
            "mkdir": self._cmd_mkdir,
            "cd": self._cmd_cd,
            "ls": self._cmd_ls,
            "pwd": self._cmd_pwd,
            "touch": self._cmd_touch,
            "write": self._cmd_write,
            "append": self._cmd_append,
            "cat": self._cmd_cat,
            "rm": self._cmd_rm,
            "stat": self._cmd_stat,
            "df": self._cmd_df,
            "alloc": self._cmd_alloc,
            "help": self._cmd_help,
            "exit": self._cmd_exit,
            "quit": self._cmd_exit,
        }

        handler = commands.get(cmd)
        if handler is None:
            print(f"  Unknown command: '{cmd}'. Type 'help' for usage.")
            return

        try:
            handler(args)
        except Exception as e:
            print(f"  Error: {e}")

    # ------------------------------------------------------------------
    # Command implementations
    # ------------------------------------------------------------------
    def _cmd_mkdir(self, args: List[str]) -> None:
        if not args:
            print("  Usage: mkdir <name>")
            return
        self.fs.mkdir(args[0])
        print(f"  Directory '{args[0]}' created.")

    def _cmd_cd(self, args: List[str]) -> None:
        path = args[0] if args else "/"
        self.fs.cd(path)

    def _cmd_ls(self, args: List[str]) -> None:
        detailed = "-l" in args
        entries = self.fs.ls(detailed=detailed)
        if not entries:
            print("  (empty)")
        else:
            for entry in entries:
                print(f"  {entry}")

    def _cmd_pwd(self, args: List[str]) -> None:
        print(f"  {self.fs.pwd()}")

    def _cmd_touch(self, args: List[str]) -> None:
        if not args:
            print("  Usage: touch <name>")
            return
        self.fs.touch(args[0])
        print(f"  File '{args[0]}' created.")

    def _cmd_write(self, args: List[str]) -> None:
        if len(args) < 2:
            print('  Usage: write <name> <text>')
            return
        name = args[0]
        text = " ".join(args[1:])
        self.fs.write_file(name, text)
        print(f"  Wrote {len(text)} bytes to '{name}'.")

    def _cmd_append(self, args: List[str]) -> None:
        if len(args) < 2:
            print('  Usage: append <name> <text>')
            return
        name = args[0]
        text = " ".join(args[1:])
        self.fs.append_file(name, text)
        print(f"  Appended {len(text)} bytes to '{name}'.")

    def _cmd_cat(self, args: List[str]) -> None:
        if not args:
            print("  Usage: cat <name>")
            return
        content = self.fs.read_file(args[0])
        if content:
            print(content)
        else:
            print("  (empty file)")

    def _cmd_rm(self, args: List[str]) -> None:
        if not args:
            print("  Usage: rm <name>")
            return
        self.fs.rm(args[0])
        print(f"  '{args[0]}' removed.")

    def _cmd_stat(self, args: List[str]) -> None:
        if not args:
            print("  Usage: stat <name>")
            return
        info = self.fs.stat(args[0])
        print(f"  Inode      : {info['inode']}")
        print(f"  Type       : {info['type']}")
        print(f"  Size       : {info['size']} bytes")
        print(f"  Permissions: {info['permissions']}")
        print(f"  Created    : {info['created']}")
        print(f"  Modified   : {info['modified']}")
        print(f"  Blocks     : {info['blocks']}")
        if info["index_block"] is not None:
            print(f"  Index Block: {info['index_block']}")

    def _cmd_df(self, args: List[str]) -> None:
        info = self.fs.df()
        print(f"  Allocation : {info['allocation_strategy']}")
        print(f"  Block Size : {info['block_size']} bytes")
        print(f"  Total      : {info['total_blocks']} blocks ({info['total_bytes']} bytes)")
        print(f"  Used       : {info['used_blocks']} blocks ({info['used_bytes']} bytes)")
        print(f"  Free       : {info['free_blocks']} blocks ({info['free_bytes']} bytes)")

    def _cmd_alloc(self, args: List[str]) -> None:
        print(f"  Current allocation strategy: {self.fs.alloc_strategy}")

    def _cmd_help(self, args: List[str]) -> None:
        print(self.HELP_TEXT)

    def _cmd_exit(self, args: List[str]) -> None:
        self.fs.save()
        print("  Virtual disk saved. Goodbye!")
        self.running = False
