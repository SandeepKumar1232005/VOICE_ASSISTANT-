"""
Nexus AI — Coding Agent

Handles programming-specific tasks like Git operations, project scaffolding,
and code review. Works alongside the standard AIAgent which handles 
general explanations and generation.
"""

import os
import subprocess
from typing import Optional

from nexus_ai.agents.base_agent import BaseAgent, AgentResult
from nexus_ai.services.nemotron_api import NemotronClient
from nexus_ai.utils.logger import get_logger

logger = get_logger("CodingAgent")


class CodingAgent(BaseAgent):
    """
    Coding Agent — Software development workflows.
    
    Capabilities:
        - Git status, pull, commit
        - Project scaffolding (Python, Web, API)
        - Code review via Nemotron AI
    """

    def __init__(self, nemotron: NemotronClient):
        super().__init__("CodingAgent")
        self.nemotron = nemotron

    async def execute(self, task: dict) -> AgentResult:
        action = task.get("action", "")
        params = task.get("parameters", {})

        if action == "GIT_STATUS":
            return self._git_status(params)
        elif action == "GIT_PULL":
            return self._git_pull(params)
        elif action == "GIT_COMMIT":
            return self._git_commit(params)
        elif action == "PROJECT_SCAFFOLD":
            return self._scaffold_project(params)
        elif action == "CODE_REVIEW":
            return self._review_code(params)

        return AgentResult(success=False, message=f"Unknown coding action: {action}")

    def _run_git_command(self, cmd: list, cwd: str) -> AgentResult:
        """Helper to run a git command safely."""
        if not cwd or not os.path.exists(cwd):
            return AgentResult(success=False, message=f"Directory not found: {cwd}")
            
        try:
            result = subprocess.run(
                ["git"] + cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"Git {' '.join(cmd)} succeeded in {cwd}")
                output = result.stdout.strip()
                if not output:
                    output = "(No output)"
                return AgentResult(success=True, message=output)
            else:
                logger.warning(f"Git {' '.join(cmd)} failed in {cwd}")
                return AgentResult(success=False, message=f"Git error: {result.stderr.strip()}")
                
        except Exception as e:
            logger.error(f"Git execution error: {e}")
            return AgentResult(success=False, message=f"Failed to run git: {str(e)}")

    def _git_status(self, params: dict) -> AgentResult:
        path = params.get("path", os.getcwd())
        res = self._run_git_command(["status", "-s"], path)
        
        if not res.success:
            return res
            
        if res.message == "(No output)":
            return AgentResult(success=True, message="Working tree is clean.")
            
        # Parse the short status to make it readable
        lines = res.message.split("\n")
        msg = f"You have {len(lines)} changed files in {os.path.basename(path)}."
        return AgentResult(success=True, message=msg, data={"raw_status": res.message})

    def _git_pull(self, params: dict) -> AgentResult:
        path = params.get("path", os.getcwd())
        res = self._run_git_command(["pull"], path)
        
        if res.success:
            if "Already up to date" in res.message:
                return AgentResult(success=True, message="Repository is already up to date.")
            return AgentResult(success=True, message="Successfully pulled latest changes.")
        return res

    def _git_commit(self, params: dict) -> AgentResult:
        path = params.get("path", os.getcwd())
        message = params.get("message", "Auto-commit from Nexus AI")
        
        # 1. Add all
        add_res = self._run_git_command(["add", "."], path)
        if not add_res.success:
            return add_res
            
        # 2. Commit
        commit_res = self._run_git_command(["commit", "-m", message], path)
        if commit_res.success:
            return AgentResult(success=True, message=f"Successfully committed changes with message: '{message}'.")
        return commit_res

    def _scaffold_project(self, params: dict) -> AgentResult:
        name = params.get("name", "new_project")
        proj_type = params.get("type", "python").lower()
        base_path = params.get("path", os.getcwd())
        
        target_dir = os.path.join(base_path, name)
        
        if os.path.exists(target_dir):
            return AgentResult(success=False, message=f"Directory {name} already exists.")
            
        try:
            os.makedirs(target_dir)
            
            if proj_type == "python":
                # Basic python structure
                os.makedirs(os.path.join(target_dir, "src"))
                os.makedirs(os.path.join(target_dir, "tests"))
                with open(os.path.join(target_dir, "requirements.txt"), "w") as f:
                    f.write("# Dependencies\n")
                with open(os.path.join(target_dir, "src", "main.py"), "w") as f:
                    f.write("def main():\n    print('Hello World')\n\nif __name__ == '__main__':\n    main()\n")
                with open(os.path.join(target_dir, "README.md"), "w") as f:
                    f.write(f"# {name}\n")
                    
                return AgentResult(success=True, message=f"Python project '{name}' scaffolded successfully.")
                
            elif proj_type == "web":
                # Basic HTML/CSS/JS
                os.makedirs(os.path.join(target_dir, "css"))
                os.makedirs(os.path.join(target_dir, "js"))
                with open(os.path.join(target_dir, "index.html"), "w") as f:
                    f.write("<!DOCTYPE html>\n<html>\n<head>\n<title>Project</title>\n</head>\n<body>\n<h1>Hello</h1>\n</body>\n</html>")
                with open(os.path.join(target_dir, "css", "style.css"), "w") as f:
                    f.write("body { font-family: sans-serif; }\n")
                with open(os.path.join(target_dir, "js", "main.js"), "w") as f:
                    f.write("console.log('Ready');\n")
                    
                return AgentResult(success=True, message=f"Web project '{name}' scaffolded successfully.")
                
            else:
                # Generic fallback
                os.makedirs(os.path.join(target_dir, "src"))
                with open(os.path.join(target_dir, "README.md"), "w") as f:
                    f.write(f"# {name}\n")
                return AgentResult(success=True, message=f"Generic project '{name}' created.")
                
        except Exception as e:
            logger.error(f"Scaffold error: {e}")
            return AgentResult(success=False, message=f"Failed to create project: {e}")

    def _review_code(self, params: dict) -> AgentResult:
        code_or_file = params.get("query", "").strip()
        language = params.get("language", "auto")
        
        if not code_or_file:
            return AgentResult(success=False, message="Please provide code or a file path to review.")
            
        if not self.nemotron.is_available():
            return AgentResult(success=False, message="AI features unavailable (API key missing).")
            
        content = code_or_file
        filename = "snippet"
        
        # Check if it's a file path
        if os.path.exists(code_or_file):
            try:
                filename = os.path.basename(code_or_file)
                with open(code_or_file, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                return AgentResult(success=False, message=f"Could not read file: {e}")
                
        prompt = f"Please review the following {language} code. Focus on bugs, security, performance, and best practices. Code:\n\n```{language}\n{content}\n```"
        
        try:
            response = self.nemotron.generate_response(
                user_input=prompt,
                system_prompt="You are an expert Senior Software Engineer performing a code review. Be constructive, concise, and highlight critical issues first.",
                temperature=0.3
            )
            return AgentResult(
                success=True, 
                message=f"I've reviewed {filename}.",
                data={"review": response, "file": filename}
            )
        except Exception as e:
            logger.error(f"Code review error: {e}")
            return AgentResult(success=False, message=f"Error during code review: {e}")

    def get_capabilities(self) -> list[str]:
        return ["GIT_STATUS", "GIT_PULL", "GIT_COMMIT", "PROJECT_SCAFFOLD", "CODE_REVIEW"]
