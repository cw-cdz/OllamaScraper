#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Merge official and community Ollama model catalogs into a single combined file.

This script reads separate JSON files for official and community models,
merges them, and preserves metadata from both sources.

Usage:
    ./merge_catalogs.py                  # Use default paths
    ./merge_catalogs.py --official path --community path --output path

Output Structure:
    {
        "scraped_at": "most_recent_completed_at_timestamp",
        "sources": {
            "official": {...metadata...},
            "community": {...metadata...}
        },
        "total_models": 182,
        "models": [{...model with 'source' field...}]
    }
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


def load_catalog(file_path: Path) -> Optional[Dict[str, Any]]:
    """Load a catalog JSON file.

    Args:
        file_path: Path to the JSON file

    Returns:
        Parsed JSON data or None if file doesn't exist or is invalid
    """
    if not file_path.exists():
        print(f"Warning: {file_path} not found, skipping")
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error parsing {file_path}: {e}")
        return None
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None


def merge_catalogs(
    official_data: Optional[Dict[str, Any]],
    community_data: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Merge official and community catalogs.

    Args:
        official_data: Official catalog data (or None)
        community_data: Community catalog data (or None)

    Returns:
        Merged catalog with combined models and metadata
    """
    # Initialize merged data
    merged_models: List[Dict[str, Any]] = []
    sources: Dict[str, Dict[str, Any]] = {}

    # Add official models
    if official_data:
        official_models = official_data.get('models', [])
        # Tag each model with source
        for model in official_models:
            model['source'] = 'official'
        merged_models.extend(official_models)

        sources['official'] = {
            'scraped_at': official_data.get('scraped_at'),
            'completed_at': official_data.get('completed_at'),
            'duration_seconds': official_data.get('duration_seconds'),
            'model_count': len(official_models)
        }

    # Add community models
    if community_data:
        community_models = community_data.get('models', [])
        # Tag each model with source
        for model in community_models:
            model['source'] = 'community'
        merged_models.extend(community_models)

        sources['community'] = {
            'scraped_at': community_data.get('scraped_at'),
            'completed_at': community_data.get('completed_at'),
            'duration_seconds': community_data.get('duration_seconds'),
            'model_count': len(community_models)
        }

    # Determine most recent scrape time (use most recent completed_at)
    scrape_times = []
    if official_data and official_data.get('completed_at'):
        scrape_times.append(official_data['completed_at'])
    if community_data and community_data.get('completed_at'):
        scrape_times.append(community_data['completed_at'])

    most_recent_scrape = max(scrape_times) if scrape_times else datetime.utcnow().isoformat() + '+00:00'

    # Build merged catalog
    merged = {
        'scraped_at': most_recent_scrape,
        'sources': sources,
        'total_models': len(merged_models),
        'models': merged_models
    }

    return merged


def main(
    official_path: str = 'out/ollama_models_official.json',
    community_path: str = 'out/ollama_models_community.json',
    output_path: str = 'out/ollama_models.json'
) -> int:
    """Main merge function.

    Args:
        official_path: Path to official models JSON
        community_path: Path to community models JSON
        output_path: Path for merged output JSON

    Returns:
        Exit code (0 for success, 1 for error)
    """
    print("Merging Ollama model catalogs...")

    # Load catalogs
    official_data = load_catalog(Path(official_path))
    community_data = load_catalog(Path(community_path))

    # Check if we have at least one valid catalog
    if not official_data and not community_data:
        print("Error: No valid catalog files found!")
        return 1

    # Merge
    merged = merge_catalogs(official_data, community_data)

    # Write output
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    # Print summary
    print(f"✓ Merged catalog written to {output_path}")
    print(f"  Total models: {merged['total_models']}")
    if 'official' in merged['sources']:
        print(f"  Official: {merged['sources']['official']['model_count']} models")
    if 'community' in merged['sources']:
        print(f"  Community: {merged['sources']['community']['model_count']} models")

    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Merge official and community Ollama model catalogs'
    )
    parser.add_argument(
        '--official',
        default='out/ollama_models_official.json',
        help='Path to official models JSON (default: out/ollama_models_official.json)'
    )
    parser.add_argument(
        '--community',
        default='out/ollama_models_community.json',
        help='Path to community models JSON (default: out/ollama_models_community.json)'
    )
    parser.add_argument(
        '--output',
        default='out/ollama_models.json',
        help='Path for merged output JSON (default: out/ollama_models.json)'
    )

    args = parser.parse_args()
    exit(main(args.official, args.community, args.output))
