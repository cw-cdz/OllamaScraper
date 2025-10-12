#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "beautifulsoup4>=4.12.3",
#   "httpx>=0.27.0",
#   "lxml>=5.2.1",
#   "rich>=13.7.0",
#   "tenacity>=8.2.3",
# ]
# ///
"""Ollama model catalog scraper.

Workflow:
1. Fetch https://ollama.com/search -> extract model slugs + high level capability badges & headline blurb & pulls summary.
2. For each model slug X:
   - Fetch https://ollama.com/library/{slug} -> extract description (Readme intro), total downloads, capability chips (tools / thinking / vision / embedding / etc.).
   - Fetch https://ollama.com/library/{slug}/tags -> extract table rows: tag name, size, context, input type (if present).
3. Aggregate into structured JSON and write to out/ollama_models.json.

Notes:
- We keep network polite (small concurrency) and retry transient failures.
- HTML structure may change; parsing uses defensive heuristics.
- No authentication; only public pages.

Output schema (JSON):
{
  "scraped_at": iso8601,
  "models": [
	 {
	   "slug": str,
	   "name": str,                # Display name if different from slug
	   "pulls": int | null,         # Total downloads (approx numeric) if parseable
	   "pulls_text": str | null,    # Original textual representation
	   "capabilities": [str],       # e.g. ["tools","thinking","vision"]
	   "blurb": str | null,         # Short one-line from search card
	   "description": str | null,   # Longer description/README intro
	   "updated": str | null,       # Relative or absolute text (as shown)
	   "tags_count": int | null,    # Number of tag variants listed on tags page
	   "variants": [
		  {
			"tag": str,             # e.g. "llama3:8b-instruct-q4_0"
			"size_bytes": int | null,
			"size_text": str,       # e.g. "4.7GB"
			"context": str | null,  # e.g. "8K"
			"input": str | null     # e.g. "Text" or other modality
		  }, ...
	   ]
	 }
  ]
}
"""
from __future__ import annotations
import re
import json
import asyncio
import httpx
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential
from typing import List, Dict, Any, Optional
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
from rich.console import Console
from rich.table import Table

BASE = "https://ollama.com"
SEARCH_URL = f"{BASE}/search"
LIB_URL = f"{BASE}/library/{{slug}}"
TAGS_URL = f"{BASE}/library/{{slug}}/tags"

console = Console()

CAPABILITY_KEYWORDS = {"tools","thinking","vision","embedding","multimodal","reasoning"}
SIZE_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([KMG]B)")
PULLS_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([KMB])?\s*Pulls", re.IGNORECASE)
NUM_ABBR = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}

@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=0.75, min=0.5, max=6))
async def fetch(client: httpx.AsyncClient, url: str) -> str:
	resp = await client.get(url, timeout=30)
	resp.raise_for_status()
	return resp.text

def filter_by_mode(slug: str, mode: str) -> bool:
	"""Filter slugs based on mode.

	Args:
		slug: Model slug (e.g., 'llama3' or 'user/model')
		mode: 'official', 'community', or 'all'

	Returns:
		True if slug should be included, False otherwise
	"""
	has_slash = '/' in slug
	if mode == 'official':
		return not has_slash
	elif mode == 'community':
		return has_slash
	elif mode == 'all':
		return True
	return False

def parse_search(html: str, mode: str = 'official') -> List[Dict[str, Any]]:
	soup = BeautifulSoup(html, 'lxml')
	out = []
	for a in soup.select('a[href^="/library/"]'):
		href = a.get('href','')
		slug = href.split('/library/')[-1].strip()
		if not slug or not filter_by_mode(slug, mode):
			continue
		if any(m['slug'] == slug for m in out):  # dedupe
			continue
		text = ' '.join(a.get_text(' ').split())
		capabilities = sorted({w.lower() for w in text.split() if w.lower() in CAPABILITY_KEYWORDS})
		pulls_match = PULLS_RE.search(text)
		pulls_val = None
		pulls_text = None
		if pulls_match:
			pulls_text = pulls_match.group(0)
			num = float(pulls_match.group(1))
			abbr = pulls_match.group(2)
			if abbr:
				num *= NUM_ABBR.get(abbr.upper(), 1)
			pulls_val = int(num)
		blurb = text
		if pulls_match:
			blurb = blurb.replace(pulls_match.group(0), '').strip()
		for c in capabilities:
			blurb = re.sub(rf"\b{re.escape(c)}\b", '', blurb, flags=re.IGNORECASE)
		blurb = ' '.join(blurb.split())
		out.append({
			'slug': slug,
			'capabilities': capabilities,
			'pulls': pulls_val,
			'pulls_text': pulls_text,
			'blurb': blurb or None,
		})
	return out

