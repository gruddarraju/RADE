# RADE Transcript Crawler & Summarizer

Automated tool to extract video transcripts from the Data Engineering Hub platform and generate summarized Word documents using a local LLM.

## How It Works

```
┌─────────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  crawl_transcripts  │────▶│   transcripts/   │────▶│  summarize_to_docx  │
│    (Playwright)     │     │   (.txt files)   │     │   (Ollama + docx)   │
└─────────────────────┘     └──────────────────┘     └─────────────────────┘
         │                                                      │
         ▼                                                      ▼
   Logs into DEH                                         output/
   Auto-discovers courses                                (.docx summaries)
   Extracts transcripts
```

## Prerequisites

- **Python 3.9+**
- **Ollama** — Local LLM runtime ([install guide](https://ollama.com/download))
- A Data Engineering Hub account (email/password login)

## Setup

### 1. Install Python dependencies

```powershell
cd learning\scripts
pip install -r requirements.txt
```

### 2. Install Playwright browsers

```powershell
playwright install chromium
```

### 3. Install and start Ollama

Download from https://ollama.com/download, then pull a model:

```powershell
ollama pull llama3
```

### 4. Configure credentials

Edit `config.yaml` and fill in your email and password:

```yaml
credentials:
  email: "your-email@example.com"
  password: "your-actual-password"
```

> **Security**: `config.yaml` is in `.gitignore` and will NOT be committed. Never share this file.

## Usage

### Step 1: Crawl transcripts

Extract transcripts from all courses:

```powershell
python crawl_transcripts.py --config config.yaml
```

Extract from a specific course only:

```powershell
python crawl_transcripts.py --config config.yaml --course "Success Blueprint"
```

Run in headless mode (no browser window):

```powershell
python crawl_transcripts.py --config config.yaml --headless
```

Options:
| Flag | Default | Description |
|------|---------|-------------|
| `--config` | `config.yaml` | Path to config file |
| `--course` | All courses | Filter by course name (partial match) |
| `--headless` | `false` | Run browser without visible window |
| `--delay` | `2.0` | Seconds between page loads |

### Step 2: Generate Word summaries

Summarize all crawled transcripts:

```powershell
python summarize_to_docx.py --config config.yaml
```

Summarize a specific course:

```powershell
python summarize_to_docx.py --config config.yaml --course "rade-success-blueprint"
```

Use a different model:

```powershell
python summarize_to_docx.py --config config.yaml --model mistral
```

Options:
| Flag | Default | Description |
|------|---------|-------------|
| `--config` | `config.yaml` | Path to config file |
| `--course` | All courses | Filter by course folder name |
| `--model` | From config (`llama3`) | Override Ollama model |

## Output Structure

```
learning/
├── scripts/
│   ├── crawl_transcripts.py
│   ├── summarize_to_docx.py
│   ├── config.yaml            (your credentials - gitignored)
│   ├── config.yaml.example    (reference template)
│   ├── requirements.txt
│   └── README.md              (this file)
├── phase1-starter/
│   ├── 01-rade-success-blueprint/
│   │   └── transcripts/       (generated here)
│   │       ├── 01-welcome-to-deh.txt
│   │       ├── 02-how-the-program-works.txt
│   │       └── ...
│   ├── 02-unix-and-cloud-foundations/
│   │   └── transcripts/
│   │       └── ...
│   └── ...
├── phase2-applied-mastery/
│   └── track-a-spark/
│       └── 01-apache-spark-and-emr/
│           └── transcripts/
│               └── ...
└── output/                    (generated Word docs)
    ├── rade-success-blueprint-summary.docx
    └── unix-and-cloud-foundations-summary.docx
```

Transcripts are saved directly inside each module's folder (under a `transcripts/` subfolder), keeping everything co-located with the relevant course material.

## Supported Ollama Models

Any model available on Ollama works. Recommended options:

| Model | Size | Best For |
|-------|------|----------|
| `llama3` | 4.7GB | Good balance of quality and speed |
| `llama3:70b` | 40GB | Highest quality (needs more RAM) |
| `mistral` | 4.1GB | Fast, good summaries |
| `gemma2` | 5.4GB | Strong comprehension |
| `phi3` | 2.3GB | Lightweight, faster on limited hardware |

## Troubleshooting

**Login fails:**
- Verify your email/password in `config.yaml`
- Try with `--headless` disabled (default) to watch the browser
- Check if the platform changed its login page structure

**No transcripts found:**
- Not all videos have transcripts enabled
- The platform may use different DOM structures for some courses
- Try running without `--headless` to observe what happens

**Ollama errors:**
- Ensure Ollama is running: `ollama serve`
- Ensure the model is pulled: `ollama pull llama3`
- Check if the model fits in your RAM

**Slow summarization:**
- Use a smaller model (`phi3` is fastest)
- Ensure you have enough RAM for the model
- GPU acceleration helps significantly if available
