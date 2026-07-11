# Algebra-Problem-Solver-With-Manim
A tool translating algebra problems to Manim videos using natural languages.

## Introduction 

  It`s a tool using AI to solve and generate JSON descriptions, which can be used to render aligned videos.
This tool only requires LLM API keys.

## effects
  <img width="554" height="391" alt="屏幕截图 2026-07-10 132356" src="https://github.com/user-attachments/assets/d26bd947-45a6-4d6c-9664-2cb26bb7a88b" />

  
https://github.com/user-attachments/assets/3c715cea-8a92-4938-8d22-0535588f53cc

## Somethings can be imporved further
  Generation might be too slow, and the tool is in a early version.
  But the author may not have enough time to imporve it.

## License & Dependency Statement
  This project code is released under the MIT License (see LICENSE file).
  Core dependency: Manim Community Edition (manim-ce), which is distributed under the MIT License.
  This project only calls Manim as a third-party library, does not modify the source code of Manim.

## Install 
  ```bush
`# Clone repo
git clone https://github.com/wrlca/Algebra-Problem-Solver-With-Manim.git
cd Algebra-Problem-Solver-With-Manim

# Install dependencies
pip install -r requirements.txt
```
The LaTex will be installed too.

# Quick Start Example

## Program Overview
Script name: `main.py`
This Manim math animation tool has 3 independent operating modes controlled by CLI arguments:
1. AI JSON Generation Mode: Read math problems from `.txt`/`.md`, call local LLM (Ollama / llama.cpp) to generate standardized animation JSON config. System prompt loads externally from `proptm.txt`. PDF file support removed.
2. Video Render Mode: Read JSON config, auto draw function graphs, moving points & algebra animations, export MP4 video.
3. Script Export Mode: Split every graph step into standalone `.py` Manim files to avoid layer overlay bugs.

### Local LLM Choice (Required for AI generation)
#### Option 1: Ollama (Recommended)
1. Install Ollama official client
2. Pull model: `ollama pull qwen2:7b`
3. Default API address: `http://127.0.0.1:11434`

#### Option 2: llama.cpp
1. Compile llama.cpp server
2. Run server, default address: `http://127.0.0.1:8080`

#### Online LLMs

To call online cloud LLM APIs (OpenAI, DeepSeek, GLM, Tongyi, remote Ollama/llama.cpp deployed on cloud servers), we only need to pass 2 extra CLI arguments:
--ai-endpoint: Full online API base URL (must end with /v1)
The script uses standard OpenAI-compatible chat endpoint /v1/chat/completions which all mainstream online LLMs support.
Supported Online LLM Types
Official commercial APIs: OpenAI, DeepSeek, Zhipu GLM, Ali Tongyi, Qwen Dashscope
Self-hosted cloud remote LLM: Ollama / llama.cpp running on cloud VPS
Third-party proxy OpenAI-compatible gateways

Key Rule
All online cloud LLMs share the same request format as Ollama’s OpenAI-compatible /v1 interface, so set --ai-backend ollama unconditionally when calling online services.

##### Standard Template for Online API Command
```bush
python main.py \
--ai-generate \
--input-file math_problem.txt \
--output-json render_config.json \
--ai-backend ollama \
--ai-model "MODEL_NAME_FROM_PROVIDER" \
--ai-endpoint "https://YOUR_ONLINE_API_DOMAIN/v1"
```

##### Example 
```bush
python main.py --ai-generate --input-file problem.txt --ai-backend ollama --ai-model gpt-4o-mini --ai-endpoint https://api.openai.com/v1
```

### proptm.txt Note
- Stores strict JSON generation rules for AI
- If missing or unreadable, program loads a minimal fallback prompt automatically (no crash)
- Edit with any text editor, changes take effect after restarting the script

## Step 3 All CLI Arguments Full Reference
Run help command to view all parameters:
```bash
python main.py -h
```
### Global Mode Priority Rule
1. If `--ai-generate` exists → ONLY run AI JSON generation, skip rendering/export
2. If no `--ai-generate` but `--export` exists → ONLY export separate Manim scripts
3. No above flags → Default: Render MP4 video from input JSON

