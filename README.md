# File System Simulator

**CSE 323: Operating Systems Design**

A virtual file system simulator that emulates core file system operations inside a virtual
environment. Supports hierarchical directory structures, multiple disk block allocation
strategies, file metadata management, and persistent state across sessions.

## Features

- **Hierarchical Directory Structure** — Create, navigate, and manage nested directories.
- **File Operations** — Create, read, write, append, and delete files.
- **Disk Block Allocation** — Supports Contiguous, Linked, and Indexed allocation methods.
- **Metadata Tracking** — File size, timestamps (created/modified), and permission bits.
- **Persistence** — Virtual disk state saved to a single binary host file.
- **Interactive CLI Shell** — Familiar commands: `mkdir`, `cd`, `ls`, `touch`, `rm`, `cat`, `write`, `stat`, `df`, and more.

## Project Structure

```
filesys_simulator/
├── README.md
├── main.py              # Entry point — launches the CLI shell
├── config.py            # Disk geometry and system constants
├── storage.py           # Storage layer — disk blocks and free-space bitmap
├── filesystem.py        # File system layer — inodes, directories, allocation
├── shell.py             # User interface layer — command-line shell
└── tests/
    ├── __init__.py
    ├── test_storage.py
    └── test_filesystem.py
```

## Quick Start

```bash
# No external dependencies required — uses Python 3 standard library only.

# Run the simulator
python main.py

# Run with a custom disk image file
python main.py --disk my_disk.img

# Choose an allocation strategy (contiguous | linked | indexed)
python main.py --alloc linked

# Run unit tests
python -m pytest tests/ -v
```

## Shell Commands

| Command | Description |
|---------|-------------|
| `mkdir <name>` | Create a new directory |
| `cd <path>` | Change current directory (supports `..` and `/`) |
| `ls [-l]` | List directory contents (`-l` for detailed view) |
| `touch <name>` | Create an empty file |
| `write <name> <text>` | Write text content to a file |
| `append <name> <text>` | Append text content to a file |
| `cat <name>` | Display file contents |
| `rm <name>` | Remove a file or empty directory |
| `stat <name>` | Show file/directory metadata |
| `df` | Show disk usage statistics |
| `alloc` | Show current allocation strategy |
| `help` | Show available commands |
| `exit` | Save state and exit |

## Allocation Strategies

- **Contiguous** — Each file occupies a set of contiguous blocks on disk. Fast sequential reads but suffers from external fragmentation.
- **Linked** — Each block contains a pointer to the next block. No external fragmentation but slower random access.
- **Indexed** — A dedicated index block holds pointers to all data blocks. Supports direct access without external fragmentation.

## Author

Md. Sakibur Rahman Somoy | 1921382642
