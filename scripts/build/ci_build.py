#!/usr/bin/env python3
"""GitHub Actions / Cloud Build compilation script.

This script is optimized for CI environments with:
- High parallelism
- Caching of Nuitka build artifacts
- Clean separation of build stages
- Targets: ``lsp`` (default), ``cli``, or ``all``

Usage (GitHub Actions):
    - name: Build LSP binary
      run: python scripts/build/ci_build.py --target lsp --jobs 4

    - name: Build CLI binary
      run: python scripts/build/ci_build.py --target cli --jobs 4

Usage (Cloud Build):
    steps:
      - name: python
        args: [python, scripts/build/ci_build.py, --target, lsp, --jobs, 4]
"""

from __future__ import annotations

import argparse
import hashlib
import multiprocessing
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).parent.parent.parent.resolve()
DIST = ROOT / "dist"
SRC = ROOT / "src" / "pynescript"
SRC_LSP = SRC / "langserver"
PROVIDERS_DIR = SRC_LSP / "providers"
BUILD_DIR = ROOT / "scripts" / "build"
KEY_FILE = BUILD_DIR / ".metadata.key"
LSP_BINARY_NAME = "pynescript-lsp"
CLI_BINARY_NAME = "pynescript"
VSCODE_EXT = ROOT / "vscode-extension"


def run(cmd: Sequence[str | Path], cwd: Path | None = None, env: dict | None = None, capture: bool = False):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    kwargs: dict = dict(cwd=cwd, env=env or os.environ)
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    result = subprocess.run(list(cmd), **kwargs)
    if result.returncode != 0:
        print(f"  FAILED: exit {result.returncode}", file=sys.stderr)
        if capture and result.stderr:
            print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result


def _resolve_fernet_key() -> bytes:
    """Stable Fernet key: CRYPTO_KEY → PYNESCRIPT_METADATA_KEY → METADATA_KEY → .metadata.key → generate."""
    for env_name in ("CRYPTO_KEY", "PYNESCRIPT_METADATA_KEY", "METADATA_KEY"):
        raw = (os.environ.get(env_name) or "").strip()
        if raw:
            key = raw.encode("ascii")
            BUILD_DIR.mkdir(parents=True, exist_ok=True)
            KEY_FILE.write_bytes(key)
            os.chmod(KEY_FILE, 0o600)
            print(f"  Key: from env {env_name}")
            return key

    if KEY_FILE.exists():
        print(f"  Key: {KEY_FILE}")
        return KEY_FILE.read_bytes()

    from cryptography.fernet import Fernet

    key = Fernet.generate_key()
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_bytes(key)
    os.chmod(KEY_FILE, 0o600)
    print(f"  Key: generated {KEY_FILE} (set secrets.METADATA_KEY for reproducible CI)")
    return key


def stage_metadata() -> None:
    """Generate and encrypt metadata."""
    gen_script = ROOT / "scripts" / "generate_builtin_metadata.py"
    if gen_script.exists():
        run([sys.executable, str(gen_script)])

    from cryptography.fernet import Fernet

    plaintext_path = PROVIDERS_DIR / "builtin_metadata.json"
    if not plaintext_path.is_file():
        print(f"  ERROR: Metadata plaintext not found at {plaintext_path}", file=sys.stderr)
        sys.exit(1)

    key = _resolve_fernet_key()
    enc_path = PROVIDERS_DIR / "builtin_metadata.json.enc"
    plaintext = plaintext_path.read_bytes()
    fernet = Fernet(key)
    encrypted = fernet.encrypt(plaintext)
    enc_path.write_bytes(encrypted)
    sha = hashlib.sha256(plaintext).hexdigest()[:16]
    (PROVIDERS_DIR / "builtin_metadata.json.sha256").write_text(sha + "\n")
    print(f"  Metadata: {len(plaintext) // 1024}KB -> encrypted")


