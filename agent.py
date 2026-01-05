#!/usr/bin/env python3
"""
Local Code Agent - A Claude Code-like CLI tool for Ollama
Works with local LLMs to read/write files, run commands, and assist with coding.
"""

import json
import os
import subprocess
import sys
import re
import requests
from pathlib import Path
from typing import Optional

# Configuration
OLLAMA_URL = "http://192.168.0.200:11434"
MODEL = "qwen2.5-coder:7b"  # Change this to your preferred model
MAX_CONTEXT_TOKENS = 8192
AUTO_APPROVE_READS = True  # Auto-approve file reads without confirmation

# ANSI colors for terminal output
class Colors:
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    END = "\033[0m"

def print_colored(text: str, color: str = Colors.END):
    print(f"{color}{text}{Colors.END}")

def print_tool_call(tool_name: str, args: dict):
    print_colored(f"\n🔧 Tool: {tool_name}", Colors.CYAN + Colors.BOLD)
    for key, value in args.items():
        display_value = value if len(str(value)) < 100 else str(value)[:100] + "..."
        print_colored(f"   {key}: {display_value}", Colors.CYAN)

def print_tool_result(result: str, max_lines: int = 20):
    lines = result.split('\n')
    if len(lines) > max_lines:
        display = '\n'.join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)"
    else:
        display = result
    print_colored(f"📤 Result:\n{display}", Colors.GREEN)

# Tool definitions
TOOLS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file at the given path. Use this to examine existing code or files.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to read (relative or absolute)"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Creates the file if it doesn't exist, overwrites if it does.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "edit_file",
        "description": "Replace a specific block of text in a file with new content. This is preferred over write_file for large files.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to edit"
                },
                "old_content": {
                    "type": "string",
                    "description": "The exact block of text to be replaced"
                },
                "new_content": {
                    "type": "string",
                    "description": "The new text to insert instead"
                }
            },
            "required": ["path", "old_content", "new_content"]
        }
    },
    {
        "name": "list_directory",
        "description": "List files and directories at the given path. Use this to explore the project structure.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path to list (default: current directory)"
                }
            },
            "required": []
        }
    },
    {
        "name": "run_command",
        "description": "Run a shell command and return its output. Use for running tests, installing packages, git operations, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "search_files",
        "description": "Search for a pattern in files using grep. Useful for finding where something is defined or used.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "The search pattern (supports regex)"
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (default: current directory)"
                },
                "file_pattern": {
                    "type": "string",
                    "description": "File pattern to filter, e.g., '*.py' (optional)"
                }
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "task_complete",
        "description": "Call this when the task is complete and no more actions are needed.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "A brief summary of what was accomplished"
                }
            },
            "required": ["summary"]
        }
    }
]

# Tool implementations
def read_file(path: str) -> str:
    try:
        path = os.path.expanduser(path)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content if content else "(empty file)"
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"

def write_file(path: str, content: str) -> str:
    try:
        path = os.path.expanduser(path)
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to {path}"
    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"
    
def edit_file(path: str, old_content: str, new_content: str) -> str:
    try:
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            return f"Error: File not found: {path}"
        
        with open(path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        if old_content not in file_content:
            return "Error: Could not find the exact 'old_content' in the file. Please make sure the search block matches exactly (including indentation and spaces)."
        
        # Prüfen, ob der Block mehrfach vorkommt
        occurrences = file_content.count(old_content)
        if occurrences > 1:
            return f"Error: The 'old_content' block was found {occurrences} times. Please provide a more specific unique block to replace."
        
        new_file_content = file_content.replace(old_content, new_content)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_file_content)
            
        return f"Successfully edited {path}. Replaced unique occurrence of the specified block."
    except Exception as e:
        return f"Error editing file: {str(e)}"

def list_directory(path: str = ".") -> str:
    try:
        path = os.path.expanduser(path) if path else "."
        entries = []
        for entry in sorted(os.listdir(path)):
            if entry.startswith('.'):
                continue  # Skip hidden files
            full_path = os.path.join(path, entry)
            if os.path.isdir(full_path):
                entries.append(f"📁 {entry}/")
            else:
                size = os.path.getsize(full_path)
                entries.append(f"📄 {entry} ({size} bytes)")
        return '\n'.join(entries) if entries else "(empty directory)"
    except FileNotFoundError:
        return f"Error: Directory not found: {path}"
    except Exception as e:
        return f"Error listing directory: {str(e)}"

def run_command(command: str) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.getcwd()
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\n[stderr]: {result.stderr}" if output else f"[stderr]: {result.stderr}"
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        return output.strip() if output.strip() else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 60 seconds"
    except Exception as e:
        return f"Error running command: {str(e)}"

