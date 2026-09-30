from argate.models import ChangedFile


def parse_name_status(data: bytes) -> list[ChangedFile]:
    tokens = data.decode("utf-8", errors="replace").split("\0")
    files = []
    index = 0
    while index < len(tokens) and tokens[index]:
        status = tokens[index]
        index += 1
        old_path = None
        if status.startswith(("R", "C")):
            old_path = tokens[index]
            index += 1
        path = tokens[index]
        index += 1
        files.append(ChangedFile(path=path, old_path=old_path, status=status[0]))
    return files


def apply_numstat(files: list[ChangedFile], data: bytes) -> None:
    lookup = {file.path: file for file in files}
    tokens = data.decode("utf-8", errors="replace").split("\0")
    index = 0
    while index < len(tokens) and tokens[index]:
        added, deleted, path = tokens[index].split("\t", 2)
        index += 1
        if not path:  # Rename/copy numstat uses an extra NUL old/new path pair.
            index += 1
            path = tokens[index]
            index += 1
        file = lookup[path]
        file.binary = added == "-" or deleted == "-"
        file.insertions = int(added) if added != "-" else 0
        file.deletions = int(deleted) if deleted != "-" else 0
