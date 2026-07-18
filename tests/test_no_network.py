import ast
import pathlib

FORBIDDEN_MODULES = {
    "requests", "urllib", "urllib2", "urllib3", "http", "http.client",
    "socket", "ftplib", "smtplib", "httpx", "aiohttp",
}

SCAN_DIRS = ["core", "app"]


def _imported_modules(py_file: pathlib.Path) -> set[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module.split(".")[0])
    return modules


def test_no_networking_imports_in_core_or_app():
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    violations = []
    for scan_dir in SCAN_DIRS:
        for py_file in (repo_root / scan_dir).rglob("*.py"):
            found = _imported_modules(py_file) & FORBIDDEN_MODULES
            if found:
                violations.append(f"{py_file}: imports {sorted(found)}")
    assert not violations, "Networking imports found:\n" + "\n".join(violations)
