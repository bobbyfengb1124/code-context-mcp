"""Cut source files into symbols at function/method/class boundaries.

Falls back to overlapping line windows when there is no grammar, the file
does not parse cleanly, or it defines no symbols.
"""

from dataclasses import dataclass
from functools import cache

from tree_sitter import Node, Parser
from tree_sitter_language_pack import get_parser

from .languages import LanguageSpec, for_path

WINDOW = 60
OVERLAP = 10
NAME_TYPES = ("identifier", "type_identifier", "property_identifier", "field_identifier",
              "function_name", "simple_name", "word")


@dataclass
class Chunk:
    name: str
    kind: str  # function | method | class | window
    start_line: int  # 1-based, inclusive
    end_line: int
    code: str


@cache
def _parser(grammar: str) -> Parser:
    return get_parser(grammar)


def name_of(node: Node) -> str | None:
    n = node.child_by_field_name("name")
    if n is None:
        for child in node.named_children:
            if child.type in NAME_TYPES:
                n = child
                break
            if child.type in ("type_spec", "variable_declarator"):  # Go types, TS const arrows
                n = child.child_by_field_name("name")
                break
    return n.text.decode("utf-8", "replace") if n is not None else None


def _symbols(root: Node, spec: LanguageSpec, lines: list[str]) -> list[Chunk]:
    out: list[Chunk] = []

    def visit(node: Node, in_class: bool) -> None:
        for child in node.named_children:
            kind = spec.symbols.get(child.type)
            accept = spec.accept.get(child.type)
            clean = not child.has_error  # a broken subtree has unreliable boundaries; look inside it
            if kind and clean and (accept is None or accept(child)) and (name := name_of(child)):
                if kind == "function" and in_class:
                    kind = "method"
                # include decorators/annotations that sit on a wrapping node (Python)
                outer = child.parent if child.parent.type == "decorated_definition" else child
                start, end = outer.start_point.row, child.end_point.row
                # pull in a doc comment directly above (Go/Java/TS/Bash/PS style), no blank line between
                prev = outer.prev_sibling
                while (prev is not None and "comment" in prev.type and prev.end_point.row == start - 1
                       and not prev.text.startswith(b"#!")):  # a shebang is not a doc comment
                    start, prev = prev.start_point.row, prev.prev_sibling
                out.append(Chunk(name, kind, start + 1, end + 1, "\n".join(lines[start:end + 1])))
                if kind == "class":
                    visit(child, True)  # methods; nested functions inside functions are skipped
            else:
                visit(child, in_class)

    visit(root, False)
    return out


def windows(name: str, lines: list[str], start: int = 0, stop: int | None = None) -> list[Chunk]:
    """60-line windows with 10 lines of overlap over lines[start:stop] (0-based)."""
    stop = len(lines) if stop is None else stop
    out = []
    while start < stop:
        end = min(start + WINDOW, stop)
        out.append(Chunk(name, "window", start + 1, end, "\n".join(lines[start:end])))
        if end == stop:
            break
        start = end - OVERLAP
    return out


def gaps(symbols: list[Chunk], lines: list[str]) -> list[tuple[int, int]]:
    """0-based [start, stop) runs of lines not covered by any symbol and not blank."""
    covered = [False] * len(lines)
    for s in symbols:
        covered[s.start_line - 1:s.end_line] = [True] * (s.end_line - s.start_line + 1)
    out, start = [], None
    for i, done in enumerate([*covered, True]):
        if not done and start is None:
            start = i
        elif done and start is not None:
            stop = i
            while start < stop and not lines[start].strip():  # trim blank edges
                start += 1
            while stop > start and not lines[stop - 1].strip():
                stop -= 1
            if start < stop:
                out.append((start, stop))
            start = None
    return out


def chunk_file(path: str, source: bytes) -> list[Chunk]:
    # split on \n only, like tree-sitter rows; splitlines() also breaks on \f, \x1c,  ...
    lines = [ln.removesuffix("\r") for ln in source.decode("utf-8", "replace").split("\n")]
    if lines and lines[-1] == "":
        lines.pop()
    spec = for_path(path)
    symbols = _symbols(_parser(spec.grammar).parse(source).root_node, spec, lines) if spec else []
    # top-level code and regions the grammar could not parse are still indexed, as windows
    name = path.rsplit("/", 1)[-1]
    return symbols + [w for a, b in gaps(symbols, lines) for w in windows(name, lines, a, b)]
