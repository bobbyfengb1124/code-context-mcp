from ccctx.chunk import chunk_file, gaps, windows


def summary(path, src):
    return [(c.kind, c.name, c.start_line, c.end_line) for c in chunk_file(path, src.encode())]


def test_window_overlap():
    lines = [f"l{i}" for i in range(1, 131)]
    got = [(w.start_line, w.end_line) for w in windows("f", lines)]
    assert got == [(1, 60), (51, 110), (101, 130)]


def test_window_offset_range():
    lines = ["x"] * 200
    got = [(w.start_line, w.end_line) for w in windows("f", lines, 99, 105)]
    assert got == [(100, 105)]


def test_gaps_skip_blank_runs():
    from ccctx.chunk import Chunk
    lines = ["import os", "", "def f():", "  pass", "", "", "x = 1"]
    sym = [Chunk("f", "function", 3, 4, "")]
    assert gaps(sym, lines) == [(0, 1), (6, 7)]  # blank edges trimmed


def test_python_symbols_methods_decorators_and_toplevel():
    src = '''import os

@decorator
def top():
    def nested():
        pass
    return 1

class A:
    def m(self):
        return top()

app = A()
'''
    assert summary("x.py", src) == [
        ("function", "top", 3, 7),
        ("class", "A", 9, 11),
        ("method", "m", 10, 11),
        ("window", "x.py", 1, 1),
        ("window", "x.py", 13, 13),
    ]


def test_go():
    src = "package p\n\ntype S struct{}\n\nfunc (s S) M() {}\n\nfunc F() {\n}\n"
    assert [s for s in summary("a.go", src) if s[0] != "window"] == [
        ("class", "S", 3, 3), ("method", "M", 5, 5), ("function", "F", 7, 8)]


def test_doc_comment_attached_only_when_adjacent():
    src = "package p\n\n// F does a thing.\n// Really.\nfunc F() {}\n\n// stray\n\nfunc G() {}\n"
    assert summary("a.go", src) == [
        ("function", "F", 3, 5), ("function", "G", 9, 9),
        ("window", "a.go", 1, 1), ("window", "a.go", 7, 7)]


def test_java():
    src = "class A {\n  A() {}\n  void m() {}\n}\n"
    assert summary("A.java", src) == [("class", "A", 1, 4), ("method", "A", 2, 2), ("method", "m", 3, 3)]


def test_typescript_arrow_const_only_top_level():
    src = ("export const f = () => 1;\n"
           "const n = 5;\n"
           "export class K {\n  run() { const g = () => 2; }\n}\n")
    syms = [s for s in summary("a.ts", src) if s[0] != "window"]
    assert syms == [("function", "f", 1, 1), ("class", "K", 3, 5), ("method", "run", 4, 4)]


def test_bash():
    src = "#!/bin/bash\ngreet() {\n  echo hi\n}\ngreet\n"
    assert summary("a.sh", src) == [
        ("function", "greet", 2, 4), ("window", "a.sh", 1, 1), ("window", "a.sh", 5, 5)]


def test_powershell_and_parse_error_keeps_clean_symbols():
    src = ("function Get-A {\n  'a'\n}\n"
           "class W {\n  [string] Name() { return 'w' }\n}\n"
           "$v = Invoke-X $dir\\file.ps1\n")  # grammar gap: $var\path bareword
    syms = [s for s in summary("a.ps1", src) if s[0] != "window"]
    assert ("function", "Get-A", 1, 3) in syms
    assert ("class", "W", 4, 6) in syms


def test_no_grammar_is_windows():
    assert summary("README.md", "# hi\ntext\n") == [("window", "README.md", 1, 2)]


def test_empty_file():
    assert summary("a.py", "") == []