### 1. AI Generation Mode Flags
| Flag | Required | Description |
|------|----------|-------------|
| `--ai-generate` | Yes | Enable AI generation mode (main switch) |
| `--input-file` | Yes | Path of math problem file, only `.txt` / `.md` supported (PDF removed) |
| `--output-json` | No | Output JSON path, default `generated.json` |
| `--ai-backend` | No | LLM backend, choices `ollama` / `llamacpp`, default `ollama` |
| `--ai-model` | No | LLM model name, default `qwen2:7b` |
| `--ai-endpoint` | No | Custom LLM API URL, override default local address |

#### Example 1: Default Ollama (Simplest Command)
```bash
python main.py --ai-generate --input-file problem.txt
```
Logic: Load `proptm.txt` → Send problem text to local Ollama → Save output as `generated.json`

#### Example 2: Custom output JSON name
```bash
python main.py --ai-generate --input-file math.md --output-script.json
```

#### Example 3: Switch LLM model
```bash
python main.py --ai-generate --input-file problem.txt --ai-model qwen2.5:14b
```

#### Example 4: Use llama.cpp local server
```bash
python main.py --ai-generate --input-file problem.txt --ai-backend llamacpp --ai-endpoint http://127.0.0.1:8080
```

#### Example 5: Remote LAN Ollama server
```bash
python main.py --ai-generate --input-file problem.txt --ai-endpoint http://192.168.1.200:11434
```

### 2. Video Render Mode Flags
Positional argument (first value): `json_file` (path of animation JSON, mandatory)
Optional render control flags:
| Short | Long Flag | Values | Function |
|-------|-----------|--------|----------|
| `-p` | `--performance` | `quality` / `balanced` / `speed` / `ultra_fast` | Render precision preset, default `balanced` |
| `-q` | `--quality` | `low_quality` / `medium_quality` / `high_quality` / `fourk_quality` | Video resolution setting |
| N/A | `--no-hw-accel` | Boolean switch | Disable NVIDIA hardware encoding (fix Windows GPU crash)

#### Example 1: Standard balanced render (Most Used)
```bash
python main.py output.json
```

#### Example 2: High precision 1080p demo video
```bash
python main.py output.json -p quality -q high_quality
```

#### Example 3: Ultra-fast low-res preview for debugging
```bash
python main.py output.json -p ultra_fast -q low_quality
```

#### Example 4: Disable GPU hardware acceleration
```bash
python main.py output.json --no-hw-accel
```

### 3. Script Export Mode Flags
| Flag | Description |
|------|-------------|
| `--export` | Enable separate script export mode |
| `--export-dir` | Custom output folder name, default `export_manim` |

#### Example 1: Default export folder
```bash
python main.py output.json --export
```
After execution, folder `export_manim` is created, each graph step becomes an independent `.py` Manim file.

#### Example 2: Custom export directory
```bash
python main.py output.json --export --export-dir step_animations
```

## Full End-to-End Workflow Example
### Step 1 Generate JSON from math problem text
```bash
python main.py --ai-generate --input-file problem.txt --output result.json
```
### Step 2 Render animation MP4 video
```bash
python main.py result.json -p balanced -q high_quality
```
### Optional Step 3 Export split Manim scripts
```bash
python main.py result.json --export
```

## Common Error Troubleshooting
1. `ModuleNotFoundError: requests`
Run install command: `pip install requests`
2. LaTeX formula rendering broken
Install complete TeXLive / MiKTeX environment
3. AI API timeout
Check if Ollama/llama.cpp server is running on matching port
4. AI generates invalid JSON syntax
Edit `proptm.txt` to tighten format rules, lower model temperature
5. Function graph shows blank screen
Check `x_range` in JSON covers function valid domain, use `**` instead of `^` for powers
6. Graph overlaps and does not clear
Set `"fade_out": true` and `"clear_graph": true` inside each `graph_step` object in JSON
7. Unsupported input file extension
Only `.txt` and `.md` are allowed; PDF support removed permanently
