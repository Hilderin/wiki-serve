from pathlib import Path


def _resolve_file(config, path: str) -> Path | None:
    p = Path(path)
    if p.is_absolute():
        return p if p.exists() else None

    candidate = (Path.cwd() / p).resolve()
    if candidate.exists():
        return candidate

    for inc in config.include_paths:
        inc = inc.resolve()
        base = inc if inc.is_dir() else inc.parent
        candidate = (base / p).resolve()
        if candidate.exists():
            return candidate

    return None
