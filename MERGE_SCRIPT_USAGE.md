# Merge Catalogs Script - Usage Guide

## Overview

`merge_catalogs.py` is a PEP 723 self-contained Python script that merges official and community Ollama model catalogs into a single combined JSON file.

**Location:** `/home/kasm-user/workspaces_tools/OllamaScraper/merge_catalogs.py`

## Features

- ✅ **PEP 723 compliant** - Self-contained with inline dependencies
- ✅ **Zero external dependencies** - Uses only Python stdlib
- ✅ **Graceful error handling** - Handles missing files, invalid JSON
- ✅ **Source tagging** - Each model tagged with `source: "official"|"community"`
- ✅ **Metadata preservation** - Keeps all scrape metadata from both sources
- ✅ **UV compatible** - Can be run with `uv run` or directly

## Basic Usage

### Default Paths
```bash
./merge_catalogs.py
```

Reads from:
- `out/ollama_models_official.json`
- `out/ollama_models_community.json`

Writes to:
- `out/ollama_models.json`

### Custom Paths
```bash
./merge_catalogs.py \
  --official path/to/official.json \
  --community path/to/community.json \
  --output path/to/merged.json
```

### Using UV
```bash
uv run merge_catalogs.py
```

## Output Structure

```json
{
  "scraped_at": "2025-10-11T06:01:30+00:00",
  "sources": {
    "official": {
      "scraped_at": "2025-10-11T05:00:00+00:00",
      "completed_at": "2025-10-11T05:00:25+00:00",
      "duration_seconds": 25.5,
      "model_count": 182
    },
    "community": {
      "scraped_at": "2025-10-11T06:00:00+00:00",
      "completed_at": "2025-10-11T06:01:30+00:00",
      "duration_seconds": 90.0,
      "model_count": 800
    }
  },
  "total_models": 982,
  "models": [
    {
      "slug": "llama3.1",
      "source": "official",
      "capabilities": ["tools", "reasoning"],
      ...
    },
    {
      "slug": "user/custom-model",
      "source": "community",
      ...
    }
  ]
}
```

## Merge Logic

### Timestamp Selection
The merged `scraped_at` field uses the **most recent** `completed_at` timestamp from either source.

### Model Arrays
- Official models are merged first
- Community models are appended
- Each model gets a `source` field added

### Metadata
All metadata from both sources is preserved in the `sources` object:
- `scraped_at` - When scraping started
- `completed_at` - When scraping finished
- `duration_seconds` - How long it took
- `model_count` - Number of models from this source

## GitHub Actions Integration

```yaml
- name: Merge catalogs
  run: ./merge_catalogs.py
```

Or with custom paths:
```yaml
- name: Merge catalogs
  run: |
    ./merge_catalogs.py \
      --official out/ollama_models_official.json \
      --community out/ollama_models_community.json \
      --output out/ollama_models.json
```

## Error Handling

### Missing Files
If one catalog is missing, the script continues with available data:
```
Warning: out/ollama_models_community.json not found, skipping
✓ Merged catalog written to out/ollama_models.json
  Total models: 182
  Official: 182 models
```

### No Valid Files
If both catalogs are missing, the script exits with error code 1:
```
Error: No valid catalog files found!
```

### Invalid JSON
If a file contains invalid JSON, it's skipped with a warning:
```
Error parsing out/ollama_models_official.json: Expecting value: line 1 column 1
```

## Examples

### View Merged Metadata
```bash
cat out/ollama_models.json | jq '{scraped_at, total_models, sources}'
```

### Count Models by Source
```bash
cat out/ollama_models.json | jq '[.models[].source] | group_by(.) | map({source: .[0], count: length})'
```

### List Official Models Only
```bash
cat out/ollama_models.json | jq '.models[] | select(.source == "official") | .slug'
```

### List Community Models Only
```bash
cat out/ollama_models.json | jq '.models[] | select(.source == "community") | .slug'
```

## Testing

### Verify Script Works
```bash
./merge_catalogs.py
echo $?  # Should print 0 for success
```

### Test with Mock Data
```bash
# Create test files
echo '{"scraped_at":"2025-10-11T05:00:00Z","completed_at":"2025-10-11T05:00:25Z","duration_seconds":25.5,"model_type":"official","models":[{"slug":"test1"}]}' > /tmp/test_official.json

echo '{"scraped_at":"2025-10-11T06:00:00Z","completed_at":"2025-10-11T06:01:30Z","duration_seconds":90,"model_type":"community","models":[{"slug":"test2"}]}' > /tmp/test_community.json

# Merge
./merge_catalogs.py \
  --official /tmp/test_official.json \
  --community /tmp/test_community.json \
  --output /tmp/test_merged.json

# Verify
cat /tmp/test_merged.json | jq '.'
```

## Development

### Requirements
- Python 3.11+
- No external dependencies

### Script Location
`/home/kasm-user/workspaces_tools/OllamaScraper/merge_catalogs.py`

### PEP 723 Metadata
```python
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
```

## Troubleshooting

### Permission Denied
```bash
chmod +x merge_catalogs.py
```

### Wrong Python Version
Check your Python version:
```bash
python3 --version  # Should be 3.11+
```

### UV Not Found
Install uv or run directly:
```bash
python3 merge_catalogs.py
```

## License

Same as parent project.