def parse_library(html: str, model: Dict[str, Any]) -> None:
	soup = BeautifulSoup(html, 'lxml')
	title = soup.find(['h1','h2'])
	if title:
		model['name'] = ' '.join(title.get_text(' ').split())
	text_all = soup.get_text(' ')
	dl_match = re.search(r"([0-9]+(?:\.[0-9]+)?)([KMB])?\s*Downloads", text_all, re.IGNORECASE)
	if dl_match:
		num = float(dl_match.group(1))
		abbr = dl_match.group(2)
		if abbr:
			num *= NUM_ABBR.get(abbr.upper(), 1)
		model['pulls'] = int(num)
		model['pulls_text'] = dl_match.group(0)
	caps_found = set(model.get('capabilities', []))
	for kw in CAPABILITY_KEYWORDS:
		if re.search(rf"\b{re.escape(kw)}\b", text_all, re.IGNORECASE):
			caps_found.add(kw)
	model['capabilities'] = sorted(caps_found)
	readme = soup.find(id=re.compile('readme', re.IGNORECASE))
	if readme:
		desc = ' '.join(readme.get_text(' ').split())
		model['description'] = desc[:2000]
	else:
		meta = soup.find('meta', attrs={'name':'description'})
		if meta and meta.get('content'):
			model['description'] = meta['content'][:2000]

def parse_tags(html: str, model: Dict[str, Any]) -> None:
	soup = BeautifulSoup(html, 'lxml')
	variants = []
	for a in soup.select('a[href*=":"]'):
		href = a.get('href','')
		if '/library/' not in href:
			continue
		tag_full = href.split('/library/')[-1]
		if not tag_full.startswith(model['slug'] + ':'):
			continue
		parent_txt = ' '.join(a.parent.get_text(' ').split()) if a.parent else ''
		size_match = SIZE_RE.search(parent_txt)
		size_text = size_match.group(0) if size_match else None
		size_bytes = None
		if size_match:
			num = float(size_match.group(1))
			unit = size_match.group(2)
			mult = {'KB': 1024, 'MB': 1024**2, 'GB': 1024**3}.get(unit.upper(), 1)
			size_bytes = int(num * mult)
		ctx_match = re.search(r"\b(\d+(?:\.?\d+)?K)\b", parent_txt)
		context = ctx_match.group(1) if ctx_match else None
		input_match = re.search(r"\b(Text|Vision|Audio|Image)\b", parent_txt, re.IGNORECASE)
		input_type = input_match.group(1).capitalize() if input_match else None
		variants.append({
			'tag': tag_full,
			'size_text': size_text,
			'size_bytes': size_bytes,
			'context': context,
			'input': input_type,
		})
	seen = set()
	deduped = []
	for v in variants:
		if v['tag'] in seen:
			continue
		seen.add(v['tag'])
		deduped.append(v)
	model['variants'] = deduped
	model['tags_count'] = len(deduped)

def get_output_path(mode: str, custom_out: Optional[str]) -> str:
	"""Determine output path based on mode and custom override.

	Args:
		mode: 'official', 'community', or 'all'
		custom_out: Custom output path (overrides mode-based naming)

	Returns:
		Output file path
	"""
	if custom_out:
		return custom_out

	if mode == 'official':
		return 'out/ollama_models_official.json'
	elif mode == 'community':
		return 'out/ollama_models_community.json'
	else:
		return 'out/ollama_models.json'

