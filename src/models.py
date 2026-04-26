"""Data models for the application."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ProcessingStats:
    """Statistics for a single PDF processing run."""
    pdf_name: str
    page_count: int
    output_tokens: Optional[int] = None
    elapsed_seconds: Optional[float] = None
    success: bool = False
    error_message: Optional[str] = None


@dataclass
class BatchSummary:
    """Summary of processing multiple PDFs."""
    total: int
    successful: int = 0
    failed: int = 0
    failed_files: list[str] = field(default_factory=list)
    total_tokens: int = 0
    total_cost_usd: float = 0.0