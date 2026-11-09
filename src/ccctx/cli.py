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
