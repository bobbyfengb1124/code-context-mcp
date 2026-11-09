"""Language table. Adding a language = adding one LanguageSpec; the chunker never changes."""

from collections.abc import Callable
from dataclasses import dataclass, field

from tree_sitter import Node


@dataclass(frozen=True)
class LanguageSpec:
    name: str
    grammar: str
    extensions: tuple[str, ...]
    symbols: dict[str, str]  # node type -> kind (function | method | class)
    # optional per-node-type filter, e.g. "only const declarations holding an arrow function"
    accept: dict[str, Callable[[Node], bool]] = field(default_factory=dict)


def _ts_arrow_const(node: Node) -> bool:
    if node.parent is None or node.parent.type not in ("program", "export_statement"):
        return False  # top-level only; inline callbacks would flood the index
    decl = next((c for c in node.named_children if c.type == "variable_declarator"), None)
    value = decl and decl.child_by_field_name("value")
    return bool(value and value.type in ("arrow_function", "function_expression"))


_TS_SYMBOLS = {
    "function_declaration": "function",
    "generator_function_declaration": "function",
    "lexical_declaration": "function",
    "class_declaration": "class",
    "abstract_class_declaration": "class",
    "interface_declaration": "class",
    "enum_declaration": "class",
    "method_definition": "method",
}

LANGUAGES = [
    LanguageSpec("python", "python", (".py", ".pyi"), {
        "function_definition": "function",
        "class_definition": "class",
    }),
    LanguageSpec("go", "go", (".go",), {
        "function_declaration": "function",
        "method_declaration": "method",
        "type_declaration": "class",
    }),
    LanguageSpec("java", "java", (".java",), {
        "class_declaration": "class",
        "interface_declaration": "class",
        "enum_declaration": "class",
        "record_declaration": "class",
        "method_declaration": "method",
        "constructor_declaration": "method",
        "compact_constructor_declaration": "method",
    }),
    LanguageSpec("typescript", "typescript", (".ts", ".mts", ".cts", ".js", ".mjs", ".cjs"),
                 _TS_SYMBOLS, {"lexical_declaration": _ts_arrow_const}),
    LanguageSpec("typescript", "tsx", (".tsx", ".jsx"),
                 _TS_SYMBOLS, {"lexical_declaration": _ts_arrow_const}),
    LanguageSpec("bash", "bash", (".sh", ".bash"), {
        "function_definition": "function",
    }),
    LanguageSpec("powershell", "powershell", (".ps1", ".psm1"), {
        "function_statement": "function",
        "class_statement": "class",
        "enum_statement": "class",
        "class_method_definition": "method",
    }),
]

_BY_EXT = {ext: spec for spec in LANGUAGES for ext in spec.extensions}


def for_path(path: str) -> LanguageSpec | None:
    dot = path.rfind(".")
    return _BY_EXT.get(path[dot:].lower()) if dot > path.rfind("/") else None


def grammars() -> list[str]:
    return sorted({spec.grammar for spec in LANGUAGES})
