#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_BIN = r"C:/msys64/home/anjan/pdf2htmlEX/pdf2htmlEX/build/pdf2htmlEX.exe"
DEFAULT_DATA_DIR = r"C:/msys64/home/anjan/pdf2htmlEX/pdf2htmlEX/build/data"
DEFAULT_MSYS_PATHS = [
    r"C:/msys64/mingw64/bin",
    r"C:/msys64/ucrt64/bin",
    r"C:/msys64/usr/bin",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a PDF into a single self-contained HTML file using "
            "a locally installed pdf2htmlEX executable."
        )
    )
    parser.add_argument("input_pdf", type=Path, help="Source PDF file")
    parser.add_argument("output_html", type=Path, help="Destination HTML file")
    parser.add_argument(
        "--pdf2htmlex-bin",
        default=DEFAULT_BIN,
        help=(
            "Path or command name for the locally installed pdf2htmlEX executable. "
            f"Default: {DEFAULT_BIN}"
        ),
    )
    parser.add_argument(
        "--data-dir",
        default=DEFAULT_DATA_DIR,
        help=(
            "pdf2htmlEX resource directory containing manifest/CSS/JS assets. "
            f"Default: {DEFAULT_DATA_DIR}"
        ),
    )
    parser.add_argument(
        "--zoom",
        type=float,
        default=None,
        help="Optional pdf2htmlEX zoom factor. Leave unset to preserve normal page scale.",
    )
    parser.add_argument(
        "--hdpi",
        type=int,
        default=216,
        help="Background image horizontal DPI. Higher = better fidelity, bigger output.",
    )
    parser.add_argument(
        "--vdpi",
        type=int,
        default=216,
        help="Background image vertical DPI. Higher = better fidelity, bigger output.",
    )
    parser.add_argument(
        "--bg-format",
        choices=["png", "jpg", "svg"],
        default="png",
        help="Background format for non-text objects. png is the safest fidelity choice.",
    )
    parser.add_argument(
        "--font-format",
        default="woff",
        help="Embedded font format produced by pdf2htmlEX. Default: woff",
    )
    parser.add_argument(
        "--font-size-multiplier",
        type=float,
        default=4.0,
        help="Helps browsers preserve tiny text metrics. Default: 4.0",
    )
    parser.add_argument(
        "--correct-text-visibility",
        type=int,
        choices=[0, 1, 2],
        default=1,
        help="How aggressively pdf2htmlEX moves occluded text to the background layer. Default: 1",
    )
    parser.add_argument(
        "--tounicode",
        type=int,
        choices=[-1, 0, 1],
        default=0,
        help="Character mapping mode. 0 balances copy/paste and rendering. Default: 0",
    )

    fallback_group = parser.add_mutually_exclusive_group()
    fallback_group.add_argument(
        "--fallback",
        dest="fallback",
        action="store_true",
        help="Enable pdf2htmlEX fallback mode for difficult PDFs that need it.",
    )
    fallback_group.add_argument(
        "--no-fallback",
        dest="fallback",
        action="store_false",
        help="Disable fallback mode (default). This is safer when text becomes selectable but invisible.",
    )
    parser.set_defaults(fallback=False)

    debug_group = parser.add_mutually_exclusive_group()
    debug_group.add_argument(
        "--debug",
        dest="debug",
        action="store_true",
        help="Enable pdf2htmlEX debug output and keep the exact command visible.",
    )
    debug_group.add_argument(
        "--no-debug",
        dest="debug",
        action="store_false",
        help="Disable pdf2htmlEX debug output (default).",
    )
    parser.set_defaults(debug=False)

    clean_group = parser.add_mutually_exclusive_group()
    clean_group.add_argument(
        "--keep-tmp",
        dest="clean_tmp",
        action="store_false",
        help="Keep pdf2htmlEX temporary files for troubleshooting.",
    )
    clean_group.add_argument(
        "--clean-tmp",
        dest="clean_tmp",
        action="store_true",
        help="Remove temporary files after conversion (default).",
    )
    parser.set_defaults(clean_tmp=True)

    return parser


