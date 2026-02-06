from __future__ import annotations

from pathlib import Path
import json
import random
from typing import Any

try:
    import requests  # pip install requests (only needed if USE_NETWORK=True)
except Exception:
    requests = None


# -------------------------
# CONFIG
# -------------------------

BASE_URL = "https://phages.wustl.edu/starterator/json/"
PROJECT_DIR = Path(__file__).parent

# where downloaded jsons live
JSON_DIR = PROJECT_DIR / "json_data"

# list of pham ids (one per line)
PHAM_IDS_FILE = PROJECT_DIR / "pham_ids.txt"

# sampling: set None to use all
PHAMS_AMOUNT: int | None = 200

# network toggle
USE_NETWORK: bool = True          # if False, only read from local JSON_DIR
FORCE_REDOWNLOAD: bool = False    # only applies if USE_NETWORK=True

# adjacency definition (same-frame adjacent starts)
ADJ_STEP_BP: int = 3

# status updates
CHUNK_SIZE: int = 20


# -------------------------
# IO helpers
# -------------------------

def load_pham_ids() -> list[int]:
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


def pham_json_path(pham_id: int) -> Path:
    return JSON_DIR / f"{pham_id}.json"


def download_pham_json(pham_id: int, force: bool = False) -> Path | None:
    """
    Ensure JSON exists locally, downloading if allowed.
    """
    JSON_DIR.mkdir(exist_ok=True)
    path = pham_json_path(pham_id)

    if path.exists() and not force:
        return path

    if not USE_NETWORK:
        # local-only mode
        if path.exists():
            return path
        print(f"Missing local JSON for pham {pham_id}: {path}")
        return None

    if requests is None:
        print("ERROR: requests is not installed, but USE_NETWORK=True.")
        return None

    url = f"{BASE_URL}{pham_id}.json"
    print(f"Downloading {url} ...")
    try:
        resp = requests.get(url, timeout=20)
    except Exception as e:
        print(f"  ERROR: could not download {url}: {e}")
        return None

    if resp.status_code != 200:
        print(f"  ERROR: status {resp.status_code} for {url}")
        return None

    # validate json
    try:
        _ = resp.json()
    except json.JSONDecodeError as e:
        print(f"  ERROR: invalid JSON from {url}: {e}")
        return None

    path.write_text(resp.text, encoding="utf-8")
    print(f"  Saved to {path}")
    return path


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# -------------------------
# Adjacent-start logic
# -------------------------

def ordered_5prime_to_3prime(coords: list[int], orientation: str) -> list[int]:
    """
    Return coords ordered in the gene's 5'->3' direction.

    Orientation values in your JSON are typically "F" or "R".
    """
    ori = (orientation or "").upper()
    if ori.startswith("F"):
        return sorted(coords)
    if ori.startswith("R"):
        return sorted(coords, reverse=True)

    # unknown orientation: fall back to ascending, but flagging would also be reasonable
    return sorted(coords)


def cluster_adjacent(coords_ordered: list[int], step: int = 3) -> list[list[int]]:
    """
    Given coords already ordered in 5'->3', group into clusters where consecutive coords differ by `step`.
    """
    if not coords_ordered:
        return []

    clusters: list[list[int]] = []
    cur = [coords_ordered[0]]

    for c in coords_ordered[1:]:
        if abs(c - cur[-1]) == step:
            cur.append(c)
        else:
            clusters.append(cur)
            cur = [c]

    clusters.append(cur)
    return clusters


def infer_called_coord(gene: dict[str, Any]) -> tuple[int | None, str]:
    """
    Map gene["Start"] to a coordinate that actually appears in gene["AvailableCoord"].

    Some phams appear to have Start that is consistently off by 1 relative to AvailableCoord,
    so we try Start, then Start+1, then Start-1.

    Returns: (called_coord_or_None, note_string)
    """
    start = gene.get("Start")
    coords = gene.get("AvailableCoord") or []

    if start is None or not coords:
        return None, "missing_start_or_availablecoord"

    coords_set = set(coords)

    if start in coords_set:
        return start, "used_Start"
    if (start + 1) in coords_set:
        return start + 1, "used_Start_plus_1"
    if (start - 1) in coords_set:
        return start - 1, "used_Start_minus_1"

    return None, "Start_not_mappable_to_AvailableCoord"