def _package_version() -> str:
    """Read package version for Windows resource / product metadata."""
    about = ROOT / "src" / "pynescript" / "__about__.py"
    if not about.is_file():
        return "0.0.0"
    text = about.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("__version__"):
            # __version__ = "0.3.0"
            return line.split("=", 1)[1].strip().strip("\"'")
    return "0.0.0"


def _product_version(version: str) -> str:
    # Nuitka Windows version resource requires dotted numeric product/file version.
    # Accept pep440-ish versions by taking the leading X.Y.Z.
    version_core = version.split("+")[0].split("a")[0].split("b")[0].split("rc")[0]
    parts = [p for p in version_core.split(".") if p.isdigit()]
    while len(parts) < 3:
        parts.append("0")
    return ".".join(parts[:4])  # Nuitka accepts up to 4 components


def _find_binary(output_dir: Path, binary_name: str) -> Path | None:
    """Locate a compiled binary by exact name (never confuse CLI with LSP).

    ``pynescript`` must not match ``pynescript-lsp`` via a naive ``name*`` glob.
    Accepts exact name plus common Nuitka suffixes (``.bin``, ``.exe``, …).
    """
    if not output_dir.is_dir():
        return None

    candidates = [
        output_dir / binary_name,
        output_dir / f"{binary_name}.bin",
        output_dir / f"{binary_name}.exe",
        output_dir / f"{binary_name}.onefile.exe",
    ]
    for path in candidates:
        if path.is_file():
            return path

    # Fallback: exact name or name + extension only (not name-something).
    for path in sorted(output_dir.iterdir()):
        if not path.is_file():
            continue
        name = path.name
        if name == binary_name or name.startswith(f"{binary_name}."):
            return path
    return None


def compile_onefile(jobs: int, *, target: str = "lsp") -> Path:
    """Build onefile binary via Nuitka for ``lsp`` or ``cli``."""
    if target not in ("lsp", "cli"):
        raise ValueError(f"Unknown target: {target}")

    binary_name = LSP_BINARY_NAME if target == "lsp" else CLI_BINARY_NAME
    output_dir = DIST / target
    output_dir.mkdir(parents=True, exist_ok=True)
    jobs = jobs or max(1, multiprocessing.cpu_count() - 1)

    entry = (SRC_LSP / "__main__.py") if target == "lsp" else (SRC / "__main__.py")
    if not entry.is_file():
        raise FileNotFoundError(f"Entry not found: {entry}")

    product_version = _product_version(_package_version())
    file_description = (
        "PYNE Pine Script Language Server"
        if target == "lsp"
        else "PYNE Pine Script CLI"
    )

    # Prefer package name so Nuitka resolves imports under pynescript.*
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    env["PYTHONPATH"] = src_path + os.pathsep + env.get("PYTHONPATH", "")

    cmd: list[str] = [
        sys.executable,
        "-m",
        "nuitka",
        "--onefile",
        "--assume-yes-for-downloads",  # Dependency Walker / ccache on CI (no TTY)
        f"--output-dir={output_dir}",
        f"--output-filename={binary_name}",
        "--python-flag=no_site,no_docstrings",
        "--static-libpython=no",
        "--follow-imports",
        "--nofollow-import-to=numba",
        "--nofollow-import-to=llvmlite",
        "--nofollow-import-to=numpy",
        "--nofollow-import-to=cryptography",
        "--nofollow-import-to=matplotlib",
        "--nofollow-import-to=ccxt",
        "--lto=auto",
        f"--product-name={binary_name}",
        f"--product-version={product_version}",
        f"--file-version={product_version}",
        f"--file-description={file_description}",
        "--company-name=HOOX",
        f"--jobs={jobs}",
        "--remove-output",
    ]

    if target == "lsp":
        # Follow imports from the LSP entry only — do NOT force-include the whole
        # pynescript tree (compiler/numba bloat + broken cryptography rpaths on macOS).
        cmd += [
            "--nofollow-import-to=pynescript.compiler",
            "--nofollow-import-to=pynescript.ast.evaluator",
            f"--include-data-dir={PROVIDERS_DIR}=pynescript/langserver/providers",
        ]
    else:
        # CLI needs evaluator for run/lint/compile-check; skip LSP/Flask stack.
        cmd += [
            "--nofollow-import-to=pynescript.langserver",
            "--nofollow-import-to=pygls",
            "--nofollow-import-to=lsprotocol",
            "--nofollow-import-to=flask",
            "--nofollow-import-to=backend",
        ]

    cmd.append(str(entry))
    run(cmd, env=env)

    binary = _find_binary(output_dir, binary_name)
    if binary is None:
        raise FileNotFoundError(
            f"Binary not found under {output_dir} (looked for exact {binary_name} / .bin / .exe)"
        )

    final_binary = DIST / binary.name
    DIST.mkdir(parents=True, exist_ok=True)
    if binary.resolve() != final_binary.resolve():
        shutil.move(str(binary), str(final_binary))
    print(f"  Binary: {final_binary} ({final_binary.stat().st_size / 1024 / 1024:.1f} MB)")
    return final_binary


