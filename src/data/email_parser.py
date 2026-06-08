import base64
import re

from bs4 import BeautifulSoup

__all__ = [
    "decode_b64url",
    "extract_body",
    "clean_body",
    "extract_auth_status",
]


def decode_b64url(data: str) -> str:
    if not data:
        return ""
    padded = data + ("=" * (-len(data) % 4))
    decoded_bytes = base64.urlsafe_b64decode(padded.encode("utf-8"))
    return decoded_bytes.decode("utf-8", errors="ignore")


def extract_body(payload: dict) -> str:
    plain_text = ""
    html_text = ""
    queue = [payload]

    while queue:
        part = queue.pop(0)
        mime_type = (part.get("mimeType") or "").lower()
        body_data = part.get("body", {}).get("data", "")

        if body_data:
            decoded = decode_b64url(body_data)
            if mime_type == "text/plain" and not plain_text:
                plain_text = decoded
            elif mime_type == "text/html" and not html_text:
                html_text = BeautifulSoup(decoded, "lxml").get_text(" ", strip=True)
            elif not plain_text and not html_text:
                plain_text = decoded

        subparts = part.get("parts", [])
        if subparts:
            queue.extend(subparts)

    return plain_text or html_text


def clean_body(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\u200b\u200c\u200d\u200e\u200f\u2060\ufeff]", "", text)
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_auth_status(headers: list[dict]) -> tuple[str, str, str]:
    auth_values = []
    received_spf_values = []

    for header in headers:
        name = (header.get("name") or "").lower()
        value = header.get("value") or ""

        if name in ("authentication-results", "arc-authentication-results"):
            auth_values.append(value)
        elif name == "received-spf":
            received_spf_values.append(value)

    auth_blob = "\n".join(auth_values).lower()

    def extract(pattern: str, text: str) -> str:
        match = re.search(pattern, text)
        return match.group(1) if match else ""

    spf = extract(r"\bspf=(pass|fail|softfail|neutral|none|temperror|permerror)\b", auth_blob)
    dkim = extract(r"\bdkim=(pass|fail|neutral|none|temperror|permerror)\b", auth_blob)
    dmarc = extract(r"\bdmarc=(pass|fail|bestguesspass|none|temperror|permerror)\b", auth_blob)

    if not spf and received_spf_values:
        received_spf_blob = "\n".join(received_spf_values).lower()
        spf = extract(r"^\s*(pass|fail|softfail|neutral|none|temperror|permerror)\b", received_spf_blob)

    return spf, dkim, dmarc