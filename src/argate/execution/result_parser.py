import re


def parse_counts(output: str) -> dict[str, int | None]:
    """Best-effort pytest summary; unknown formats retain unknown counts."""
    counts = {"passed": None, "failed": None, "skipped": None}
    for key in counts:
        matches = re.findall(rf"\b(\d+) {key}\b", output)
        if matches:
            counts[key] = int(matches[-1])
    return counts
