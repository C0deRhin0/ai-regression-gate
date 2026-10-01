import os
from pathlib import Path


def write_summary(markdown: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with Path(path).open("a", encoding="utf-8") as stream:
            stream.write(markdown + "\n")
