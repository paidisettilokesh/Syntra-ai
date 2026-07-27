from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.processing.ocr import process_attachment


@pytest.mark.asyncio
async def test_process_attachment_txt():
    payload = b"Hello, this is a plain text attachment."
    res = await process_attachment("test.txt", payload)
    assert res == "Hello, this is a plain text attachment."


@pytest.mark.asyncio
@patch("src.infrastructure.processing.ocr.docx.Document")
async def test_process_attachment_docx(mock_doc_cls):
    mock_para1 = MagicMock()
    mock_para1.text = "Hello DOCX Paragraph 1"
    mock_para2 = MagicMock()
    mock_para2.text = "Hello DOCX Paragraph 2"

    mock_doc = MagicMock()
    mock_doc.paragraphs = [mock_para1, mock_para2]
    mock_doc_cls.return_value = mock_doc

    res = await process_attachment("test.docx", b"dummy")
    assert res == "Hello DOCX Paragraph 1\nHello DOCX Paragraph 2"


@pytest.mark.asyncio
@patch("src.infrastructure.processing.ocr.pdfplumber.open")
async def test_process_attachment_pdf_plumber(mock_pdf_open):
    mock_page1 = MagicMock()
    mock_page1.extract_text.return_value = "PDF Page 1 Text"

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page1]
    mock_pdf_open.return_value.__enter__.return_value = mock_pdf

    res = await process_attachment("test.pdf", b"dummy")
    assert res == "PDF Page 1 Text"


@pytest.mark.asyncio
@patch("src.infrastructure.processing.ocr.pytesseract.image_to_string")
@patch("src.infrastructure.processing.ocr.Image.open")
async def test_process_attachment_image(mock_image_open, mock_tesseract):
    mock_tesseract.return_value = "Extracted Image OCR Text"
    res = await process_attachment("test.png", b"dummy")
    assert res == "Extracted Image OCR Text"


@pytest.mark.asyncio
@patch("src.infrastructure.processing.ocr.pdfplumber.open")
@patch("src.infrastructure.processing.ocr.pytesseract.image_to_string")
@patch("fitz.open")
@patch("src.infrastructure.processing.ocr.Image.open")
async def test_process_attachment_pdf_fallback(
    mock_image_open, mock_fitz_open, mock_tesseract, mock_pdf_open
):
    # 1. Standard text extraction returns empty/short text
    mock_page1 = MagicMock()
    mock_page1.extract_text.return_value = "   "  # short text triggers fallback
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page1]
    mock_pdf_open.return_value.__enter__.return_value = mock_pdf

    # 2. Mock fitz (PyMuPDF) loading
    mock_doc = MagicMock()
    mock_doc.__len__.return_value = 1
    mock_page = MagicMock()
    mock_pix = MagicMock()
    mock_pix.tobytes.return_value = b"image_data"
    mock_page.get_pixmap.return_value = mock_pix
    mock_doc.load_page.return_value = mock_page
    mock_fitz_open.return_value = mock_doc

    # 3. Mock Image open and Tesseract OCR response
    mock_image_open.return_value = MagicMock()
    mock_tesseract.return_value = "Fallback OCR Text"

    res = await process_attachment("test.pdf", b"dummy")
    assert "Fallback OCR Text" in res


@pytest.mark.asyncio
@patch("src.infrastructure.processing.ocr.docx.Document")
async def test_process_attachment_graceful_error_handling(mock_doc_cls):
    # Raise error during document parsing
    mock_doc_cls.side_effect = Exception("Parsing error")
    res = await process_attachment("test.docx", b"dummy")
    assert res == ""  # gracefully falls back to empty string
