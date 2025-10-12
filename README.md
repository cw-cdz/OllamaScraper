# Ollama Model Scraper

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python-based asynchronous web scraper to fetch and catalog all available models from the [Ollama](https://ollama.com) model library.

This tool systematically gathers information from the Ollama website, including model descriptions, capabilities, pull counts, and detailed variant tags (size, context length, etc.), and aggregates it into a single, structured JSON file.

## Features

- **Asynchronous Scraping**: Uses `httpx` and `asyncio` for fast, non-blocking network requests.
- **Robust & Polite**: Implements exponential backoff and retries with `tenacity` to handle transient network errors gracefully.
- **Rich CLI Output**: Displays a progress bar during scraping and a summary table of the top models upon completion, powered by `rich`.
- **Structured JSON Output**: Saves all scraped data in a clean, well-defined JSON format for easy use in other applications.
- **Comprehensive Data**: Captures a wide range of data points:
  - Model name, slug, and blurb
  - Total pull counts
  - Auto-detected capabilities (e.g., `vision`, `tools`, `embedding`)
  - Full model description (from README)
  - A complete list of variants/tags with size, context length, and input modality.

## Prerequisites

- Python 3.11+
- UV package manager

## Installation

This script uses UV and PEP 723 for dependency management. No separate installation or virtual environment needed!

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/chrizzo84/OllamaScraper.git
    cd OllamaScraper
    ```

2.  **Install UV (if not already installed):**
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

3.  **Make the script executable (one time only):**
    ```bash
    chmod +x ollama_scraper.py
    ```

That's it! UV will automatically handle all dependencies when you run the script.

## Usage

Run the scraper from the command line. The output will be saved to `out/ollama_models.json` by default.

**Run directly (recommended):**
```bash
./ollama_scraper.py
```

**Or using UV explicitly:**
```bash
uv run ollama_scraper.py
```

### Command-line Options

-   `--limit <N>`: Limit the number of models to scrape (useful for quick tests).
    ```bash
    ./ollama_scraper.py --limit 10
    ```
-   `--out <PATH>`: Specify a custom output file path.
    ```bash
    ./ollama_scraper.py --out data/models.json
    ```

## Accessing the Data

The model data is automatically updated daily via a GitHub Actions workflow. The latest version is always available in the `out/ollama_models.json` file in this repository.

You can access the raw JSON file directly for use in your own applications via the following URL:

```
https://raw.githubusercontent.com/chrizzo84/OllamaScraper/refs/heads/main/out/ollama_models.json
```


## Output Schema

The output JSON file has the following structure:

```json
{
  "scraped_at": "iso8601-timestamp",
  "models": [
    {
      "slug": "str",
      "name": "str",
      "pulls": "int | null",
      "pulls_text": "str | null",
      "capabilities": ["str"],
      "blurb": "str | null",
      "description": "str | null",
      "updated": "str | null",
      "tags_count": "int | null",
      "variants": [
        {
          "tag": "str",
          "size_bytes": "int | null",
          "size_text": "str",
          "context": "str | null",
          "input": "str | null"
        }
      ]
    }
  ]
}
```

## License

This project is licensed under the MIT License. See the LICENSE.md file for details.