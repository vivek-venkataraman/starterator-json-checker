from pathlib import Path
import re
import json

import requests


# Base URL where Starterator JSONs live
url = "http://phages.wustl.edu/starterator/json/"

# text file location
phams_file = Path(__file__).parent / "pham_ids.txt"


def fetch_pham_ids_from_server() -> list[int]:
    """
    Download the directory listing from url, extract all *.json filenames,
    and return the list of pham IDs as integers.
    """
    print(f"Fetching pham list from {url} ...")
    resp = requests.get(url, timeout=20)

    resp.raise_for_status()

    html = resp.text

    # Look for href="12345.json" or href='12345.json'
    ids: set[int] = set()
    for match in re.finditer(r'href=[\'"](\d+)\.json[\'"]', html):
        pham_str = match.group(1)
        try:
            ids.add(int(pham_str))
        except ValueError:
            print(f"  WARNING: could not parse pham id {pham_str!r}")

    ids_list = sorted(ids)
    print(f"Found {len(ids_list)} pham IDs on server.")
    return ids_list


def write_pham_ids_file(pham_ids: list[int]) -> None:
    """
    Write the list of pham IDs to phams_file, one per line.
    Overwrites any existing file.
    """
    if not pham_ids:
        print("No pham IDs to write; not updating pham_ids.txt.")
        return

    lines = [str(pid) for pid in pham_ids]
    phams_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(pham_ids)} IDs to {phams_file}")


def main():
    pham_ids = fetch_pham_ids_from_server()
    if not pham_ids:
        print("No pham IDs discovered on server; aborting.")
        return

    write_pham_ids_file(pham_ids)


if __name__ == "__main__":
    main()