def search_files(pattern: str, path: str = ".", file_pattern: str = None) -> str:
    try:
        path = os.path.expanduser(path) if path else "."
        cmd = f"grep -rn --color=never"
        if file_pattern:
            cmd += f" --include='{file_pattern}'"
        cmd += f" '{pattern}' {path} 2>/dev/null | head -50"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout.strip()
        return output if output else f"No matches found for pattern: {pattern}"
    except subprocess.TimeoutExpired:
        return "Error: Search timed out"
    except Exception as e:
        return f"Error searching: {str(e)}"

def execute_tool(tool_name: str, args: dict) -> tuple[str, bool]:
    """Execute a tool and return (result, is_complete)"""
    if tool_name == "read_file":
        return read_file(args.get("path", "")), False
    elif tool_name == "write_file":
        return write_file(args.get("path", ""), args.get("content", "")), False
    elif tool_name == "edit_file":
        return edit_file(
            args.get("path", ""),
            args.get("old_content", ""),
            args.get("new_content", "")
        ), False
    elif tool_name == "list_directory":
        return list_directory(args.get("path", ".")), False
    elif tool_name == "run_command":
        return run_command(args.get("command", "")), False
    elif tool_name == "search_files":
        return search_files(
            args.get("pattern", ""),
            args.get("path", "."),
            args.get("file_pattern")
        ), False
    elif tool_name == "task_complete":
        return args.get("summary", "Task completed."), True
    else:
        return f"Unknown tool: {tool_name}", False

def get_confirmation(tool_name: str, args: dict) -> bool:
    """Ask user for confirmation before executing a tool"""
    if AUTO_APPROVE_READS and tool_name in ["read_file", "list_directory", "search_files"]:
        return True
    
    print_colored("\n⚠️  Approve this action? [y/n/q]: ", Colors.YELLOW)
    response = input().strip().lower()
    if response == 'q':
        print_colored("Exiting...", Colors.RED)
        sys.exit(0)
    return response in ['y', 'yes', '']

def build_system_prompt() -> str:
    cwd = os.getcwd()
    return f"""You are a helpful coding assistant with access to tools for reading/writing files and running commands.

Current working directory: {cwd}

You have access to these tools:
- edit_file: Replace a unique block of text (Search & Replace)
- read_file: Read file contents
- write_file: Create or overwrite files
- list_directory: List files in a directory
- run_command: Execute shell commands
- search_files: Search for patterns in files (grep)
- task_complete: Call when done with the task

IMPORTANT INSTRUCTIONS:
1. When you need to use a tool, respond with a JSON block in this exact format:
```tool
{{"tool": "tool_name", "args": {{"param": "value"}}}}
```

2. You can include explanation text before or after the tool block.
3. Only call ONE tool at a time, then wait for the result.
4. After receiving tool results, continue working or call task_complete when done.
5. Always read relevant files before modifying them.
6. For coding tasks, make sure to test your changes if possible.
7. Use edit_file for small changes in large files instead of write_file. 
8. When using edit_file, ensure the 'old_content' matches EXACTLY what is in the file.

Example tool calls:
```tool
{{"tool": "list_directory", "args": {{"path": "."}}}}
```

```tool
{{"tool": "read_file", "args": {{"path": "main.py"}}}}
```

```tool
{{"tool": "run_command", "args": {{"command": "python test.py"}}}}
```

```tool
{{
  "tool": "edit_file", 
  "args": {{
    "path": "main.py",
    "old_content": "def hello():\\n    print('hi')",
    "new_content": "def hello():\\n    print('hello world')"
  }}
}}
"""

def parse_tool_call(response: str) -> Optional[tuple[str, dict]]:
    """Extract tool call from model response"""
    # Look for ```tool blocks
    pattern = r'```tool\s*\n?\s*(\{.*?\})\s*\n?```'
    matches = re.findall(pattern, response, re.DOTALL)
    
    if matches:
        try:
            data = json.loads(matches[0])
            return data.get("tool"), data.get("args", {})
        except json.JSONDecodeError:
            pass
    
    # Fallback: look for raw JSON with tool key
    pattern = r'\{\s*"tool"\s*:\s*"(\w+)"\s*,\s*"args"\s*:\s*(\{[^}]*\})\s*\}'
    match = re.search(pattern, response, re.DOTALL)
    if match:
        try:
            args = json.loads(match.group(2))
            return match.group(1), args
        except json.JSONDecodeError:
            pass
    
    return None, None

def chat_with_ollama(messages: list) -> str:
    """Sendet Nachrichten an Ollama mit Streaming-Support"""
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": MODEL,
                "messages": messages,
                "stream": True,  # Streaming aktivieren
                "options": {"num_ctx": MAX_CONTEXT_TOKENS}
            },
            timeout=120,
            stream=True
        )
        response.raise_for_status()
        
        full_content = ""
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                if "message" in chunk and "content" in chunk["message"]:
                    content = chunk["message"]["content"]
                    full_content += content
                    # Wir drucken den Content direkt aus (ohne Zeilenumbruch)
                    print(content, end="", flush=True)
        return full_content
    except Exception as e:
        print_colored(f"\n❌ Error: {e}", Colors.RED)
        sys.exit(1)

