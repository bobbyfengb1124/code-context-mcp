"""ccctx command line. Thin layer: parse args, call services, print."""

import typer

from . import db, repos

app = typer.Typer(no_args_is_help=True, add_completion=False)
repo_app = typer.Typer(no_args_is_help=True, help="Register and list codebases.")
app.add_typer(repo_app, name="repo")


def print_table(headers: list[str], rows: list[list], right: set[str] = frozenset()) -> None:
    widths = [max(len(str(x)) for x in [h, *(r[i] for r in rows)]) for i, h in enumerate(headers)]
    for row in [headers, *rows]:
        cells = [
            str(v).rjust(w) if h in right else str(v).ljust(w)
            for v, w, h in zip(row, widths, headers)
        ]
        typer.echo("  ".join(cells).rstrip())


@app.command()
def init():
    """Download the tree-sitter grammars up front (they are otherwise fetched on first use)."""
    from tree_sitter_language_pack import download

    from .languages import grammars

    download(grammars())
    typer.echo(f"Grammars ready: {', '.join(grammars())}")


@app.command("ingest")
def ingest_cmd(name: str):
    """Parse a registered repository into symbols."""
    from . import ingest

    try:
        s = ingest.ingest(db.connect(), name)
    except ingest.IngestError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)
    reasons = ", ".join(f"{n} {r}" for r, n in s.skipped.most_common() if n)
    width = len(f"{max(s.scanned, s.symbols):,}")
    typer.echo(f"Scanned  {s.scanned:>{width},} files")
    typer.echo(f"Skipped  {sum(s.skipped.values()):>{width},} files" + (f" ({reasons})" if reasons else ""))
    typer.echo(f"Indexed  {s.symbols:>{width},} symbols from {s.files:,} files in {s.seconds:.1f}s")


@app.command()
def symbols(
    repo: str = typer.Option(None, "--repo"),
    kind: str = typer.Option(None, "--kind", help="function | method | class | window"),
    limit: int = typer.Option(20, "--limit"),
):
    """List indexed symbols."""
    from . import store

    rows = store.list_symbols(db.connect(), repo, kind, limit)
    print_table(
        ["REPO", "PATH", "LINES", "KIND", "NAME"],
        [[r["repo"], r["path"], f"{r['start_line']}-{r['end_line']}", r["kind"], r["name"]] for r in rows],
    )


@app.command()
def stats(
    by_language: bool = typer.Option(False, "--by-language", help="Break counts down by language."),
    repo: str = typer.Option(None, "--repo"),
):
    """Index statistics."""
    from . import store

    conn = db.connect()
    if not by_language:
        return repo_list()
    rows = store.stats_by_language(conn, repo)
    print_table(
        ["REPO", "LANGUAGE", "FILES", "SYMBOLS", "WINDOWS"],
        [[r["repo"], r["language"], f"{r['files']:,}", f"{r['symbols']:,}", f"{r['windows']:,}"] for r in rows],
        right={"FILES", "SYMBOLS", "WINDOWS"},
    )


@repo_app.command("add")
def repo_add(path: str, name: str = typer.Option(None, "--name", help="Short name (default: folder name).")):
    """Register a local git repository."""
    try:
        name, root = repos.add(db.connect(), path, name)
    except repos.RepoError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)
    typer.echo(f"Registered {name} -> {root}")


@repo_app.command("list")
def repo_list():
    """List registered repositories with file and symbol counts."""
    rows = repos.list_all(db.connect())
    print_table(
        ["NAME", "PATH", "FILES", "SYMBOLS"],
        [[r["name"], r["path"], f"{r['files']:,}", f"{r['symbols']:,}"] for r in rows],
        right={"FILES", "SYMBOLS"},
    )