async def scrape_model(client: httpx.AsyncClient, base_info: Dict[str, Any]) -> Dict[str, Any]:
	slug = base_info['slug']
	model = dict(base_info)
	try:
		lib_html, tags_html = await asyncio.gather(
			fetch(client, LIB_URL.format(slug=slug)),
			fetch(client, TAGS_URL.format(slug=slug)),
		)
		parse_library(lib_html, model)
		parse_tags(tags_html, model)
	except Exception as e:  # noqa
		model['error'] = str(e)
	return model

async def scrape_with_mode(
	mode: str,
	limit: Optional[int],
	out_path: Optional[str]
):
	"""Run scraping for a specific mode."""
	start_time = datetime.now(timezone.utc)

	async with httpx.AsyncClient(headers={'User-Agent': 'Mozilla/5.0 (compatible; OllamaScraper/1.0)'}) as client:
		search_html = await fetch(client, SEARCH_URL)
		base_models = parse_search(search_html, mode)
		if limit:
			base_models = base_models[:limit]
		console.log(f"[{mode}] Discovered {len(base_models)} model slugs")
		results: List[Dict[str, Any]] = []
		sem = asyncio.Semaphore(6)
		progress = Progress(SpinnerColumn(), *Progress.get_default_columns(), TimeElapsedColumn(), transient=True)
		task_id = progress.add_task(f"[{mode}] Scraping models", total=len(base_models))
		progress.start()
		try:
			async def worker(info: Dict[str, Any]):
				async with sem:
					m = await scrape_model(client, info)
					results.append(m)
					progress.advance(task_id)
			await asyncio.gather(*(worker(m) for m in base_models))
		finally:
			progress.stop()

	results.sort(key=lambda x: (-(x.get('pulls') or 0), x['slug']))

	end_time = datetime.now(timezone.utc)
	duration_seconds = (end_time - start_time).total_seconds()

	data = {
		'scraped_at': start_time.isoformat(),
		'completed_at': end_time.isoformat(),
		'duration_seconds': round(duration_seconds, 2),
		'model_type': mode,
		'models': results,
	}

	output_file = get_output_path(mode, out_path)
	import os
	os.makedirs(os.path.dirname(output_file), exist_ok=True)
	with open(output_file, 'w', encoding='utf-8') as f:
		json.dump(data, f, ensure_ascii=False, indent=2)

	console.log(f"[bold green]Scrape completed in {duration_seconds:.1f}s[/bold green]")
	console.log(f"Mode: {mode}")
	console.log(f"Wrote {output_file} with {len(results)} models")

	table = Table(title=f"Ollama Models - {mode.capitalize()} (top 20 by pulls)")
	table.add_column("Slug")
	table.add_column("Pulls", justify="right")
	table.add_column("Caps")
	table.add_column("Variants", justify="right")
	for m in results[:20]:
		table.add_row(m['slug'], str(m.get('pulls') or ''), ','.join(m.get('capabilities', [])), str(m.get('tags_count') or 0))
	console.print(table)

async def main(
	limit: Optional[int] = None,
	mode: str = 'official',
	out_path: Optional[str] = None
):
	if mode == 'all':
		# Run official scrape
		console.log("[bold cyan]Running official models scrape...[/bold cyan]")
		await scrape_with_mode('official', limit, None)

		# Run community scrape
		console.log("[bold cyan]Running community models scrape...[/bold cyan]")
		await scrape_with_mode('community', limit, None)

		console.log("[bold green]Both scrapes completed![/bold green]")
		return

	# Single mode scraping
	await scrape_with_mode(mode, limit, out_path)

if __name__ == '__main__':
	import argparse
	p = argparse.ArgumentParser(
		description='Scrape Ollama model library with official/community filtering'
	)
	p.add_argument(
		'--limit',
		type=int,
		help='Limit number of models for quick test'
	)
	p.add_argument(
		'--mode',
		choices=['official', 'community', 'all'],
		default='official',
		help='Scraping mode: official (no slash), community (has slash), or all (both)'
	)
	p.add_argument(
		'--out',
		help='Custom output path (ignored if mode=all)'
	)
	args = p.parse_args()

	# Validate: mode=all conflicts with custom output
	if args.mode == 'all' and args.out:
		console.print("[yellow]Warning: --out ignored when --mode=all (generates both default files)[/yellow]")
		args.out = None

	asyncio.run(main(limit=args.limit, mode=args.mode, out_path=args.out))
