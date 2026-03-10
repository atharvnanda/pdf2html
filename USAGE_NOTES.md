# PDF to HTML with your local MSYS2-built `pdf2htmlEX`

This project now targets your confirmed local Windows build of `pdf2htmlEX`.

Default executable:

```text
C:\msys64\home\anjan\pdf2htmlEX\pdf2htmlEX\build\pdf2htmlEX.exe
```

Default data directory:

```text
C:\msys64\home\anjan\pdf2htmlEX\pdf2htmlEX\build\data
```

The wrapper is set up so the normal command is simply:

```bash
python convert_pdf.py input.pdf output.html
```

It keeps the same fidelity-focused `pdf2htmlEX` flags for newspaper/ePaper-style PDFs.

---

## 1. What the script does automatically now

When you run:

```bash
python convert_pdf.py input.pdf output.html
```

the script will:

1. call your local `pdf2htmlEX.exe`
2. automatically prepare and pass your build's `data` directory
3. prepend likely MSYS2 runtime DLL folders to `PATH`
4. generate one self-contained HTML file using fidelity-first flags

For your current newspaper/ePaper PDF, the wrapper now defaults to **`--no-fallback`** because your local build was producing **selectable but invisible text** in fallback mode.

This means you do **not** have to type the `.exe` path every time.

---

## 2. Important note about `data-dir`

`data-dir` is **not** your PDF input folder.

It is used by `pdf2htmlEX` for its own internal files, such as:

- manifest
- CSS templates
- JS helpers
- bundled support assets

So:

- your **input PDF** can live anywhere
- your **output HTML** can live anywhere
- `data-dir` just points to `pdf2htmlEX`'s resource files

If `build\data` does not already exist, the wrapper will automatically populate it from:

- `pdf2htmlEX\share`
- `poppler-data`

Example:

```bash
python convert_pdf.py D:\papers\epaper.pdf D:\papers\epaper.html
```

That does **not** require `D:\papers` to be inside the build `data` folder.

---

## 3. Python venv usage

Your Python venv is still fine to use.

This script uses only the Python standard library.

Example:

```bash
python -m venv .venv
.venv\Scripts\activate
python convert_pdf.py input.pdf output.html
```

---

## 4. Basic usage

### Standard usage

```bash
python convert_pdf.py input.pdf output.html
```

### Example

```bash
python convert_pdf.py D:\docs\newspaper.pdf D:\docs\newspaper.html
```

### If you ever want to override the executable path manually

```bash
python convert_pdf.py input.pdf output.html --pdf2htmlex-bin "C:\msys64\home\anjan\pdf2htmlEX\pdf2htmlEX\build\pdf2htmlEX.exe"
```

### If you ever want to override the data directory manually

```bash
python convert_pdf.py input.pdf output.html --data-dir "C:\msys64\home\anjan\pdf2htmlEX\pdf2htmlEX\build\data"
```

---

## 5. Exact CLI command pattern used by the script

The wrapper prints the exact command before running it.

A typical command will look like this:

```bash
"C:\msys64\home\anjan\pdf2htmlEX\pdf2htmlEX\build\pdf2htmlEX.exe" --data-dir "C:\msys64\home\anjan\pdf2htmlEX\pdf2htmlEX\build\data" --embed-css 1 --embed-font 1 --embed-image 1 --embed-javascript 1 --embed-outline 0 --split-pages 0 --process-nontext 1 --process-outline 0 --printing 1 --fallback 0 --optimize-text 0 --correct-text-visibility 1 --embed-external-font 1 --font-format woff --font-size-multiplier 4.0 --space-as-offset 0 --tounicode 0 --use-cropbox 1 --bg-format png --clean-tmp 1 --debug 0 --dest-dir "D:\docs" "D:\docs\input.pdf" output.html
```

The wrapper also prepares the subprocess `PATH` so the MSYS2-built executable can find runtime DLLs.

Note: your current local build exposes `--dpi` in `--help` rather than separate `--hdpi` / `--vdpi`. The wrapper detects this automatically and uses the compatible flag.

---

## 6. Why these flags were chosen

These defaults prioritize **layout fidelity** over output size.

- `--embed-css 1`  
  Keep CSS inside the HTML.

- `--embed-font 1`  
  Embed extracted fonts into the HTML.

- `--embed-image 1`  
  Embed images/background assets into the HTML.

- `--embed-javascript 1`  
  Keep generated JS inside the HTML.

- `--split-pages 0`  
  Produce a single HTML file.

- `--fallback 0` by default  
  For your local build and current PDF, this avoids the case where text remains selectable but is rendered transparent. You can still turn fallback on manually for difficult files.

- `--optimize-text 0`  
  Disables aggressive text merging/reduction that can disturb layout.

- `--correct-text-visibility 1`  
  Helps avoid hidden/covered text showing through incorrectly.

