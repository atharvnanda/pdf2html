# import cv2
# import fitz  # PyMuPDF
# import numpy as np
# from doclayout_yolo import YOLOv10
# from huggingface_hub import hf_hub_download

# # 1. Fix the Bug: Explicitly download the weights file
# print("Loading model weights...")
# model_path = hf_hub_download(
#     repo_id="juliozhao/DocLayout-YOLO-DocStructBench", 
#     filename="doclayout_yolo_docstructbench_imgsz1024.pt"
# )

# # Load the model using the physical file path instead of from_pretrained
# model = YOLOv10(model_path)

# # 2. Use PyMuPDF to get an image of the first PDF page
# print("Extracting PDF image...")
# doc = fitz.open("data/input.pdf")
# pix = doc[0].get_pixmap(matrix=fitz.Matrix(300/72, 300/72)) # 300 DPI

# # Convert the PyMuPDF image to a format YOLO and OpenCV understand (NumPy Array)
# img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
# img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

# # 3. Perform prediction directly on the image array
# print("Running layout detection...")
# det_res = model.predict(
#     img_bgr,           
#     imgsz=1024,        
#     conf=0.2,          
#     device="cuda:0"    
# )

# # 4. Annotate and save the result
# print("Drawing boxes and saving...")
# annotated_frame = det_res[0].plot(pil=True, line_width=3, font_size=15)
# cv2.imwrite("yolo-result.jpg", annotated_frame)
# print("Saved successfully to yolo-result.jpg")


# RENDERING LAYOUT DIRECTLY ON PDF

import fitz  # PyMuPDF
import cv2
import numpy as np
from doclayout_yolo import YOLOv10
from huggingface_hub import hf_hub_download

# 1. Configuration
PDF_PATH = "data/input.pdf"
OUTPUT_PDF = "output_annotated.pdf"
DPI = 300
ZOOM = DPI / 72  # Scaling factor: Pixels to Points

def annotate_pdf():
    # 2. Load Model
    print("Loading model weights...")
    model_path = hf_hub_download(
        repo_id="juliozhao/DocLayout-YOLO-DocStructBench", 
        filename="doclayout_yolo_docstructbench_imgsz1024.pt"
    )
    model = YOLOv10(model_path)

    # 3. Open PDF and prepare for image extraction
    print("Extracting PDF image...")
    doc = fitz.open(PDF_PATH)
    page = doc[0]  # First page
    
    # Render PDF page to image at 300 DPI
    matrix = fitz.Matrix(ZOOM, ZOOM)
    pix = page.get_pixmap(matrix=matrix)
    img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

    # 4. Run Inference on the image
    print("Running layout detection...")
    det_res = model.predict(img_bgr, imgsz=1024, conf=0.2, device="cuda:0")
    
    # 5. Map coordinates and draw directly onto the PDF
    print("Mapping coordinates and drawing on PDF...")
    boxes = det_res[0].boxes
    names = det_res[0].names
    
    for box in boxes:
        # Get coordinates in Image Pixels
        x1_img, y1_img, x2_img, y2_img = box.xyxy[0].tolist()
        label = names[int(box.cls[0])]
        
        # Scale down to PDF Points
        x1_pdf = x1_img / ZOOM
        y1_pdf = y1_img / ZOOM
        x2_pdf = x2_img / ZOOM
        y2_pdf = y2_img / ZOOM
        
        # Create PyMuPDF Rectangle
        rect = fitz.Rect(x1_pdf, y1_pdf, x2_pdf, y2_pdf)
        
        # Draw the rectangle on the PDF (Red color)
        page.draw_rect(rect, color=(1, 0, 0), width=1)
        
        # Insert the label text right above the box
        page.insert_text(
            fitz.Point(rect.x0, rect.y0 - 2), 
            label, 
            fontsize=8, 
            color=(1, 0, 0)
        )

    # 6. Save the newly annotated PDF
    doc.save(OUTPUT_PDF)
    print(f"Success! Check the bounding boxes in: {OUTPUT_PDF}")

if __name__ == "__main__":
    annotate_pdf()