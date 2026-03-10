import fitz

doc = fitz.open("data/input.pdf")

for page in doc:
    words_data = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                if not text:
                    continue
                words_data.append({
                    "text": text,
                    "x": span["origin"][0],
                    "y": span["origin"][1],
                    "size": span["size"],
                    "color": span["color"],
                    "bbox": span["bbox"]
                })

    # Erase original text
    for w in words_data:
        page.add_redact_annot(fitz.Rect(w["bbox"]))
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

    # Rewrite with Hindi-capable font
    for w in words_data:
        page.insert_text(
            (w["x"], w["y"]),
            w["text"],
            fontfile=r"font\static\NotoSansDevanagari-Regular.ttf",  # ← Hindi font
            fontname="NotoHindi",
            fontsize=w["size"],
            color=(0, 0, 0),
        )

doc.save("fixed.pdf")
print("Done!")