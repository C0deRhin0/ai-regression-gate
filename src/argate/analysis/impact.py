import re

from argate.config import Config
from argate.models import ChangeSet


def matches(path: str, pattern: str) -> bool:
    """POSIX repository globs: * within a segment, ** across segments, ? one character."""
    pattern = pattern.removeprefix("./")
    expression = ""
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*" and pattern[index:index + 2] == "**":
            index += 2
            if index < len(pattern) and pattern[index] == "/":
                expression += "(?:.*/)?"
                index += 1
            else:
                expression += ".*"
            continue
        expression += "[^/]*" if char == "*" else "[^/]" if char == "?" else re.escape(char)
        index += 1
    return re.fullmatch(expression, path) is not None


def any_match(path: str, patterns: list[str]) -> bool:
    return any(matches(path, pattern) for pattern in patterns)


def map_components(changes: ChangeSet, config: Config) -> list[str]:
    affected = set()
    for file in changes.changed_files:
        file.components = sorted(
            name for name, component in config.components.items()
            if any(any_match(path, component.paths) for path in [file.path, file.old_path] if path)
        )
        affected.update(file.components)
    return sorted(affected)
