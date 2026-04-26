"""PDF to image conversion using pdf2image (requires poppler)."""

from pathlib import Path
from typing import List, Optional

from pdf2image import convert_from_path
from PIL import Image

from src.config import get_settings
from src.exceptions import PDFConversionEmptyError


class PDFPageExtractor:
    """Extract pages from PDF as images."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def extract(self, pdf_path: Path) -> List[Path]:
        """
        Convert PDF to list of image file paths.

        Args:
            pdf_path: Path to PDF file.

        Returns:
            List of paths to generated JPEG images.

        Raises:
            PDFConversionEmptyError: If no images were generated.
        """
        # Convert PDF to PIL images
        pil_images = convert_from_path(
            str(pdf_path),
            dpi=self.settings.pdf_dpi,
            fmt="jpeg",
        )

        if not pil_images:
            raise PDFConversionEmptyError(f"No images extracted from {pdf_path}")

        image_paths = []
        for idx, pil_image in enumerate(pil_images, start=1):
            processed_image = self._prepare_image(pil_image)
            output_path = (
                self.settings.temp_images_dir / f"{pdf_path.stem}_page_{idx}.jpg"
            )
            processed_image.save(
                output_path,
                "JPEG",
                quality=self.settings.image_quality,
                optimize=True,
            )
            image_paths.append(output_path)

        return image_paths

    def _prepare_image(self, image: Image.Image) -> Image.Image:
        """Resize and convert image to RGB."""
        # Resize if necessary
        if max(image.size) > self.settings.max_image_size:
            ratio = self.settings.max_image_size / max(image.size)
            new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        # Ensure RGB mode
        if image.mode != "RGB":
            image = image.convert("RGB")

        return image