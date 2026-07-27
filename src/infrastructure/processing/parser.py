import re

from bs4 import BeautifulSoup


def clean_email_body(body_content: str) -> str:
    """
    Strips HTML tags, normalizes whitespace, and attempts to remove
    common signature blocks and quoted replies to save tokens.
    """
    if not body_content:
        return ""

    if (
        "<html" in body_content.lower()
        or "<body" in body_content.lower()
        or "<div" in body_content.lower()
    ):
        soup = BeautifulSoup(body_content, "html.parser")
        text = soup.get_text(separator="\n")
    else:
        text = body_content

    text = re.sub(r"\n\s*\n", "\n\n", text)

    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        line_strip = line.strip()

        if line_strip.startswith("On ") and "wrote:" in line_strip:
            break

        if line_strip == "--" or line_strip == "-- ":
            break

        if line_strip in ["________________________________", "--- Original Message ---"]:
            break

        if line_strip.startswith(">"):
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()
