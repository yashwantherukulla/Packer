from __future__ import annotations

import ast

from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet
from packer.engine.sandbox.findings import Finding

_CALL_NAMES = {
    "eval": ("ast.eval", "high"),
    "exec": ("ast.exec", "high"),
    "compile": ("ast.compile", "medium"),
    "__import__": ("ast.dynamic-import", "medium"),
}
_ATTR_ROOTS = {
    "subprocess": ("ast.subprocess", "high"),
    "socket": ("ast.network", "high"),
    "os": ("ast.os", "low"),
    "ctypes": ("ast.ctypes", "high"),
    "pickle": ("ast.pickle", "medium"),
    "base64": ("ast.base64", "low"),
    "marshal": ("ast.marshal", "medium"),
}
_OS_HIGH = {"system", "popen", "execv", "execve", "execvp", "spawn"}


@SCANNER_REGISTRY.register("ast_rules")
class AstRulesScanner:
    """AST-level dangerous-construct detector for Python units (spec §2)."""

    name = "ast_rules"

    def scan(self, files: FileSet) -> list[Finding]:
        out: list[Finding] = []
        for path, data in files.files.items():
            if not path.endswith(".py"):
                continue
            try:
                tree = ast.parse(data.decode("utf-8", "replace"), filename=path)
            except SyntaxError as exc:
                out.append(
                    Finding(
                        "info",
                        "ast.parse-error",
                        path,
                        exc.lineno or 0,
                        "file did not parse as Python",
                    )
                )
                continue
            out.extend(self._walk(tree, path))
        return out

    def _walk(self, tree: ast.AST, path: str) -> list[Finding]:
        out: list[Finding] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                out.extend(self._call(node, path))
            elif isinstance(node, ast.Import | ast.ImportFrom):
                out.extend(self._import(node, path))
        return out

    def _call(self, node: ast.Call, path: str) -> list[Finding]:
        line = node.lineno
        func = node.func
        if isinstance(func, ast.Name) and func.id in _CALL_NAMES:
            rule, sev = _CALL_NAMES[func.id]
            return [Finding(sev, rule, path, line, f"call to {func.id}()")]
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            root = func.value.id
            if root == "os" and func.attr in _OS_HIGH:
                return [Finding("high", "ast.os-exec", path, line, f"os.{func.attr}()")]
            if root in _ATTR_ROOTS:
                rule, sev = _ATTR_ROOTS[root]
                return [Finding(sev, rule, path, line, f"{root}.{func.attr}()")]
        return []

    def _import(self, node: ast.AST, path: str) -> list[Finding]:
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module.split(".")[0]]
        out: list[Finding] = []
        for n in names:
            if n in _ATTR_ROOTS and n not in ("os", "base64"):
                rule, sev = _ATTR_ROOTS[n]
                out.append(
                    Finding(
                        sev if sev != "high" else "medium",
                        f"{rule}-import",
                        path,
                        getattr(node, "lineno", 0),
                        f"imports {n}",
                    )
                )
        return out
