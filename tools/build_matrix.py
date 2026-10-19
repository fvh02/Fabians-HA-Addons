#!/usr/bin/env python3
"""Prints the GitHub Actions build matrix: one entry per add-on and architecture.

Usage: build_matrix.py [CHANGED_FILE ...]  – without arguments every add-on is built.
An add-on is rebuilt when a file in its folder changed; a change in shared/ or in the workflow
rebuilds all of them.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLATFORMS = {
    "amd64": ("linux/amd64", "ubuntu-24.04"),
    "aarch64": ("linux/arm64", "ubuntu-24.04-arm"),
    "armv7": ("linux/arm/v7", "ubuntu-24.04-arm"),
}


def addons() -> list[Path]:
    return sorted(p.parent for p in ROOT.glob("*/config.yaml"))


def archs(config: str) -> list[str]:
    block = re.search(r"^arch:\n((?:  - .+\n)+)", config, re.M)
    return re.findall(r"  - (\S+)", block.group(1)) if block else []


def base_image(addon: Path, arch: str) -> str:
    build = addon / "build.yaml"
    if not build.exists():
        return ""
    match = re.search(rf"^  {arch}: *(\S+)", build.read_text(), re.M)
    return match.group(1) if match else ""


def main(changed: list[str]) -> None:
    everything = not changed or any(f.startswith(("shared/", ".github/", "tools/build_matrix.py")) for f in changed)
    include = []
    for addon in addons():
        if not everything and not any(f.startswith(addon.name + "/") for f in changed):
            continue
        config = (addon / "config.yaml").read_text()
        version = re.search(r'^version: *"?([^"\n]+)"?', config, re.M).group(1)
        slug = re.search(r"^slug: *(\S+)", config, re.M).group(1)
        for arch in archs(config):
            platform, runner = PLATFORMS[arch]
            include.append({"addon": addon.name, "slug": slug, "version": version, "arch": arch,
                            "platform": platform, "runner": runner, "base": base_image(addon, arch)})
    print(json.dumps({"include": include}))


if __name__ == "__main__":
    main(sys.argv[1:])
