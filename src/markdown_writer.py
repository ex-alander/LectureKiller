"""Markdown file writer with error handling."""

from pathlib import Path
from typing import Optional

from src.exceptions import APIRequestError


class MarkdownWriter:
    """Write markdown content to disk."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save(self, content: str, pdf_name: str) -> Path:
        """
        Save markdown content to file.

        Args:
            content: Markdown string.
            pdf_name: Original PDF name (without extension).

        Returns:
            Path to created file.

        Raises:
            OSError: If file cannot be written.
        """
        output_path = self.output_dir / f"{pdf_name}.md"
        output_path.write_text(content, encoding="utf-8")
        return output_path

    def exists(self, pdf_name: str) -> bool:
        """Check if output file already exists."""
        return (self.output_dir / f"{pdf_name}.md").exists()