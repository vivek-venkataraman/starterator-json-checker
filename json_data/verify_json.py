from pathlib import Path
import json
import random

import requests  # install in your project env: pip install requests



url = "http://phages.wustl.edu/starterator/json/"

# Folder where JSON files are stored locally
output_dir = Path(__file__).parent / "json_data"

# pham_ids.txt written by your "fetch" script
pham_ids_file = Path(__file__).parent / "pham_ids.txt"

# amount of phams to sample
phams_amount: int | None = 50  # change this as you like

def load_pham_ids() -> list[int]:

    """Load pham IDs from pham_ids_file."""

    if not pham_ids_file.exists():
        print(f"{pham_ids_file} does not exist. Run fetch_pham_ids.py first.")
        return []

    ids: list[int] = []
    for line in pham_ids_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            ids.append(int(line))
        except ValueError:
            print(f"WARNING: ignoring invalid line in {pham_ids_file}: {line!r}")
    ids = sorted(set(ids))
    print(f"Loaded {len(ids)} pham IDs from {pham_ids_file}")
    return ids


# get jsons

def get_pham_url(pham_id: int):
    """makes URL given pham."""
    return "http://phages.wustl.edu/starterator/json/" + str(pham_id) + ".json"

# checks to see if json file is local

def download_pham_json(pham_id: int, force: bool = False) -> Path | None:
    """
    Ensure JSON for this pham is present locally.
    - If it exists and force=False, just return the path.
    - Otherwise, download it from the server into output_dir.

    Returns the local Path if successful, else None.
    """
    output_dir.mkdir(exist_ok=True)
    downloaded_json_path = output_dir / str((pham_id) + ".json")

    if downloaded_json_path.exists() and not force:
        return local_path

    url = get_pham_url(pham_id)
    print("Downloading" + str(url) + "...")
    try:
        resp = requests.get(url, timeout=15)
    except requests.RequestException as e:
        print(f"  ERROR: could not download {url}: {e}")
        return None

    if resp.status_code != 200:
        print(f"  ERROR: server returned status {resp.status_code} for {url}")
        return None

    try:
        _ = resp.json()  # validate JSON
    except json.JSONDecodeError as e:
        print(f"  ERROR: response from {url} was not valid JSON: {e}")
        return None

    local_path.write_text(resp.text, encoding="utf-8")
    print(f"  Saved to {local_path}")
    return local_path


def load_pham_json(path: Path) -> dict:
    """Load one pham JSON file and return the parsed dict."""
    with path.open() as f:
        return json.load(f)


# conservation calculations

def recompute_conservation(data: dict) -> dict:
    """
    Recompute conservation as:
        Conservation[start] = (# genes with that start in AvailableStarts) / MemberCount

    Returns a dict with string keys like the JSON: {"1": 0.2, "2": 0.8, ...}
    """
    member_count = data["MemberCount"]
    present_counts: dict[int, int] = {}

    # Count how many genes list each start in AvailableStarts
    for gene in data["Genes"]:
        for start_num in gene["AvailableStarts"]:
            present_counts[start_num] = present_counts.get(start_num, 0) + 1

    # Convert to fractions and string keys to match JSON format
    recomputed = {
        str(start_num): present_counts[start_num] / member_count
        for start_num in sorted(present_counts.keys())
    }
    return recomputed


def compare_conservation(data: dict, tol: float = 1e-6):
    """
    Compare JSON Conservation values with recomputed ones.

    Returns:
        (pham_name, mismatches)

    mismatches is a list of dicts like:
        {
            "start": "12",
            "issue": "value_mismatch",
            "json": 0.8,
            "recomputed": 1.0,
        }
    """
    pham_name = data.get("Name")
    json_cons: dict[str, float] = data["Conservation"]
    recomputed: dict[str, float] = recompute_conservation(data)

    mismatches = []
    all_keys = sorted(set(json_cons.keys()) | set(recomputed.keys()), key=int)

    for k in all_keys:
        jc = json_cons.get(k)
        rc = recomputed.get(k)

        if jc is None or rc is None:
            mismatches.append({
                "start": k,
                "issue": "missing_in_one_side",
                "json": jc,
                "recomputed": rc,
            })
        else:
            if abs(jc - rc) > tol:
                mismatches.append({
                    "start": k,
                    "issue": "value_mismatch",
                    "json": jc,
                    "recomputed": rc,
                })

    return pham_name, mismatches


#main

def main():
    pham_ids = load_pham_ids()
    if not pham_ids:
        return

    # randomly sample from list of all pham ids
    if phams_amount is not None and phams_amount > 0:
        if len(pham_ids) > phams_amount:
            sampled_ids = random.sample(pham_ids, phams_amount)
            sampled_ids.sort()
            print(
                f"Sampling {phams_amount} phams out of {len(pham_ids)} "
                f"from {pham_ids_file.name}"
            )
            pham_ids = sampled_ids
        else:
            print(
                f"Requested to sample {phams_amount} phams, "
                f"but only {len(pham_ids)} available; using all."
            )
    else:
        print(f"phams_amount is {phams_amount}; using all {len(pham_ids)} phams.")

    total = 0
    bad = 0

    for pham_id in pham_ids:
        total += 1
        path = download_pham_json(pham_id)  # skips if already cached
        if path is None:
            print(f"Skipping pham {pham_id}: download failed.")
            continue

        try:
            data = load_pham_json(path)
        except json.JSONDecodeError as e:
            print(f"ERROR: {path} is not valid JSON: {e}")
            continue

        pham_name, mismatches = compare_conservation(data)

        if mismatches:
            bad += 1
            print(f"\n=== {pham_name or pham_id} ({path.name}) has {len(mismatches)} mismatch(es) ===")
            for m in mismatches:
                print(
                    f"  start {m['start']}: {m['issue']} "
                    f"json={m['json']} recomputed={m['recomputed']}"
                )
        else:
            print(f"{pham_name or pham_id} ({path.name}): all Conservation values match.")

    print(f"\nChecked {total} phams; {bad} mismatches.")

    print(sampled_ids)


if __name__ == "__main__":
    main()