def quote_command(parts: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(parts)
    try:
        import shlex

        return shlex.join(parts)
    except Exception:
        return " ".join(parts)


def fail(message: str, exit_code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def resolve_executable(executable: str) -> str:
    candidate = Path(executable)
    if candidate.exists():
        return str(candidate.resolve())

    resolved = shutil.which(executable)
    if resolved:
        return resolved

    fail(
        "pdf2htmlEX executable not found. Install pdf2htmlEX locally and ensure it is on PATH, "
        "or pass its full path with --pdf2htmlex-bin.\n\n"
        "A Python venv can hold this wrapper script, but pdf2htmlEX itself is a native binary, not a pip package."
    )


def resolve_data_dir(data_dir: str) -> str:
    candidate = Path(data_dir)
    if candidate.exists() and candidate.is_dir():
        return str(candidate.resolve())

    fail(
        f"pdf2htmlEX data directory was not found: {data_dir}\n\n"
        "This directory contains manifest/CSS/JS resources used by pdf2htmlEX."
    )


def sync_tree_contents(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def prepare_data_dir(data_dir: str, executable: str) -> str:
    candidate = Path(data_dir)

    exe_path = Path(executable).resolve()
    project_root = exe_path.parent.parent
    share_dir = project_root / "share"
    pdfjs_dir = project_root / "3rdparty" / "PDF.js"
    poppler_data_dir = project_root.parent / "poppler-data"

    if not share_dir.exists():
        fail(
            "Unable to prepare pdf2htmlEX data directory automatically because the share directory was not found: "
            f"{share_dir}"
        )

    candidate.mkdir(parents=True, exist_ok=True)
    sync_tree_contents(share_dir, candidate)

    if pdfjs_dir.exists() and pdfjs_dir.is_dir():
        for name in ["compatibility.js", "compatibility.min.js"]:
            source = pdfjs_dir / name
            if source.exists() and source.is_file():
                shutil.copy2(source, candidate / name)

    if poppler_data_dir.exists() and poppler_data_dir.is_dir():
        sync_tree_contents(poppler_data_dir, candidate / "poppler")

    required_files = [candidate / "manifest", candidate / "compatibility.min.js"]
    missing = [str(path) for path in required_files if not path.exists()]
    if missing:
        fail(
            "Failed to prepare pdf2htmlEX data directory. Missing required resource files: "
            + ", ".join(missing)
        )

    return str(candidate.resolve())


def resolve_paths(input_pdf: Path, output_html: Path) -> tuple[Path, Path]:
    input_pdf = input_pdf.expanduser().resolve()
    output_html = output_html.expanduser().resolve()

    if not input_pdf.exists():
        fail(f"Input PDF does not exist: {input_pdf}")
    if not input_pdf.is_file():
        fail(f"Input path is not a file: {input_pdf}")
    if input_pdf.suffix.lower() != ".pdf":
        print(f"WARNING: Input file does not end with .pdf: {input_pdf}", file=sys.stderr)

    output_html.parent.mkdir(parents=True, exist_ok=True)
    return input_pdf, output_html


def build_runtime_env() -> dict[str, str]:
    env = os.environ.copy()
    extra_dirs = [path for path in DEFAULT_MSYS_PATHS if Path(path).exists()]
    if extra_dirs:
        current_path = env.get("PATH", "")
        env["PATH"] = os.pathsep.join(extra_dirs + ([current_path] if current_path else []))
    return env


def get_supported_options(executable: str, data_dir: str, env: dict[str, str]) -> set[str]:
    result = subprocess.run(
        [executable, "--data-dir", data_dir, "--help"],
        check=False,
        capture_output=True,
        env=env,
    )
    help_text = (result.stdout or b"") + b"\n" + (result.stderr or b"")
    decoded = help_text.decode("utf-8", errors="ignore")
    options: set[str] = set()
    for line in decoded.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            option = stripped.split()[0].rstrip(",")
            options.add(option)
        elif ",--" in stripped:
            option = stripped.split(",--", 1)[1].split()[0].rstrip(",")
            options.add(f"--{option}")
    return options


def build_command(
    executable: str,
    args: argparse.Namespace,
    input_pdf: Path,
    output_html: Path,
    supported_options: set[str],
) -> list[str]:
    pdf2html_args: list[str] = [
        executable,
        "--data-dir",
        args.data_dir,
        "--embed-css",
        "1",
        "--embed-font",
        "1",
        "--embed-image",
        "1",
        "--embed-javascript",
        "1",
        "--embed-outline",
        "0",
        "--split-pages",
        "0",
        "--process-nontext",
        "1",
        "--process-outline",
        "0",
        "--printing",
        "1",
        "--fallback",
        "1" if args.fallback else "0",
        "--optimize-text",
        "0",
        "--correct-text-visibility",
        str(args.correct_text_visibility),
        "--embed-external-font",
        "1",
        "--font-format",
        args.font_format,
        "--font-size-multiplier",
        str(args.font_size_multiplier),
        "--space-as-offset",
        "0",
        "--tounicode",
        str(args.tounicode),
        "--use-cropbox",
        "1",
        "--bg-format",
        args.bg_format,
        "--clean-tmp",
        "1" if args.clean_tmp else "0",
        "--debug",
        "1" if args.debug else "0",
        "--dest-dir",
        str(output_html.parent),
    ]

    if "--hdpi" in supported_options and "--vdpi" in supported_options:
        pdf2html_args.extend(["--hdpi", str(args.hdpi), "--vdpi", str(args.vdpi)])
    elif "--dpi" in supported_options:
        if args.hdpi != args.vdpi:
            print(
                "WARNING: This pdf2htmlEX build supports only --dpi, not separate --hdpi/--vdpi. "
                f"Using dpi={max(args.hdpi, args.vdpi)}.",
                file=sys.stderr,
            )
        pdf2html_args.extend(["--dpi", str(max(args.hdpi, args.vdpi))])
    else:
        print(
            "WARNING: Could not detect DPI option support in pdf2htmlEX help output. "
            f"Falling back to --dpi {max(args.hdpi, args.vdpi)}.",
            file=sys.stderr,
        )
        pdf2html_args.extend(["--dpi", str(max(args.hdpi, args.vdpi))])

    if args.zoom is not None:
        pdf2html_args.extend(["--zoom", str(args.zoom)])

    pdf2html_args.extend([str(input_pdf), output_html.name])
    return pdf2html_args


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_pdf, output_html = resolve_paths(args.input_pdf, args.output_html)
    executable = resolve_executable(args.pdf2htmlex_bin)
    args.data_dir = prepare_data_dir(args.data_dir, executable)
    args.data_dir = resolve_data_dir(args.data_dir)
    env = build_runtime_env()
    supported_options = get_supported_options(executable, args.data_dir, env)

    command = build_command(executable, args, input_pdf, output_html, supported_options)
    print("Running command:")
    print(quote_command(command))

    completed = subprocess.run(command, check=False, env=env)
    if completed.returncode != 0:
        fail(
            "pdf2htmlEX conversion failed. Common causes: the local pdf2htmlEX installation is incomplete, "
            "required fonts are missing, the MSYS2 runtime DLL paths are unavailable, or the PDF uses broken/custom encodings.",
            completed.returncode,
        )

    if not output_html.exists():
        fail(f"Conversion finished but output file was not created: {output_html}")

    print(f"\nDone: {output_html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())