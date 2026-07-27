"""
Binary Attachment MIME Validator for Syntra AI Mail Agent.

Inspects the actual binary content of email attachments using magic byte
signatures to detect file type mismatches (e.g., an .exe disguised as a .pdf).

This module uses only Python standard library — no new dependencies.
No changes to the existing attachment processing pipeline are required;
this is called additively from EmailVerificationService._validate_attachments().
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# ── Magic byte signatures ──────────────────────────────────────────────────────
# Maps the first N bytes of a file to its actual type.
# Signatures ordered by specificity (longer patterns first where needed).

_MAGIC_SIGNATURES: List[Tuple[bytes, str]] = [
    # Executable / Dangerous
    (b"MZ",                              "exe/dll"),        # PE32 Windows executable
    (b"\x7fELF",                         "elf"),            # Linux ELF executable
    (b"\xca\xfe\xba\xbe",               "macho"),          # macOS Mach-O binary
    (b"#!/",                             "shell-script"),   # Shell script shebang
    (b"#!",                              "script"),         # Generic script shebang
    # Office / Macro-capable
    (b"PK\x03\x04",                     "zip-based"),      # ZIP (DOCX/XLSX/PPTX/JAR/APK)
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "ole-compound"),# OLE2 (DOC/XLS/PPT — legacy Office)
    # Documents
    (b"%PDF",                            "pdf"),
    # Archives
    (b"Rar!\x1a\x07",                   "rar"),
    (b"\x1f\x8b",                        "gzip"),
    (b"BZh",                             "bzip2"),
    (b"\xfd7zXZ\x00",                   "xz"),
    (b"7z\xbc\xaf\x27\x1c",            "7zip"),
    # Images
    (b"\xff\xd8\xff",                    "jpeg"),
    (b"\x89PNG\r\n\x1a\n",             "png"),
    (b"GIF87a",                          "gif"),
    (b"GIF89a",                          "gif"),
    (b"BM",                              "bmp"),
    (b"RIFF",                            "riff"),           # WAV/AVI
    # Java
    (b"\xca\xfe\xba\xbe",              "java-class"),      # Java class (same as macho — context-dependent)
]

# ── Extension to expected type groups ─────────────────────────────────────────
# Maps declared file extensions to the set of acceptable detected types.

_EXTENSION_ALLOWED_TYPES: Dict[str, List[str]] = {
    ".pdf":  ["pdf"],
    ".jpg":  ["jpeg"],
    ".jpeg": ["jpeg"],
    ".png":  ["png"],
    ".gif":  ["gif"],
    ".bmp":  ["bmp"],
    ".docx": ["zip-based"],   # Modern Office
    ".xlsx": ["zip-based"],
    ".pptx": ["zip-based"],
    ".doc":  ["ole-compound", "zip-based"],
    ".xls":  ["ole-compound", "zip-based"],
    ".ppt":  ["ole-compound", "zip-based"],
    ".zip":  ["zip-based"],
    ".rar":  ["rar"],
    ".7z":   ["7zip"],
    ".gz":   ["gzip"],
    ".tar":  ["gzip", "xz", "bzip2"],
    ".txt":  [],              # text has no reliable magic bytes — skip
    ".csv":  [],
    ".json": [],
    ".xml":  [],
    ".html": [],
}

# Types that are always dangerous regardless of extension
_ALWAYS_DANGEROUS_TYPES = {"exe/dll", "elf", "macho", "shell-script", "script", "java-class"}


@dataclass
class MimeValidationResult:
    filename: str
    declared_extension: str
    detected_type: Optional[str]
    is_mismatch: bool
    is_dangerous: bool
    risk_note: str


def detect_type_from_bytes(payload: bytes) -> Optional[str]:
    """
    Detect the actual file type from the first bytes of the payload
    using magic byte signatures.

    Returns the detected type string, or None if unrecognized.
    """
    for magic, file_type in _MAGIC_SIGNATURES:
        if payload.startswith(magic):
            return file_type
    return None


def validate_attachment(filename: str, payload: bytes) -> MimeValidationResult:
    """
    Validate a single attachment's actual binary type against its declared extension.

    Args:
        filename: Original filename of the attachment.
        payload:  Raw binary content of the attachment.

    Returns:
        MimeValidationResult with mismatch and danger flags.
    """
    _, ext = os.path.splitext(filename.lower())
    detected = detect_type_from_bytes(payload) if payload else None

    is_dangerous = detected in _ALWAYS_DANGEROUS_TYPES
    is_mismatch = False
    risk_note = ""

    if is_dangerous:
        risk_note = (
            f"Attachment '{filename}' contains a {detected} binary "
            f"(declared as '{ext or 'unknown'}') — executable content detected."
        )
        is_mismatch = True
    elif detected and ext in _EXTENSION_ALLOWED_TYPES:
        allowed = _EXTENSION_ALLOWED_TYPES[ext]
        if allowed and detected not in allowed:
            is_mismatch = True
            risk_note = (
                f"Attachment '{filename}' extension is '{ext}' but binary content "
                f"appears to be '{detected}' — possible file type spoofing."
            )

    return MimeValidationResult(
        filename=filename,
        declared_extension=ext,
        detected_type=detected,
        is_mismatch=is_mismatch,
        is_dangerous=is_dangerous,
        risk_note=risk_note,
    )


def validate_attachments(
    attachment_mime_info: List[Dict],
) -> List[MimeValidationResult]:
    """
    Validate a list of attachment metadata entries.

    Args:
        attachment_mime_info: List of dicts from EmailMetadata.attachment_mime_info.
                              Each dict: {"filename": str, "payload": bytes, "size": int}

    Returns:
        List of MimeValidationResult for each attachment that had a payload.
    """
    results = []
    for info in attachment_mime_info:
        filename = info.get("filename", "unknown")
        payload = info.get("payload", b"")
        if filename and payload:
            results.append(validate_attachment(filename, payload))
    return results
