#!/usr/bin/env python3
"""GitHub Actions / Cloud Build compilation script.

This script is optimized for CI environments with:
- High parallelism
- Caching of Nuitka build artifacts
- Clean separation of build stages

Usage (GitHub Actions):
    - name: Build LSP binary
      run: python scripts/build/ci_build.py --onefile

Usage (Cloud Build):
    steps:
      - name: python
        args: [python, scripts/build/ci_build.py, --onefile, --upload-gcs, $PROJECT_ID]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.resolve()
DIST = ROOT / "dist"
SRC_LSP = ROOT / "src" / "pynescript" / "langserver"
PROVIDERS_DIR = SRC_LSP / "providers"
BUILD_DIR = ROOT / "scripts" / "build"
KEY_FILE = BUILD_DIR / ".metadata.key"
BINARY_NAME = "pynescript-lsp"
VSCODE_EXT = ROOT / "vscode-extension"


def run(cmd, cwd=None, env=None, capture=False):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    kwargs = dict(cwd=cwd, env=env or os.environ)
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"  FAILED: exit {result.returncode}")
        if capture and result.stderr:
            print(result.stderr)
        sys.exit(1)
    return result


def _resolve_fernet_key() -> bytes:
    """Stable Fernet key: CRYPTO_KEY env → .metadata.key → generate once."""
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


def stage_metadata():
    """Generate and encrypt metadata."""
    gen_script = ROOT / "scripts" / "generate_builtin_metadata.py"
    if gen_script.exists():
        run([sys.executable, str(gen_script)])

    from cryptography.fernet import Fernet

    key = _resolve_fernet_key()
    enc_path = PROVIDERS_DIR / "builtin_metadata.json.enc"
    plaintext = (PROVIDERS_DIR / "builtin_metadata.json").read_bytes()
    fernet = Fernet(key)
    encrypted = fernet.encrypt(plaintext)
    enc_path.write_bytes(encrypted)
    sha = hashlib.sha256(plaintext).hexdigest()[:16]
    (PROVIDERS_DIR / "builtin_metadata.json.sha256").write_text(sha + "\n")
    print(f"  Metadata: {len(plaintext) // 1024}KB -> encrypted")


def _package_version() -> str:
    """Read package version for Windows resource / product metadata."""
    about = ROOT / "src" / "pynescript" / "__about__.py"
    text = about.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("__version__"):
            # __version__ = "0.3.0"
            return line.split("=", 1)[1].strip().strip("\"'")
    return "0.0.0"


def compile_onefile(jobs: int) -> Path:
    """Build onefile LSP binary via Nuitka."""
    output_dir = DIST / "lsp"
    output_dir.mkdir(parents=True, exist_ok=True)
    jobs = jobs or max(1, multiprocessing.cpu_count() - 1)

    entry = SRC_LSP / "__main__.py"
    if not entry.is_file():
        raise FileNotFoundError(f"LSP entry not found: {entry}")

    version = _package_version()
    # Nuitka Windows version resource requires dotted numeric product/file version.
    # Accept pep440-ish versions by taking the leading X.Y.Z.
    version_core = version.split("+")[0].split("a")[0].split("b")[0].split("rc")[0]
    parts = [p for p in version_core.split(".") if p.isdigit()]
    while len(parts) < 3:
        parts.append("0")
    product_version = ".".join(parts[:4])  # Nuitka accepts up to 4 components

    # Prefer package name so Nuitka resolves imports under pynescript.*
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    env["PYTHONPATH"] = src_path + os.pathsep + env.get("PYTHONPATH", "")

    # Follow imports from the LSP entry only — do NOT force-include the whole
    # pynescript tree (compiler/numba bloat + broken cryptography rpaths on macOS).
    # Plaintext builtin_metadata.json is shipped; Fernet decrypt is optional.
    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--onefile",
        "--assume-yes-for-downloads",  # Dependency Walker / ccache on CI (no TTY)
        f"--output-dir={output_dir}",
        f"--output-filename={BINARY_NAME}",
        "--python-flag=no_site,no_docstrings",
        "--static-libpython=no",
        "--follow-imports",
        "--nofollow-import-to=numba",
        "--nofollow-import-to=llvmlite",
        "--nofollow-import-to=numpy",
        "--nofollow-import-to=pynescript.compiler",
        "--nofollow-import-to=pynescript.ast.evaluator",
        "--nofollow-import-to=cryptography",
        f"--include-data-dir={PROVIDERS_DIR}=pynescript/langserver/providers",
        "--lto=auto",
        f"--product-name={BINARY_NAME}",
        f"--product-version={product_version}",
        f"--file-version={product_version}",
        f"--file-description=PYNE Pine Script Language Server",
        f"--company-name=HOOX",
        f"--jobs={jobs}",
        "--remove-output",
        str(entry),
    ]

    run(cmd, env=env)

    candidates = [
        output_dir / BINARY_NAME,
        output_dir / f"{BINARY_NAME}.bin",
        output_dir / f"{BINARY_NAME}.exe",
        output_dir / f"{BINARY_NAME}.onefile.exe",
    ]
    binary = next((p for p in candidates if p.is_file()), None)
    if binary is None:
        matches = sorted(output_dir.glob(f"{BINARY_NAME}*"))
        binary = matches[0] if matches else None
    if binary is None or not binary.is_file():
        raise FileNotFoundError(f"Binary not found under {output_dir} (looked for {BINARY_NAME}*)")

    final_binary = DIST / binary.name
    if binary.resolve() != final_binary.resolve():
        shutil.move(str(binary), str(final_binary))
    print(f"  Binary: {final_binary} ({final_binary.stat().st_size / 1024 / 1024:.1f} MB)")
    return final_binary


def package_vsix(binary: Path) -> Path:
    """Build VSIX bundle."""
    vsix_file = DIST / "vsix" / f"pynescript-lsp.vsix"
    vsix_file.parent.mkdir(exist_ok=True)

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
        lsp_dir.mkdir(exist_ok=True)
        bin_copy = lsp_dir / binary.name
        shutil.copy2(binary, bin_copy)
        zf.write(bin_copy, f"pynescript-lsp/{binary.name}")

    print(f"  VSIX: {vsix_file} ({vsix_file.stat().st_size / 1024 / 1024:.1f} MB)")
    return vsix_file


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=None)
    parser.add_argument("--skip-vsix", action="store_true")
    parser.add_argument("--skip-metadata", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    jobs = args.jobs or max(1, multiprocessing.cpu_count() - 1)

    print("=" * 60)
    print("CI Build: Pynescript LSP")
    print(f"  Jobs: {jobs}")
    print(f"  Root: {ROOT}")
    print("=" * 60)

    if args.dry_run:
        print("[dry-run] Would run: metadata + compile + vsix")
        return

    DIST.mkdir(exist_ok=True)

    print("\n[1/3] Metadata...")
    if not args.skip_metadata:
        stage_metadata()
    else:
        print("  Skipped")

    print("\n[2/3] Compile...")
    binary = compile_onefile(jobs)

    print("\n[3/3] VSIX...")
    if not args.skip_vsix:
        package_vsix(binary)
    else:
        print("  Skipped")

    print(f"\n{'=' * 60}")
    print(f"Build complete!")
    print(f"  Binary: {DIST / BINARY_NAME}")
    print(f"  VSIX:   {DIST / 'vsix' / 'pynescript-lsp.vsix'}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
