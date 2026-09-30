import math
import xml.etree.ElementTree as ET
from pathlib import Path

from argate.config import CoverageConfig
from argate.models import CoverageResult


def read_cobertura(path: Path) -> float:
    content = path.read_bytes()
    if len(content) > 10_000_000 or b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
        raise ValueError("Unsafe or oversized coverage document")
    root = ET.fromstring(content)
    value = float(root.attrib["line-rate"]) * 100
    if not math.isfinite(value) or not 0 <= value <= 100:
        raise ValueError("Invalid coverage rate")
    return round(value, 4)


def collect_coverage(config: CoverageConfig, root: Path, started: float) -> CoverageResult:
    result = CoverageResult(enabled=config.enabled)
    if not config.enabled:
        return result
    try:
        path = root / config.path
        if path.stat().st_mtime < started:
            raise ValueError("Coverage report is stale")
        result.current = read_cobertura(path)
        result.baseline = read_cobertura(root / config.baseline_path) if config.baseline_path else config.baseline
        if result.baseline is not None:
            result.drop = round(result.baseline - result.current, 4)
    except (OSError, ValueError, KeyError, ET.ParseError):
        result.error = "Coverage report missing, stale, or invalid; baseline must also be valid if configured"
    return result