- `--embed-external-font 1`  
  Embeds matched local fonts when the PDF did not embed them.

- `--font-size-multiplier 4.0`  
  Helps browsers preserve small text metrics better.

- `--tounicode 0`  
  Tries to balance correct rendering with selectable/copyable text.

- `--use-cropbox 1`  
  Usually matches intended visible page bounds.

- `--bg-format png`  
  Safe high-fidelity default for non-text content.

- `--hdpi 216 --vdpi 216`  
  Higher-than-default image DPI for layout-heavy PDFs.

---

## 7. Notes about Hindi / Devanagari support

`pdf2htmlEX` can preserve Hindi text **when the original PDF has valid embedded fonts and usable Unicode mappings**.

Important practical limits:

1. If the PDF has a proper text layer and valid fonts, Hindi text can remain selectable.
2. If the PDF uses broken subset fonts or bad ToUnicode mappings, visual output may still look okay while copy/paste becomes wrong.
3. If the PDF is actually scanned images, text will not become selectable without OCR.

For Hindi-heavy PDFs, first try:

```bash
python convert_pdf.py input.pdf output.html --tounicode 1
```

If visual rendering becomes worse, switch back to the default `--tounicode 0`.

If fonts are missing on your local system, install Devanagari-capable fonts such as **Noto Sans Devanagari** or **Noto Serif Devanagari** where your `pdf2htmlEX` installation can see them.

---

## 8. Troubleshooting

### A. `pdf2htmlEX` executable not found

Make sure this file exists:

```text
C:\msys64\home\anjan\pdf2htmlEX\pdf2htmlEX\build\pdf2htmlEX.exe
```

If you moved it, pass the explicit path with `--pdf2htmlex-bin`.

### B. `data-dir` not found / manifest or resource errors

Make sure this directory exists:

```text
C:\msys64\home\anjan\pdf2htmlEX\pdf2htmlEX\build\data
```

The wrapper will try to create/populate it automatically from the adjacent source tree. If your build tree moved, pass the correct directory with `--data-dir`.

### C. MSYS2 DLL / runtime errors

If you see errors about missing DLLs when running from normal Windows Python, it means the MSYS2 runtime or MinGW DLLs are not visible.

The wrapper already prepends these if they exist:

```text
C:\msys64\mingw64\bin
C:\msys64\ucrt64\bin
C:\msys64\usr\bin
```

If you still hit DLL issues, verify that your actual runtime DLLs are in one of those folders.

### D. Hindi characters render as boxes / wrong glyphs

Possible reasons:

1. the PDF did not embed the required fonts
2. your local system does not have a suitable fallback font
3. the PDF contains broken character maps

Try:

```bash
python convert_pdf.py input.pdf output.html --tounicode 1
```

And ensure Devanagari fonts are available to the local `pdf2htmlEX` installation.

### E. Text is not selectable

This often means:

1. the PDF is scanned/image-only
2. the PDF uses bad encodings
3. some text had to be moved to the background layer for fidelity

Try:

```bash
python convert_pdf.py input.pdf output.html --correct-text-visibility 0
```

But note that this can make hidden text show through.

### E2. Text is selectable but not visible

This is the exact issue you hit.

Cause:

- in fallback mode, your generated HTML used transparent text color classes like `.fc0{color:transparent;}`
- the layout/background was preserved, but visible foreground text was not rendered properly

Fix:

```bash
python convert_pdf.py input.pdf output.html --no-fallback
```

The wrapper now uses this as the default behavior.

### F. Layout spacing drifts or columns overlap

Try:

```bash
python convert_pdf.py input.pdf output.html --hdpi 288 --vdpi 288
```

If your local build only supports `--dpi`, the wrapper automatically maps these values to a single DPI value.

or:

```bash
python convert_pdf.py input.pdf output.html --zoom 1.5
```

Advanced experiment for difficult PDFs:

```bash
python convert_pdf.py input.pdf output.html --zoom 25 --font-size-multiplier 1
```

### G. Output HTML is too large

That is expected for single-file high-fidelity output.

To reduce size:

```bash
python convert_pdf.py input.pdf output.html --hdpi 144 --vdpi 144 --no-fallback
```

If you specifically want to retry the older fallback rendering mode for a different PDF:

```bash
python convert_pdf.py input.pdf output.html --fallback
```

### H. Conversion fails on a specific PDF

Run with debug enabled:

```bash
python convert_pdf.py input.pdf output.html --debug
```

Then copy and run the exact printed command directly.

---

## 9. Summary

This updated setup gives you:

- no Docker requirement
- a Python wrapper that works fine from a venv
- a direct call to your local MSYS2-built `pdf2htmlEX` executable
- automatic `data-dir` wiring
- automatic MSYS2 runtime PATH bootstrapping
- a single self-contained HTML output
- layout-fidelity-focused defaults suitable for newspaper/ePaper PDFs