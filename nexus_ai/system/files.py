"""
Nexus AI — File System Operations

Handles file/folder CRUD, search, compression, and recycle bin.
Sandboxed to user directories for safety.
"""

import os
import shutil
import glob
import zipfile
from pathlib import Path
from typing import Optional
from nexus_ai.utils.logger import get_logger
from nexus_ai.utils.helpers import get_user_directory, format_bytes

logger = get_logger("Files")


class FileController:
    """File system operations with safety sandboxing."""

    # Directories where file operations are allowed
    SAFE_ROOTS = [
        Path.home() / "Desktop",
        Path.home() / "Documents",
        Path.home() / "Downloads",
        Path.home() / "Music",
        Path.home() / "Pictures",
        Path.home() / "Videos",
    ]

    def _is_safe_path(self, path: str) -> bool:
        """Check if a path is within allowed directories."""
        target = Path(path).resolve()
        return any(
            target == safe_root or safe_root in target.parents
            for safe_root in self.SAFE_ROOTS
        )

    def _resolve_path(self, path: str) -> str:
        """Resolve ~ and common directory names to full paths."""
        path = path.strip()

        # Handle common names
        dir_aliases = {
            "desktop": str(Path.home() / "Desktop"),
            "documents": str(Path.home() / "Documents"),
            "downloads": str(Path.home() / "Downloads"),
            "music": str(Path.home() / "Music"),
            "pictures": str(Path.home() / "Pictures"),
            "videos": str(Path.home() / "Videos"),
            "home": str(Path.home()),
        }

        lower_path = path.lower()
        if lower_path in dir_aliases:
            return dir_aliases[lower_path]

        # Expand ~
        return str(Path(path).expanduser())

    def open_folder(self, path: str) -> tuple[bool, str]:
        """Open a folder in Windows Explorer."""
        resolved = self._resolve_path(path)

        if not os.path.exists(resolved):
            return False, f"Folder '{path}' does not exist."

        try:
            os.startfile(resolved)
            logger.info(f"Opened folder: {resolved}")
            return True, f"Opened {os.path.basename(resolved)}."
        except Exception as e:
            return False, f"Failed to open folder: {e}"

    def find_files(self, query: str, location: str = None, max_results: int = 10) -> tuple[bool, str]:
        """
        Search for files by name pattern.
        
        Args:
            query: File name or pattern to search for
            location: Directory to search in (defaults to common user dirs)
            max_results: Maximum number of results
        """
        search_dirs = []
        if location:
            resolved = self._resolve_path(location)
            if os.path.isdir(resolved):
                search_dirs.append(resolved)
        else:
            search_dirs = [str(d) for d in self.SAFE_ROOTS if d.exists()]

        results = []
        for search_dir in search_dirs:
            try:
                for root, dirs, files in os.walk(search_dir):
                    for filename in files:
                        if query.lower() in filename.lower():
                            full_path = os.path.join(root, filename)
                            size = os.path.getsize(full_path)
                            results.append((filename, full_path, size))
                            if len(results) >= max_results:
                                break
                    if len(results) >= max_results:
                        break
            except PermissionError:
                continue

        if results:
            msg_parts = [f"Found {len(results)} file(s):"]
            for name, path, size in results[:5]:  # Limit speech to 5
                msg_parts.append(f"  {name} ({format_bytes(size)})")
            return True, " ".join(msg_parts)
        else:
            return False, f"No files matching '{query}' were found."

    def create_folder(self, name: str, parent_path: str = None) -> tuple[bool, str]:
        """Create a new folder."""
        if parent_path:
            base = self._resolve_path(parent_path)
        else:
            base = str(Path.home() / "Desktop")

        full_path = os.path.join(base, name)

        if not self._is_safe_path(full_path):
            return False, "Cannot create folders outside safe directories."

        try:
            os.makedirs(full_path, exist_ok=True)
            logger.info(f"Created folder: {full_path}")
            return True, f"Created folder '{name}'."
        except Exception as e:
            return False, f"Failed to create folder: {e}"

    def delete_file(self, path: str) -> tuple[bool, str]:
        """Delete a file (sends to recycle bin when possible)."""
        resolved = self._resolve_path(path)

        if not self._is_safe_path(resolved):
            return False, "Cannot delete files outside safe directories."

        if not os.path.exists(resolved):
            return False, f"File '{path}' does not exist."

        try:
            # Try using send2trash for recycle bin
            try:
                from send2trash import send2trash
                send2trash(resolved)
                logger.info(f"Sent to recycle bin: {resolved}")
                return True, f"Moved '{os.path.basename(resolved)}' to recycle bin."
            except ImportError:
                pass

            # Direct delete as fallback
            if os.path.isdir(resolved):
                shutil.rmtree(resolved)
            else:
                os.remove(resolved)
            logger.info(f"Deleted: {resolved}")
            return True, f"Deleted '{os.path.basename(resolved)}'."
        except Exception as e:
            return False, f"Failed to delete: {e}"

    def move_file(self, source: str, destination: str) -> tuple[bool, str]:
        """Move a file or folder."""
        src = self._resolve_path(source)
        dst = self._resolve_path(destination)

        if not os.path.exists(src):
            return False, f"Source '{source}' does not exist."

        try:
            shutil.move(src, dst)
            logger.info(f"Moved: {src} → {dst}")
            return True, f"Moved '{os.path.basename(src)}' to '{os.path.basename(dst)}'."
        except Exception as e:
            return False, f"Failed to move: {e}"

    def copy_file(self, source: str, destination: str) -> tuple[bool, str]:
        """Copy a file or folder."""
        src = self._resolve_path(source)
        dst = self._resolve_path(destination)

        if not os.path.exists(src):
            return False, f"Source '{source}' does not exist."

        try:
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            logger.info(f"Copied: {src} → {dst}")
            return True, f"Copied '{os.path.basename(src)}'."
        except Exception as e:
            return False, f"Failed to copy: {e}"

    def rename_file(self, path: str, new_name: str) -> tuple[bool, str]:
        """Rename a file or folder."""
        resolved = self._resolve_path(path)

        if not os.path.exists(resolved):
            return False, f"'{path}' does not exist."

        new_path = os.path.join(os.path.dirname(resolved), new_name)

        try:
            os.rename(resolved, new_path)
            logger.info(f"Renamed: {resolved} → {new_path}")
            return True, f"Renamed to '{new_name}'."
        except Exception as e:
            return False, f"Failed to rename: {e}"

    def compress(self, path: str, output_path: str = None) -> tuple[bool, str]:
        """Compress a file or folder to ZIP."""
        resolved = self._resolve_path(path)

        if not os.path.exists(resolved):
            return False, f"'{path}' does not exist."

        if output_path is None:
            output_path = resolved + ".zip"

        try:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                if os.path.isdir(resolved):
                    for root, dirs, files in os.walk(resolved):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, os.path.dirname(resolved))
                            zf.write(file_path, arcname)
                else:
                    zf.write(resolved, os.path.basename(resolved))

            logger.info(f"Compressed: {resolved} → {output_path}")
            return True, f"Compressed '{os.path.basename(resolved)}' to ZIP."
        except Exception as e:
            return False, f"Failed to compress: {e}"

    def extract(self, path: str, output_dir: str = None) -> tuple[bool, str]:
        """Extract a ZIP file."""
        resolved = self._resolve_path(path)

        if not os.path.exists(resolved):
            return False, f"'{path}' does not exist."

        if output_dir is None:
            output_dir = os.path.splitext(resolved)[0]

        try:
            with zipfile.ZipFile(resolved, 'r') as zf:
                zf.extractall(output_dir)

            logger.info(f"Extracted: {resolved} → {output_dir}")
            return True, f"Extracted '{os.path.basename(resolved)}'."
        except Exception as e:
            return False, f"Failed to extract: {e}"

    def empty_recycle_bin(self) -> tuple[bool, str]:
        """Empty the Windows recycle bin."""
        try:
            import ctypes
            # SHEmptyRecycleBinW with SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x07)
            logger.info("Recycle bin emptied")
            return True, "Recycle bin emptied."
        except Exception as e:
            return False, f"Failed to empty recycle bin: {e}"
