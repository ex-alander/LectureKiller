"""Command-line interface and main orchestration."""

import shutil
import time
from pathlib import Path
from typing import List, Optional

from loguru import logger

from src.api_client import VisionAPIClient
from src.config import get_settings
from src.exceptions import APIRequestError, PDFConversionEmptyError
from src.markdown_writer import MarkdownWriter
from src.models import BatchSummary, ProcessingStats
from src.pdf_converter import PDFPageExtractor


class PDFProcessor:
    """Orchestrate PDF processing workflow."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.extractor = PDFPageExtractor()
        self.api_client = VisionAPIClient()
        self.writer = MarkdownWriter(self.settings.output_dir)

    def run(self) -> BatchSummary:
        """Process all PDFs in input directory."""
        pdf_files = self._collect_pdfs()
        if not pdf_files:
            logger.warning("No PDF files found in {}", self.settings.input_dir)
            return BatchSummary(total=0, successful=0, failed=0, failed_files=[])

        logger.info("Found {} PDF file(s) to process\n", len(pdf_files))

        summary = BatchSummary(total=len(pdf_files), successful=0, failed=0, failed_files=[])

        for pdf_path in pdf_files:
            stats = self._process_single_pdf(pdf_path)
            if stats.success:
                summary.successful += 1
                if stats.output_tokens:
                    summary.total_tokens += stats.output_tokens
            else:
                summary.failed += 1
                summary.failed_files.append(pdf_path.name)

            time.sleep(self.settings.request_delay_seconds)

        self._print_summary(summary)
        return summary

    def _collect_pdfs(self) -> List[Path]:
        """Return list of PDF files not yet processed."""
        all_pdfs = list(self.settings.input_dir.glob("*.pdf"))
        return [pdf for pdf in all_pdfs if not self.writer.exists(pdf.stem)]

    def _process_single_pdf(self, pdf_path: Path) -> ProcessingStats:
        """Process a single PDF and return statistics."""
        logger.info("📄 {} → processing...", pdf_path.name)

        # Estimate page count for logging
        page_count = self._estimate_page_count(pdf_path)
        file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
        logger.info("   {} pages, {:.1f} MB", page_count, file_size_mb)

        start_time = time.time()

        try:
            # Step 1: Convert PDF to images
            image_paths = self.extractor.extract(pdf_path)
            logger.info("   ✅ Converted {} pages", len(image_paths))

            # Step 2: Send to API
            markdown = self.api_client.process_pdf_pages(image_paths, pdf_path.stem)

            # Step 3: Save result
            output_path = self.writer.save(markdown, pdf_path.stem)

            elapsed = time.time() - start_time
            token_estimate = self._estimate_tokens(markdown)

            logger.info(
                "   ✅ Saved to {} ({} tokens, {:.1f}s)",
                output_path.name,
                token_estimate,
                elapsed,
            )

            return ProcessingStats(
                pdf_name=pdf_path.name,
                page_count=page_count,
                output_tokens=token_estimate,
                elapsed_seconds=elapsed,
                success=True,
            )

        except (PDFConversionEmptyError, APIRequestError) as e:
            logger.error("   ❌ Failed: {}", str(e))
            return ProcessingStats(
                pdf_name=pdf_path.name,
                page_count=page_count,
                success=False,
                error_message=str(e),
            )

        finally:
            # Cleanup temporary images
            self._cleanup_temp_images(pdf_path.stem)

    @staticmethod
    def _estimate_page_count(pdf_path: Path) -> int:
        """Estimate page count from file size (fallback)."""
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(str(pdf_path))
            return len(reader.pages)
        except ImportError:
            file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
            return max(1, int(file_size_mb / 0.5))

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimation (4 chars ~ 1 token)."""
        return len(text) // 4

    def _cleanup_temp_images(self, pdf_stem: str) -> None:
        """Remove temporary images for a specific PDF."""
        pattern = f"{pdf_stem}_page_*.jpg"
        for img_path in self.settings.temp_images_dir.glob(pattern):
            try:
                img_path.unlink()
            except OSError:
                pass

    @staticmethod
    def _print_summary(summary: BatchSummary) -> None:
        """Print batch processing summary."""
        logger.info("\n" + "=" * 50)
        logger.info("✅ Processed: {} successful, {} errors", summary.successful, summary.failed)
        if summary.failed_files:
            logger.info("Failed files: {}", ", ".join(summary.failed_files))
        logger.info("=" * 50)


def main() -> None:
    """Entry point for the CLI."""
    settings = get_settings()

    # Validate directories
    settings.input_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    settings.temp_images_dir.mkdir(parents=True, exist_ok=True)

    # Validate API key
    if not settings.api_key or settings.api_key == "your_key_here":
        logger.error("❌ Please configure API_KEY in .env file")
        logger.error("   Copy .env.example to .env and add your API key")
        return

    # Run processor
    processor = PDFProcessor()
    processor.run()


if __name__ == "__main__":
    main()