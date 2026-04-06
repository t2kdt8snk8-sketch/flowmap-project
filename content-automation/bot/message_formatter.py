from __future__ import annotations

import re


def format_for_telegram(text: str) -> str:
    """Convert generic markdown to Telegram Markdown v1 subset.

    Telegram v1 supports: *bold*, _italic_, `inline code`, ```code block```, [text](url)
    It does NOT support: ## headers, **, __, ~~strike~~, > blockquote
    """
    # Strip ATX headers (## Heading) → plain text with a newline
    text = re.sub(r"^#{1,6}\s+(.+)$", r"\1", text, flags=re.MULTILINE)
    # **bold** → *bold*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text, flags=re.DOTALL)
    # __italic__ → _italic_  (only double underscores, single underscore stays)
    text = re.sub(r"__(.+?)__", r"_\1_", text, flags=re.DOTALL)
    # ~~strikethrough~~ → plain text
    text = re.sub(r"~~(.+?)~~", r"\1", text, flags=re.DOTALL)
    # > blockquote → plain text
    text = re.sub(r"^> ?(.+)$", r"\1", text, flags=re.MULTILINE)
    # Horizontal rules
    text = re.sub(r"^[-*_]{3,}$", "─────────────", text, flags=re.MULTILINE)
    return text.strip()


def split_long_message(text: str, max_length: int = 4000) -> list[str]:
    """Split text into chunks that fit Telegram's 4096-character limit.

    Splits at newline boundaries to avoid breaking sentences mid-line.
    """
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    current_lines: list[str] = []
    current_len = 0

    for line in text.splitlines(keepends=True):
        if current_len + len(line) > max_length:
            if current_lines:
                chunks.append("".join(current_lines))
            current_lines = [line]
            current_len = len(line)
        else:
            current_lines.append(line)
            current_len += len(line)

    if current_lines:
        chunks.append("".join(current_lines))

    return chunks
