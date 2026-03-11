#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import json
from pathlib import Path

# --- NEW IMPORTS FOR DLA ---
import cv2
import fitz  # PyMuPDF
import numpy as np
from doclayout_yolo import YOLOv10
from huggingface_hub import hf_hub_download
# ---------------------------

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
        "1", # Required for better word grouping
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


def run_yolo_extraction(input_pdf: Path) -> str:
    """Runs DocLayout-YOLO and returns a JSON string of normalized block coordinates per page."""
    print("\n--- Starting YOLO Document Layout Analysis ---")
    model_path = hf_hub_download(
        repo_id="juliozhao/DocLayout-YOLO-DocStructBench", 
        filename="doclayout_yolo_docstructbench_imgsz1024.pt"
    )
    model = YOLOv10(model_path)
    
    doc = fitz.open(input_pdf)
    all_pages_data = []
    
    for page_num in range(len(doc)):
        print(f"Analyzing layout on page {page_num + 1}...")
        page = doc[page_num]
        
        # Render page to image at 300 DPI for YOLO
        pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # Predict layout
        det_res = model.predict(img_bgr, imgsz=1024, conf=0.2, device="cuda:0", verbose=False)
        boxes = det_res[0].boxes
        
        page_boxes = []
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            
            # Convert to Normalized Coordinates (0.0 to 1.0) so it works regardless of browser zoom
            nx1 = x1 / pix.width
            ny1 = y1 / pix.height
            nx2 = x2 / pix.width
            ny2 = y2 / pix.height
            
            page_boxes.append({
                "nx1": nx1, "ny1": ny1, "nx2": nx2, "ny2": ny2
            })
            
        all_pages_data.append(page_boxes)
        
    return json.dumps(all_pages_data)


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
    print("Running pdf2htmlEX command:")
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

    # --- ADVANCED YOLO + SPATIAL DOM MERGE INJECTION ---
    yolo_json = run_yolo_extraction(input_pdf)
    
    print("\nInjecting Spatial DOM Merge Script...")
    editor_script = f"""
    <script>
    document.addEventListener("DOMContentLoaded", function() {{
        // The exact coordinates mapped by DocLayout-YOLO
        const yoloData = {yolo_json};
        
        // Loop through each page generated by pdf2htmlEX
        document.querySelectorAll('.pc').forEach((pageContainer, pageIndex) => {{
            const pageBoxes = yoloData[pageIndex];
            if (!pageBoxes) return;
            
            // Allow relative positioning context
            pageContainer.style.position = 'relative';
            
            pageBoxes.forEach(box => {{
                // Get absolute dimensions of the page in the browser
                const pageRect = pageContainer.getBoundingClientRect();
                
                // Translate normalized YOLO coordinates to browser pixels
                const domX1 = box.nx1 * pageRect.width;
                const domY1 = box.ny1 * pageRect.height;
                const domX2 = box.nx2 * pageRect.width;
                const domY2 = box.ny2 * pageRect.height;
                
                let textNodes = [];
                let textContent = "";
                
                // Find all pdf2htmlEX text elements
                const textElements = pageContainer.querySelectorAll('.t');
                textElements.forEach(el => {{
                    const elRect = el.getBoundingClientRect();
                    
                    // Calculate center point of the text element relative to the page
                    const relX = elRect.left - pageRect.left + (elRect.width / 2);
                    const relY = elRect.top - pageRect.top + (elRect.height / 2);
                    
                    // If the text's center falls inside the YOLO box, it belongs to this paragraph
                    if (relX >= domX1 && relX <= domX2 && relY >= domY1 && relY <= domY2) {{
                        textNodes.push(el);
                        textContent += el.textContent + " ";
                    }}
                }});
                
                if (textNodes.length > 0) {{
                    // Create the new Master Editable Block
                    const editableBlock = document.createElement('div');
                    editableBlock.setAttribute('contenteditable', 'true');
                    
                    // Style it using percentages so it remains perfectly responsive if the window resizes
                    editableBlock.style.position = 'absolute';
                    editableBlock.style.left = (box.nx1 * 100) + '%';
                    editableBlock.style.top = (box.ny1 * 100) + '%';
                    editableBlock.style.width = ((box.nx2 - box.nx1) * 100) + '%';
                    editableBlock.style.minHeight = ((box.ny2 - box.ny1) * 100) + '%';
                    
                    // Core Editor CSS properties
                    editableBlock.style.zIndex = '100'; 
                    editableBlock.style.backgroundColor = 'rgba(255, 255, 255, 0.001)'; // Invisible but clickable
                    editableBlock.style.outline = 'none';
                    editableBlock.style.cursor = 'text';
                    editableBlock.style.whiteSpace = 'pre-wrap'; // Crucial for text wrapping
                    
                    // Steal the font styles from the first text node it swallowed
                    const baseStyle = window.getComputedStyle(textNodes[0]);
                    editableBlock.style.fontFamily = baseStyle.fontFamily;
                    editableBlock.style.color = baseStyle.color;
                    
                    // FIX: Measure the actual rendered height instead of the CSS font-size
                    const actualHeight = textNodes[0].getBoundingClientRect().height;
                    
                    // Set font size to roughly match the physical height (0.8 adjusts for standard line-height)
                    editableBlock.style.fontSize = (actualHeight * 0.8) + 'px';
                    editableBlock.style.lineHeight = '1.2';
                    
                    // Keep it contained
                    editableBlock.style.boxSizing = 'border-box';
                    editableBlock.style.overflow = 'hidden'; // Hides overflow until you click into it
                    
                    // Insert merged text
                    editableBlock.innerText = textContent.trim();
                    
                    // Visual feedback when editing
                    editableBlock.addEventListener('focus', () => {{ editableBlock.style.backgroundColor = 'rgba(255, 255, 0, 0.2)'; }});
                    editableBlock.addEventListener('blur', () => {{ editableBlock.style.backgroundColor = 'rgba(255, 255, 255, 0.001)'; }});
                    
                    pageContainer.appendChild(editableBlock);
                    
                    // Render original disconnected lines invisible (but don't delete to preserve CSS layouts)
                    textNodes.forEach(el => {{
                        el.style.opacity = '0';
                        el.style.pointerEvents = 'none'; // Prevent them from stealing clicks
                    }});
                }}
            }});
        }});
    }});
    </script>
    """
    
    with open(output_html, "a", encoding="utf-8") as f:
        f.write(editor_script)
    # ------------------------------------------------

    print(f"\nDone: {output_html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())