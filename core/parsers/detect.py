import pdfplumber

# Each entry: (doc_type, required_phrases_in_first_page)
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
    ("ais",              ["Annual Information Statement"]),
]


def detect_document_type(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        first_page_text = pdf.pages[0].extract_text() or ""
    for doc_type, phrases in _SIGNATURES:
        if all(phrase in first_page_text for phrase in phrases):
            return doc_type
    return "unknown"