def package_vsix(binary: Path) -> Path:
    """Build VSIX bundle."""
    vsix_file = DIST / "vsix" / "pynescript-lsp.vsix"
    vsix_file.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(vsix_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(VSCODE_EXT):
            dirs[:] = [d for d in dirs if d not in (".git", ".vscode", "node_modules")]
            for file in files:
                if file.endswith((".ts", ".map")):
                    continue
                filepath = Path(root) / file
                arcname = filepath.relative_to(VSCODE_EXT)
                zf.write(filepath, arcname)

        lsp_dir = vsix_file.parent / "lsp_bin"
        lsp_dir.mkdir(parents=True, exist_ok=True)
        bin_copy = lsp_dir / binary.name
        shutil.copy2(binary, bin_copy)
        zf.write(bin_copy, f"pynescript-lsp/{binary.name}")

    print(f"  VSIX: {vsix_file} ({vsix_file.stat().st_size / 1024 / 1024:.1f} MB)")
    return vsix_file


def main() -> None:
    parser = argparse.ArgumentParser(description="CI Nuitka build for Pynescript LSP/CLI")
    parser.add_argument(
        "--target",
        choices=("lsp", "cli", "all"),
        default="lsp",
        help="Binary to build (default: lsp)",
    )
    parser.add_argument("--jobs", type=int, default=None)
    parser.add_argument("--skip-vsix", action="store_true")
    parser.add_argument("--skip-metadata", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    jobs = args.jobs or max(1, multiprocessing.cpu_count() - 1)
    targets = ["lsp", "cli"] if args.target == "all" else [args.target]

    print("=" * 60)
    print(f"CI Build: Pynescript ({', '.join(targets)})")
    print(f"  Jobs: {jobs}")
    print(f"  Root: {ROOT}")
    print("=" * 60)

    if args.dry_run:
        print("[dry-run] Would run: metadata + compile + vsix")
        return

    DIST.mkdir(parents=True, exist_ok=True)

    try:
        if "lsp" in targets:
            print("\n[metadata] Metadata...")
            if not args.skip_metadata:
                stage_metadata()
            else:
                print("  Skipped")

        results: dict[str, Path] = {}
        for t in targets:
            print(f"\n[compile:{t}] Compile...")
            results[t] = compile_onefile(jobs, target=t)

        if "lsp" in targets:
            print("\n[vsix] VSIX...")
            if not args.skip_vsix:
                package_vsix(results["lsp"])
            else:
                print("  Skipped")
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print("Build complete!")
    for t, path in results.items():
        print(f"  {t.upper()}: {path}")
    if "lsp" in targets and not args.skip_vsix:
        print(f"  VSIX: {DIST / 'vsix' / 'pynescript-lsp.vsix'}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
