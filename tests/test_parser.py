from src.infrastructure.processing.parser import clean_email_body


def test_clean_email_body_html():
    html = "<div><p>Hello World</p><br/>This is a test.</div>"
    res = clean_email_body(html)
    assert "Hello World" in res
    assert "This is a test." in res


def test_clean_email_body_signature():
    body = "Hello,\nHow are you?\n--\nLokesh Paidisetti\nSoftware Dev"
    res = clean_email_body(body)
    assert "Hello," in res
    assert "How are you?" in res
    assert "Lokesh" not in res
    assert "--" not in res


def test_clean_email_body_reply():
    body = "Hello John,\nLet's meet tomorrow.\nOn Mon, Jul 20, 2026 at 10:00 AM John wrote:\n> Sounds good."
    res = clean_email_body(body)
    assert "Let's meet tomorrow." in res
    assert "John wrote:" not in res
    assert "Sounds good" not in res


def test_clean_email_body_empty():
    assert clean_email_body("") == ""
    assert clean_email_body(None) == ""
