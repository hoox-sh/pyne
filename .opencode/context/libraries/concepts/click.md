<!-- Context: libraries/concepts/click | Priority: high | Version: 1.0 | Updated: 2026-07-05 -->

# Click (CLI)

This repo uses Click for the `pynescript` command group in
`src/pynescript/__main__.py`. The `pynescript-lsp` script is **not** Click
(it's `pygls`'s own entry).

**context7 source**: `/pallets/click` (674 snippets) and
`/websites/click_palletsprojects_en_stable` (925). Both are equivalent; prefer
the website one for prose and the github one for code examples.

## Patterns Used in This Repo

```python
import click

@click.group()
@click.version_option()      # auto-detects version from package metadata
def cli():
    pass

@cli.command(short_help="...")
@click.argument("filename", metavar="PATH",
                type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True))
@click.option("--encoding", default="utf-8")
@click.option("--indent", type=int, default=2)
@click.option("--output-file", metavar="PATH",
              type=click.Path(writable=True, allow_dash=True), default="-")
def parse_and_dump(filename, encoding, indent, output_file):
    with click.open_file(filename, "r", encoding=encoding) as f:
        ...
    with click.open_file(output_file, "w", encoding=encoding) as f:
        f.write(...)

if __name__ == "__main__":
    cli(prog_name="pynescript")
```

## Useful Decorators / Types

| Symbol | Purpose |
| --- | --- |
| `@click.group()` | parent of subcommands |
| `@cli.command()` | child command (use the group's decorator) |
| `@click.version_option()` | auto `--version` |
| `@click.argument("name", type=...)` | positional |
| `@click.option("--flag/--no-flag", default=False)` | boolean flag |
| `type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True)` | file path |
| `type=click.Path(writable=True, allow_dash=True)` | write path; `-` for stdout |
| `type=click.Choice([...], case_sensitive=False)` | enum-like |
| `type=click.INT`, `type=click.FLOAT` | numeric types |
| `@click.option("--fix", is_flag=True)` | boolean toggle |
| `click.open_file("-", "w", encoding="utf-8")` | context manager; `-` = stdout/stdin |
| `click.echo(...)` | print (handles bytes/unicode) |
| `raise click.ClickException("msg")` | clean error → exit code 1 |

## Version Detection

`@click.version_option()` reads from `importlib.metadata.version(package_name)`
by default. The package name is auto-detected from the call stack. Works out of
the box because the package is installed via `pyproject.toml`.

## Subcommands as Groups

```python
@cli.command()
def lint(filename, encoding, fix, fail_on):
    """Lint Pine Script files."""
    ...
```

Docstring becomes `--help` text. `short_help` is the one-liner in the group
listing; the docstring is the long help.

## Gotchas

- `click.open_file` is the **only** sanctioned way to handle `-` for stdin/stdout
  in Click — using `open()` won't treat `-` specially.
- `click.echo` is preferred over `print()` because it handles bytes, ANSI, etc.
- Raise `click.ClickException` rather than `sys.exit(1)` so error messages get
  formatted consistently.

## 📂 Codebase References

- **Implementation**: `src/pynescript/__main__.py` — `cli` group, all subcommands.
- **Reference**: `pyproject.toml` — `pynescript = "pynescript.__main__:cli"`.
- **Reference**: `click>=8.1.7` in `dependencies`.
