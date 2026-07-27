import asyncio
import io
import os

import docx
import pdfplumber
import pytesseract
from PIL import Image


def _sync_ocr_pdf(payload: bytes) -> str:
    text_content = ""
    with pdfplumber.open(io.BytesIO(payload)) as pdf:
        pages_text = []
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                pages_text.append(page_text)
        text_content = "\n".join(pages_text)

        if len(text_content.strip()) < 20:
            try:
                import fitz  # PyMuPDF

                doc = fitz.open(stream=payload, filetype="pdf")
                for page_num in range(min(3, len(doc))):  # Only OCR up to first 3 pages
                    page = doc.load_page(page_num)
                    pix = page.get_pixmap()
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    text_content += "\n" + pytesseract.image_to_string(img)
            except Exception:
                pass
    return text_content


def _sync_ocr_image(payload: bytes) -> str:
    image = Image.open(io.BytesIO(payload))
    return pytesseract.image_to_string(image)


async def process_attachment(filename: str, payload: bytes) -> str:
    """
    Attempts to extract text from a given attachment payload asymptotically.
    Supports PDF, DOCX, TXT, and Images (PNG, JPG, JPEG).
    """
    ext = os.path.splitext(filename)[1].lower()
    text_content = ""

    try:
        if ext == ".txt":
            text_content = payload.decode("utf-8", errors="ignore")

        elif ext == ".docx":
            doc = docx.Document(io.BytesIO(payload))
            text_content = "\n".join([para.text for para in doc.paragraphs])

        elif ext == ".pdf":
            text_content = await asyncio.to_thread(_sync_ocr_pdf, payload)

        elif ext in [".png", ".jpg", ".jpeg"]:
            text_content = await asyncio.to_thread(_sync_ocr_image, payload)

    except Exception:
        pass  # Ignore attachment errors

    return text_content.strip()