def agent_loop(user_input: str, messages: list) -> list:
    """Main agent loop - processes user input and executes tools"""
    messages.append({"role": "user", "content": user_input})
    
    max_iterations = 20
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        print_colored(f"\n{'─' * 50}", Colors.BLUE)
        print_colored(f"🤖 Thinking... (iteration {iteration})", Colors.MAGENTA)
        
        response = chat_with_ollama(messages)
        
        # Parse for tool calls
        tool_name, tool_args = parse_tool_call(response)
        
        if tool_name:
            # Print the model's explanation (text before/after tool call)
            explanation = re.sub(r'```tool\s*\n?\s*\{.*?\}\s*\n?```', '', response, flags=re.DOTALL).strip()
            if explanation:
                print_colored(f"\n💭 {explanation}", Colors.END)
            
            print_tool_call(tool_name, tool_args)
            
            # Get confirmation
            if not get_confirmation(tool_name, tool_args):
                print_colored("⏭️  Skipped", Colors.YELLOW)
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": "Tool execution was skipped by user. Please continue or try a different approach."})
                continue
            
            # Execute tool
            result, is_complete = execute_tool(tool_name, tool_args)
            print_tool_result(result)
            
            if is_complete:
                print_colored(f"\n✅ Task Complete: {result}", Colors.GREEN + Colors.BOLD)
                messages.append({"role": "assistant", "content": response})
                break
            
            # Add to conversation
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": f"Tool result:\n{result}\n\nContinue with the task or call task_complete if done."})
        else:
            # No tool call - just print response
            print_colored(f"\n💬 {response}", Colors.END)
            messages.append({"role": "assistant", "content": response})
            break
    
    if iteration >= max_iterations:
        print_colored("\n⚠️  Max iterations reached", Colors.YELLOW)
    
    return messages

def main():
    print_colored("""
╔═══════════════════════════════════════════════════════════════╗
║           🤖 Local Code Agent (Ollama Edition)                ║
║                                                               ║
║  Commands:                                                    ║
║    /clear  - Clear conversation history                       ║
║    /model  - Change model                                     ║
║    /cd     - Change working directory                         ║
║    /exit   - Exit the agent                                   ║
╚═══════════════════════════════════════════════════════════════╝
    """, Colors.CYAN + Colors.BOLD)
    
    print_colored(f"📂 Working directory: {os.getcwd()}", Colors.GREEN)
    print_colored(f"🧠 Model: {MODEL}", Colors.GREEN)
    print_colored(f"🔗 Ollama URL: {OLLAMA_URL}\n", Colors.GREEN)
    
    # Initialize conversation
    messages = [{"role": "system", "content": build_system_prompt()}]
    
    while True:
        try:
            print_colored("\n" + "═" * 60, Colors.BLUE)
            user_input = input(f"{Colors.BOLD}You:{Colors.END} ").strip()
            
            if not user_input:
                continue
            
            # Handle commands
            if user_input.startswith('/'):
                cmd = user_input.lower().split()[0]
                if cmd == '/exit':
                    print_colored("👋 Goodbye!", Colors.CYAN)
                    break
                elif cmd == '/clear':
                    messages = [{"role": "system", "content": build_system_prompt()}]
                    print_colored("🗑️  Conversation cleared", Colors.GREEN)
                    continue
                elif cmd == '/model':
                    parts = user_input.split(maxsplit=1)
                    if len(parts) > 1:
                        global MODEL
                        MODEL = parts[1]
                        print_colored(f"🧠 Model changed to: {MODEL}", Colors.GREEN)
                    else:
                        print_colored(f"Current model: {MODEL}", Colors.GREEN)
                        print_colored("Usage: /model <model_name>", Colors.YELLOW)
                    continue
                elif cmd == '/cd':
                    parts = user_input.split(maxsplit=1)
                    if len(parts) > 1:
                        try:
                            os.chdir(os.path.expanduser(parts[1]))
                            messages = [{"role": "system", "content": build_system_prompt()}]
                            print_colored(f"📂 Changed to: {os.getcwd()}", Colors.GREEN)
                        except Exception as e:
                            print_colored(f"Error: {e}", Colors.RED)
                    else:
                        print_colored(f"Current directory: {os.getcwd()}", Colors.GREEN)
                    continue
                else:
                    print_colored(f"Unknown command: {cmd}", Colors.RED)
                    continue
            
            # Run agent loop
            messages = agent_loop(user_input, messages)
            
        except KeyboardInterrupt:
            print_colored("\n\n👋 Interrupted. Goodbye!", Colors.CYAN)
            break
        except EOFError:
            break

if __name__ == "__main__":
    main()
