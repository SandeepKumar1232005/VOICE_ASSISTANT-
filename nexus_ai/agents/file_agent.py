"""
Nexus AI — File Management Agent

Handles all file system operations via the FileController.
"""

from nexus_ai.agents.base_agent import BaseAgent, AgentResult
from nexus_ai.system.files import FileController
from nexus_ai.utils.logger import get_logger

logger = get_logger("FileAgent")


class FileAgent(BaseAgent):
    """
    File Management Agent — File and folder operations.
    
    Capabilities:
        - Open folders
        - Find files by name
        - Create, rename, move, copy, delete files/folders
        - Compress to ZIP / Extract ZIP
        - Empty recycle bin
    """

    def __init__(self):
        super().__init__("FileAgent")
        self.file_controller = FileController()

    async def execute(self, task: dict) -> AgentResult:
        action = task.get("action", "")
        params = task.get("parameters", {})

        handlers = {
            "OPEN_FOLDER": lambda: self.file_controller.open_folder(
                params.get("path", "")
            ),
            "FIND_FILE": lambda: self.file_controller.find_files(
                params.get("query", ""),
                params.get("location"),
            ),
            "CREATE_FOLDER": lambda: self.file_controller.create_folder(
                params.get("name", "New Folder"),
                params.get("path"),
            ),
            "DELETE_FILE": lambda: self.file_controller.delete_file(
                params.get("path", "")
            ),
            "MOVE_FILE": lambda: self.file_controller.move_file(
                params.get("source", ""),
                params.get("destination", ""),
            ),
            "COPY_FILE": lambda: self.file_controller.copy_file(
                params.get("source", ""),
                params.get("destination", ""),
            ),
            "RENAME_FILE": lambda: self.file_controller.rename_file(
                params.get("path", ""),
                params.get("new_name", ""),
            ),
            "COMPRESS_FILE": lambda: self.file_controller.compress(
                params.get("path", "")
            ),
            "EXTRACT_FILE": lambda: self.file_controller.extract(
                params.get("path", "")
            ),
            "EMPTY_RECYCLE_BIN": lambda: self.file_controller.empty_recycle_bin(),
        }

        handler = handlers.get(action)
        if handler is None:
            return AgentResult(success=False, message=f"Unknown file action: {action}")

        success, message = handler()
        return AgentResult(success=success, message=message)

    def get_capabilities(self) -> list[str]:
        return [
            "OPEN_FOLDER", "FIND_FILE", "CREATE_FOLDER",
            "DELETE_FILE", "MOVE_FILE", "COPY_FILE",
            "RENAME_FILE", "COMPRESS_FILE", "EXTRACT_FILE",
            "EMPTY_RECYCLE_BIN",
        ]
