import pdfplumber

# Each entry: (doc_type, required_phrases_in_first_pages)
# Ordered most-specific first to avoid false positives.
_SIGNATURES = [
    ("fidelity_release", ["Fidelity Investments", "Release Confirmation"]),
    ("fidelity_tax",     ["Fidelity Investments", "1042-S"]),
    ("fidelity_tax",     ["Fidelity Investments", "1099-DIV"]),
    ("fidelity_statement", ["Fidelity Investments", "Account Activity"]),
    ("schwab_release",   ["Charles Schwab", "Release Confirmation"]),
    ("schwab_tax",       ["Charles Schwab", "1099-DIV"]),
    ("schwab_tax",       ["Charles Schwab", "1042-S"]),
    ("schwab_statement", ["Charles Schwab", "Account Activity"]),
    ("form16",           ["FORM NO. 16"]),
    ("form16",           ["Form No. 16"]),
    ("form16",           ["Form 16", "Assessment Year"]),   # cover-page variant
    ("ais",              ["Annual Information Statement"]),
]


def detect_document_type(pdf_path: str, password: str = "") -> str:
    with pdfplumber.open(pdf_path, password=password or None) as pdf:
        # Scan first 2 pages — many Form 16 PDFs have a cover page before the actual form
        pages_text = "\n".join(
            page.extract_text() or ""
            for page in pdf.pages[:2]
        )
    for doc_type, phrases in _SIGNATURES:
        if all(phrase in pages_text for phrase in phrases):
            return doc_type
    return "unknown"
