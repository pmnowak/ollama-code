# Local Code Agent 🤖

A Claude Code-like CLI tool that runs locally using Ollama. It provides an agentic coding experience where the AI can read/write files, run commands, and help you with coding tasks.

## Features

- 📖 **Read files** - Examine existing code
- ✍️ **Write files** - Create or modify files
- 📁 **List directories** - Explore project structure
- 🔍 **Search files** - Grep through your codebase
- ⚡ **Run commands** - Execute shell commands (tests, git, etc.)
- 🔄 **Agent loop** - AI iterates until task is complete

## Requirements

- Python 3.8+
- Ollama running locally
- A coding model (qwen2.5-coder recommended)

## Quick Start

### 1. Install Ollama (if not already installed)

```bash
# macOS
brew install ollama

# Then start the server
ollama serve
```

### 2. Pull a coding model

```bash
# Recommended for 16GB RAM
ollama pull qwen2.5-coder:7b

# Alternatives
ollama pull deepseek-coder:6.7b
ollama pull codellama:7b
```

### 3. Run the agent

```bash
# Navigate to your project directory
cd /path/to/your/project

# Run the agent
python /path/to/agent.py
```

## Usage

Once running, just type what you want to do:

```
You: List all Python files in this directory

You: Read main.py and explain what it does

You: Create a new file called utils.py with a function to parse JSON

You: Run the tests

You: Find all places where "database" is mentioned in the code
```

## Commands

| Command | Description |
|---------|-------------|
| `/clear` | Clear conversation history |
| `/model <name>` | Switch to a different Ollama model |
| `/cd <path>` | Change working directory |
| `/exit` | Exit the agent |

## Configuration

Edit these variables at the top of `agent.py`:

```python
OLLAMA_URL = "http://localhost:11434"  # Ollama server URL
MODEL = "qwen2.5-coder:7b"             # Default model
MAX_CONTEXT_TOKENS = 8192              # Context window size
AUTO_APPROVE_READS = True              # Auto-approve read operations
```

## Safety

- **Write operations require confirmation** - You'll be asked before any file is written or command is run
- **Read operations are auto-approved** by default (configurable)
- **Press 'n' to skip** any operation you don't want to execute
- **Press 'q' to quit** immediately

## Tips for Best Results

1. **Start by exploring** - Ask the AI to list files and read key files first
2. **Be specific** - "Add error handling to the login function in auth.py" works better than "improve the code"
3. **Iterate** - The AI will run multiple steps, let it complete its loop
4. **Use a good model** - qwen2.5-coder:7b gives the best results for the RAM usage

## Model Recommendations by RAM

| RAM | Model | Notes |
|-----|-------|-------|
| 8GB | qwen2.5-coder:3b | Basic but functional |
| 16GB | qwen2.5-coder:7b | Sweet spot ✨ |
| 32GB | qwen2.5-coder:14b | Better reasoning |
| 64GB+ | qwen2.5-coder:32b | Best quality |

## Troubleshooting

**"Cannot connect to Ollama"**
- Make sure Ollama is running: `ollama serve`
- Check if the URL is correct (default: http://localhost:11434)

**"Model not found"**  
- Pull the model first: `ollama pull qwen2.5-coder:7b`
- List available models: `ollama list`

**Slow responses**
- This is normal for local LLMs, especially on first run
- Subsequent queries are faster due to model caching

**AI not using tools correctly**
- Some models handle the tool format better than others
- qwen2.5-coder and deepseek-coder work best
- Try being more explicit in your request

## License

MIT - Use it however you like!