def check_gene_adjacent_rule(gene: dict[str, Any], step: int = 3) -> dict[str, Any] | None:
    """
    Rule: if the called start lies in a cluster of adjacent starts, it should equal the FIRST start in that cluster
    (first = most 5' in the gene's direction).
    """
    coords = gene.get("AvailableCoord") or []
    if not coords:
        return None

    orientation = gene.get("Orientation", "")
    ordered = ordered_5prime_to_3prime(coords, orientation)
    clusters = cluster_adjacent(ordered, step=step)

    called, note = infer_called_coord(gene)
    if called is None:
        return {
            "issue": "called_start_unmappable",
            "note": note,
            "start_field": gene.get("Start"),
            "orientation": orientation,
        }

    # find cluster containing called
    containing = None
    for cl in clusters:
        if called in cl:
            containing = cl
            break

    if containing is None:
        return {
            "issue": "called_start_not_in_any_cluster",
            "called": called,
            "note": note,
            "orientation": orientation,
        }

    if len(containing) > 1 and called != containing[0]:
        return {
            "issue": "adjacent_cluster_not_first",
            "called": called,
            "should_be": containing[0],
            "cluster": containing,
            "note": note,
            "orientation": orientation,
        }

    return None


def check_pham(data: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for gene in data.get("Genes", []):
        res = check_gene_adjacent_rule(gene, step=ADJ_STEP_BP)
        if res:
            res.update({
                "GeneID": gene.get("GeneID"),
                "locustag": gene.get("locustag"),
            })
            issues.append(res)
    return issues


# -------------------------
# main
# -------------------------

def main() -> None:
    pham_ids = load_pham_ids()
    if not pham_ids:
        return

    # sample
    if PHAMS_AMOUNT is not None and PHAMS_AMOUNT > 0 and len(pham_ids) > PHAMS_AMOUNT:
        sampled_ids = sorted(random.sample(pham_ids, PHAMS_AMOUNT))
        print(f"Sampling {PHAMS_AMOUNT} phams out of {len(pham_ids)}")
        pham_ids = sampled_ids
    else:
        print(f"Using all {len(pham_ids)} phams")

    total = 0
    bad = 0

    for pham_id in pham_ids:
        total += 1

        path = download_pham_json(pham_id, force=FORCE_REDOWNLOAD)
        if path is None:
            print(f"Skipping pham {pham_id}: could not get JSON.")
            continue

        try:
            pham_data = load_json(path)
        except json.JSONDecodeError as e:
            print(f"ERROR: {path} invalid JSON: {e}")
            continue

        name = pham_data.get("Name") or str(pham_id)
        issues = check_pham(pham_data)

        if issues:
            bad += 1
            print(f"\n=== {name} ({path.name}) adjacent-start issues: {len(issues)} ===")
            for it in issues[:50]:  # avoid giant spam; adjust as needed
                print(
                    f"  {it.get('GeneID')}: {it['issue']} "
                    f"(ori={it.get('orientation')}, note={it.get('note')}, "
                    f"called={it.get('called')}, should_be={it.get('should_be')})"
                )
            if len(issues) > 50:
                print(f"  ... ({len(issues)-50} more)")
        else:
            print(f"{name} ({path.name}): OK (adjacent rule satisfied)")

        if total % CHUNK_SIZE == 0:
            print(f"\n--- Status: processed {total}/{len(pham_ids)}; {bad} phams with issues ---")

    print(f"\nDone. Checked {total} phams; {bad} had adjacent-start issues.")


if __name__ == "__main__":
    main()
