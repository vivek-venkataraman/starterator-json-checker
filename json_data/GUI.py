# set phams_amount, cluster_size

from __future__ import annotations

from pathlib import Path
import json
from typing import Dict, List

import requests

# constants

# main website url
BASE_URL = "http://phages.wustl.edu/starterator/json/"

# locally stored JSON file location
OUTPUT_DIR = Path(__file__).parent / "json_data"

# pham_ids.txt written by fetch, contains pham numbers to all phams
PHAM_IDS_FILE = Path(__file__).parent / "pham_ids.txt"

# load pham #s from PHAM_IDS_FILE into memory
def load_pham_ids() -> list[int]:
    """Load pham IDs from PHAM_IDS_FILE (ignoring comments/blank lines)."""
    if not PHAM_IDS_FILE.exists():
        print(f"{PHAM_IDS_FILE} does not exist. Run fetch_pham_ids.py first.")
        return []

    ids: list[int] = []
    for line in PHAM_IDS_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            ids.append(int(line))
        except ValueError:
            print(f"WARNING: ignoring invalid line in {PHAM_IDS_FILE}: {line!r}")

    ids = sorted(set(ids))
    print(f"Loaded {len(ids)} pham IDs from {PHAM_IDS_FILE}")
    return ids


def get_pham_url(pham_id: int) -> str:
    """Return the JSON URL for a given pham."""
    return f"{BASE_URL}{pham_id}.json"


def download_pham_json(pham_id: int, force: bool = False) -> Path | None:
    """
    Ensure JSON for this pham is present locally in OUTPUT_DIR.

    - If it exists and force=False, just return the path.
    - Otherwise, download it from the server into OUTPUT_DIR.

    Returns the local Path if successful, else None.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)
    json_path = OUTPUT_DIR / f"{pham_id}.json"

    if json_path.exists() and not force:
        return json_path

    url = get_pham_url(pham_id)
    print(f"Downloading {url} ...")

    try:
        resp = requests.get(url, timeout=15)
    except requests.RequestException as e:
        print(f"  ERROR: could not download {url}: {e}")
        return None

    if resp.status_code != 200:
        print(f"  ERROR: server returned status {resp.status_code} for {url}")
        return None

    # Validate JSON before saving
    try:
        _ = resp.json()
    except json.JSONDecodeError as e:
        print(f"  ERROR: response from {url} was not valid JSON: {e}")
        return None

    json_path.write_text(resp.text, encoding="utf-8")
    print(f"  Saved to {json_path}")
    return json_path


def load_pham_json(path: Path) -> dict:
    """Load one pham JSON file and return the parsed dict."""
    with path.open(encoding="utf-8") as f:
        return json.load(f)



def update_all_local_jsons(pham_ids: list[int], *, force: bool = True) -> None:
    """
    Re-download JSON files for all given pham IDs into OUTPUT_DIR.

    called with "update local JSON files".
    """
    print(f"\nRefreshing JSON for {len(pham_ids)} phams (force={force})...")
    success = 0
    for pham_id in pham_ids:
        path = download_pham_json(pham_id, force=force)
        if path is not None:
            success += 1
    print(f"Finished refresh: {success}/{len(pham_ids)} phams downloaded successfully.\n")



def load_all_pham_data(pham_ids: list[int], use_network: bool) -> dict[int, dict]:
    """
    Load JSON data for all given pham IDs into memory at once.

    - If use_network=True: download (with caching) as needed.
    - If use_network=False: only read existing files from OUTPUT_DIR.

    Returns:
        dict mapping pham_id -> JSON data dict.
        Phams that fail to load are skipped (not included in the dict).
    """
    all_data: dict[int, dict] = {}
    total = len(pham_ids)
    print(f"\nLoading JSON data into memory for {total} phams (use_network={use_network})...")

    for idx, pham_id in enumerate(pham_ids, start=1):
        # Decide how to get the local JSON path
        if use_network:
            path = download_pham_json(pham_id)  # cached download
            if path is None:
                print(f"  Skipping pham {pham_id}: download failed.")
                continue
        else:
            path = OUTPUT_DIR / f"{pham_id}.json"
            if not path.exists():
                print(f"  Skipping pham {pham_id}: local file missing at {path}")
                continue

        # Load JSON into memory
        try:
            data = load_pham_json(path)
        except json.JSONDecodeError as e:
            print(f"  ERROR: {path} is not valid JSON for pham {pham_id}: {e}")
            continue

        all_data[pham_id] = data

        # progress indicator for large sets
        if idx % 100 == 0 or idx == total:
            print(f"  Loaded {idx}/{total} phams...")

    print(f"Done. Loaded JSON for {len(all_data)}/{total} phams into memory.\n")
    return all_data