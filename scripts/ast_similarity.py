"""Statement-level AST similarity between two Python files.

Rough-and-ready clone finder used to locate training/inference duplication worth pulling
into `forecasting`. Not wired into CI; see docs/TODO.md for the cleanup note.

Normalises user identifiers, argument names and constants (so renamed-but-same-shape
code matches), keeps imported module names and attribute names (they carry the API
meaning: pd.concat, .groupby, .fit), drops docstrings, imports and single-line statements
(too short to be meaningful clones - `log.info(x)` matches every other `log.info(y)`). Then:

  1. contiguous blocks of identical normalised statements  -> copy/paste candidates
  2. per-statement best fuzzy match above a threshold      -> near-miss clones
  3. coverage, weighted by fingerprint length so one big matching block counts more
     than a handful of small ones

Usage: uv run python3 scripts/ast_similarity.py A.py B.py [threshold=0.8]
"""

from __future__ import annotations

import ast
import builtins
import copy
import difflib
import sys
from dataclasses import dataclass
from pathlib import Path


class Normalise(ast.NodeTransformer):
    def __init__(self, keep: set[str]) -> None:
        self.keep = keep

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id not in self.keep:
            node.id = "_v"
        return node

    def visit_arg(self, node: ast.arg) -> ast.AST:
        node.arg = "_a"
        node.annotation = None
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        node.name = "_f"
        node.returns = None
        self.generic_visit(node)
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        node.value = type(node.value).__name__  # "1.5" and "3.0" both -> "float"
        return node

    def visit_Expr(self, node: ast.Expr) -> ast.AST | None:
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None  # docstring / bare string cell
        self.generic_visit(node)
        return node


def imported_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            names |= {(a.asname or a.name).split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            names |= {a.asname or a.name for a in n.names}
    return names


@dataclass
class Stmt:
    lineno: int
    end: int
    src: str  # first source line, for display
    fp: str  # normalised ast.dump fingerprint

    @property
    def weight(self) -> int:
        return len(self.fp)


def statements(path: Path) -> list[Stmt]:
    text = path.read_text()
    tree = ast.parse(text)
    keep = imported_names(tree) | set(dir(builtins))
    lines = text.splitlines()
    out: list[Stmt] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        end = node.end_lineno or node.lineno
        if end == node.lineno:
            continue
        norm = Normalise(keep).visit(copy.deepcopy(node))
        if norm is None:
            continue
        out.append(Stmt(node.lineno, end, lines[node.lineno - 1].strip(), ast.dump(norm)))
    return out


def ratio(x: str, y: str) -> float:
    return difflib.SequenceMatcher(None, x, y, autojunk=False).ratio()


def report(a: list[Stmt], b: list[Stmt], threshold: float) -> None:
    fa, fb = [s.fp for s in a], [s.fp for s in b]
    sm = difflib.SequenceMatcher(None, fa, fb, autojunk=False)
    print(f"multi-line statements: A={len(a)}  B={len(b)}  shared-exact={len(set(fa) & set(fb))}")

    print("\n== contiguous identical blocks (>=2 stmts) ==")
    for m in sm.get_matching_blocks():
        if m.size >= 2:
            sa, sb = a[m.a], b[m.b]
            print(f"  A {sa.lineno}-{a[m.a + m.size - 1].end:<5} <-> B {sb.lineno}-{b[m.b + m.size - 1].end:<5} ({m.size} stmts)  {sa.src[:60]}")

    print(f"\n== per-statement best match (ratio >= {threshold}), sorted by weight ==")
    matches: list[tuple[float, Stmt, Stmt]] = []
    for sa in a:
        best = max(b, key=lambda sb: ratio(sa.fp, sb.fp))
        r = ratio(sa.fp, best.fp)
        if r >= threshold:
            matches.append((r, sa, best))
    matches.sort(key=lambda t: t[1].weight, reverse=True)
    print("  ratio  weight  A                                                  | B")
    for r, sa, sb in matches:
        print(f"  {r:.2f}  {sa.weight:>6}  A:{sa.lineno:<4} {sa.src[:44]:<44} | B:{sb.lineno:<4} {sb.src[:44]}")

    total = sum(s.weight for s in a)
    matched = sum(sa.weight for _, sa, _ in matches)
    print(f"\n{len(matches)}/{len(a)} statements in A match >= {threshold} in B; weighted coverage {matched / total:.0%} of A's AST mass")


if __name__ == "__main__":
    pa, pb = Path(sys.argv[1]), Path(sys.argv[2])
    thr = float(sys.argv[3]) if len(sys.argv) > 3 else 0.8
    print(f"A = {pa}\nB = {pb}\n")
    report(statements(pa), statements(pb), thr)
