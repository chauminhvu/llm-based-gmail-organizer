import re


def remove_signature(text: str) -> tuple[str, str]:
    """
    Splits email content into body text and signature, supporting multiple European languages.
    Detects common signature delimiters, closing salutations, and Markdown-specific patterns.

    Intentional Behaviors:
    - Preserves reply headers (e.g., "On ... wrote:") within the body text when no explicit signature is found.
    - Truncates all content following a detected signature, effectively removing both the signature and any subsequent quoted reply history.

    Args:
        text (str): The raw email content.

    Returns:
        tuple[str, str]: A tuple of (body_text, signature).
    """

    if not text:
        return "", ""

    # Patterns for signature detection
    patterns = {
        'delimiters': [
            r'\n\s*--\s*\n',
            r'\n\s*={3,}\s*\n',
            r'\n\s*_{3,}\s*\n',
            r'\n\s*-{3,}\s*\n',
            r'\n\s*\*{3,}\s*\n',
            r'\n\s*-{3,}\s*$',  # delimiter at end
        ],
        'closings': [
            # English - allow leading whitespace
            r'\n\s*(?:Best regards?|Regards?|Kind regards?|Warm regards?|Brgds?|Cheers|Thanks?|Thank you|Many thanks|Sincerely|Cordially|Warmly|Best|Sent from my .*?)\s*,?\s*(?=\n|$)',
            # French
            r'\n\s*(?:Cordialement|Bien cordialement|Salutations|Meilleures salutations|Amicalement|Merci|Bien à vous|Respectueusement)\s*,?\s*(?=\n|$)',
            # German
            r'\n\s*(?:Mit freundlichen Grüßen|Freundliche Grüße|Viele Grüße|Herzliche Grüße|Beste Grüße)\s*,?\s*(?=\n|$)',
            # Italian
            r'\n\s*(?:Cordiali saluti|Distinti saluti|Saluti|Grazie|Un saluto|Cari saluti)\s*,?\s*(?=\n|$)',
            # Dutch
            r'\n\s*(?:Met vriendelijke groet|Vriendelijke groeten|Hartelijke groeten|Groeten)\s*,?\s*(?=\n|$)',
            # Luxembourgish
            r'\n\s*(?:Mat frëndleche Gréiss|Frëndlech Gréiss|Villmools Merci|Merci)\s*,?\s*(?=\n|$)',
        ],
        'markdown': [
            r'\n\n\s*!\[.*?\]\(.*?\)',  # Markdown image after blank line
        ]
    }

    # Find all possible signature start positions
    candidates = []

    for pattern_str in patterns['delimiters']:
        pattern = re.compile(pattern_str, re.MULTILINE)
        for match in pattern.finditer(text):
            candidates.append(match.start())

    # Check closing phrases - use LAST match to avoid false positives
    for pattern_str in patterns['closings']:
        pattern = re.compile(pattern_str, re.IGNORECASE | re.MULTILINE)
        matches = list(pattern.finditer(text))
        if matches:
            candidates.append(matches[-1].start())

    # Check markdown patterns
    for pattern_str in patterns['markdown']:
        pattern = re.compile(pattern_str, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        for match in pattern.finditer(text):
            candidates.append(match.start())

    # Use the earliest position found
    if candidates:
        earliest_pos = min(candidates)
        body_text = text[:earliest_pos]
        signature = text[earliest_pos:].strip()
        return body_text, signature

    return text, ""
