#!/usr/bin/env python3
"""
PDF to Markdown Converter using GPT-4o (Vision) via ProxyAPI
Processes all PDFs from ./input_pdfs and converts each to a detailed Markdown document.
"""

import os
import time
import base64
import logging
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from openai import OpenAI

# PDF to images conversion
try:
    from pdf2image import convert_from_path
    import io
    from PIL import Image
except ImportError:
    print("❌ Missing required libraries. Run: pip install pdf2image pillow openai")
    print("⚠️ Also need poppler: brew install poppler (Mac) or apt-get install poppler-utils (Linux)")
    exit(1)

# ========== CONFIGURATION ==========
# ProxyAPI settings
API_BASE_URL = "https://api.proxyapi.ru/openai/v1"  # ProxyAPI endpoint
API_KEY = ""  # Replace with actual API key
MODEL_NAME = "gpt-5.4"  # Use gpt-4o if you're fine with ~20% accuracy decrease

# Directories
INPUT_DIR = Path("./input_pdfs")
OUTPUT_DIR = Path("./output_markdown")
IMAGES_DIR = Path("./temp_images")  # Temporary directory for images

# API parameters
TEMPERATURE = 0.2
MAX_TOKENS = 32000
MAX_RETRIES = 2
RETRY_DELAY = 5  # seconds
REQUEST_DELAY = 2  # seconds between different PDF requests

# Image parameters
IMAGE_QUALITY = 85  # JPEG quality (1-100)
MAX_IMAGE_SIZE = 1024  # Resize long edge to this many pixels
DPI = 200  # DPI for PDF conversion (higher = better quality but larger)

# Token cost estimation (example pricing - adjust as needed)
COST_PER_TOKEN = 0.0001  # $0.000001 per token (example)

# Create directories if they don't exist
INPUT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

# ========== PROMPT TEMPLATES ==========
SYSTEM_PROMPT = """Ты — эксперт по восстановлению и структурированию лекционного материала.
Твоя задача: получить изображения страниц лекции (русский язык, текст, формулы, графики, схемы) и превратить их в связный, подробный, хорошо структурированный Markdown-документ.

ПРАВИЛА:
1. Ты НЕ просто распознаешь текст. Ты восстанавливаешь целостную лекцию.
2. Если на фото есть пробелы (размыто, обрезано, не видно) — экстраполируй недостающее на основе контекста и логики лекции. НЕ добавляй новые темы, примеры или параграфы, которых не было в оригинале. Можно переформулировать оборванные предложения, добавить связующие слова, уточнить нечеткий термин по контексту.
3. Все формулы переводи в LaTeX: инлайн — $...$, блочные — $$...$$.
4. Все графики, диаграммы, схемы, рисунки — преобразуй в текстовое описание. Описание должно быть максимально подробным: тип графика, оси, единицы, легенда, ключевые точки, тренды, аномалии, выводы. Опиши так, чтобы другой ИИ, который не видит картинку, понял ее полностью мог ответить на вопросы.
5. Описание каждого визуального элемента выделяй строками --- сверху и снизу.
6. Сохраняй структуру: заголовки (##, ###), списки, порядок изложения.
7. Ты должен дать на выходе ТОЛЬКО Markdown. Никаких комментариев перед или после, только чистый Markdown."""

def build_user_prompt(num_pages: int) -> str:
    """Build user prompt with page count information."""
    return f"""Вот {num_pages} изображение(й) страниц лекции (PDF преобразован в изображения). 
Пожалуйста, преобразуй их в Markdown строго по описанным выше правилам. 
Удели особое внимание описанию всех графиков и схем. 
Восстанови связность текста, сохрани все формулы в LaTeX. 
Сделай так, чтобы этот Markdown мог прочитать другой ИИ и ответить на любые вопросы по содержанию лекции.
В выводе — только Markdown, без посторонних комментариев."""

# ========== PDF PROCESSING FUNCTIONS ==========

def pdf_to_images(pdf_path: Path) -> List[Path]:
    """
    Convert PDF pages to JPEG images.

    Args:
        pdf_path: Path to PDF file

    Returns:
        List of paths to generated image files
    """
    logger.info(f"   🔄 Converting PDF to images...")

    try:
        # Convert PDF to PIL images
        images = convert_from_path(
            str(pdf_path),
            dpi=DPI,
            fmt='jpeg'
        )

        image_paths = []
        for i, image in enumerate(images):
            # Resize if too large
            if max(image.size) > MAX_IMAGE_SIZE:
                ratio = MAX_IMAGE_SIZE / max(image.size)
                new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)

            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Save image
            image_path = IMAGES_DIR / f"{pdf_path.stem}_page_{i+1}.jpg"
            image.save(image_path, 'JPEG', quality=IMAGE_QUALITY, optimize=True)
            image_paths.append(image_path)

        logger.info(f"   ✅ Converted {len(image_paths)} pages")
        return image_paths

    except Exception as e:
        logger.error(f"   ❌ Failed to convert PDF: {e}")
        return []

def encode_image_to_base64(image_path: Path) -> str:
    """
    Encode image to base64 string.

    Args:
        image_path: Path to image file

    Returns:
        Base64 encoded string
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def clean_temp_images(image_paths: List[Path]):
    """
    Delete temporary image files.

    Args:
        image_paths: List of image paths to delete
    """
    for path in image_paths:
        try:
            path.unlink()
        except Exception:
            pass

def process_pdf_with_vision(client: OpenAI, pdf_path: Path) -> Optional[str]:
    """
    Send PDF pages as images to GPT-4 Vision API and get Markdown response.

    Args:
        client: OpenAI client instance
        pdf_path: Path to PDF file

    Returns:
        Markdown string or None if failed
    """
    # Convert PDF to images
    image_paths = pdf_to_images(pdf_path)

    if not image_paths:
        logger.error(f"   ❌ No images generated from PDF")
        return None

    try:
        # Build content array with text prompt and images
        content = [
            {
                "type": "text",
                "text": build_user_prompt(len(image_paths))
            }
        ]

        # Add each image
        for img_path in image_paths:
            base64_image = encode_image_to_base64(img_path)
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}",
                    "detail": "high"  # Use high detail for better text recognition
                }
            })

        # Prepare messages
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content}
        ]

        # Retry logic
        for attempt in range(MAX_RETRIES):
            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    temperature=TEMPERATURE,
                    max_completion_tokens=MAX_TOKENS
                )

                markdown_content = response.choices[0].message.content

                if not markdown_content:
                    logger.error(f"   ❌ Empty response from API")
                    return None

                return markdown_content

            except Exception as e:
                logger.error(f"   ❌ API Error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    return None

        return None

    finally:
        # Clean up temporary images
        clean_temp_images(image_paths)

def estimate_tokens(text: str) -> int:
    """
    Rough estimation of tokens count (4 chars ~ 1 token for Russian/English mix).

    Args:
        text: Text to estimate tokens for

    Returns:
        Estimated token count
    """
    return len(text) // 4

def estimate_cost(tokens: int) -> float:
    """
    Estimate cost based on token count (example).

    Args:
        tokens: Number of tokens

    Returns:
        Estimated cost in USD
    """
    return tokens * COST_PER_TOKEN

def save_markdown(content: str, output_path: Path) -> bool:
    """
    Save markdown content to file.

    Args:
        content: Markdown content
        output_path: Output file path

    Returns:
        True if successful, False otherwise
    """
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error(f"   ❌ Failed to save file: {e}")
        return False

def get_pdf_page_count(pdf_path: Path) -> int:
    """
    Get number of pages in PDF.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Number of pages
    """
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(str(pdf_path))
        return len(reader.pages)
    except:
        # Fallback to estimation
        file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
        return max(1, int(file_size_mb / 0.5))

def get_input_pdfs() -> List[Path]:
    """
    Get all PDF files from input directory.

    Returns:
        List of Path objects for PDF files
    """
    return list(INPUT_DIR.glob("*.pdf"))

def check_existing_output(pdf_name: str) -> bool:
    """
    Check if output markdown file already exists.

    Args:
        pdf_name: Name of PDF file (without extension)

    Returns:
        True if output exists, False otherwise
    """
    output_file = OUTPUT_DIR / f"{pdf_name}.md"
    return output_file.exists()

def process_all_pdfs():
    """
    Main function to process all PDFs in input directory.
    """
    # Initialize OpenAI client
    client = OpenAI(
        base_url=API_BASE_URL,
        api_key=API_KEY,
        timeout=120.0  # 120 second timeout for large PDFs
    )

    # Get all PDF files
    pdf_files = get_input_pdfs()

    if not pdf_files:
        logger.warning("No PDF files found in ./input_pdfs directory")
        return

    logger.info(f"Found {len(pdf_files)} PDF file(s) to process\n")

    successful = 0
    failed = 0
    failed_files = []

    # Process each PDF
    for pdf_path in pdf_files:
        pdf_name = pdf_path.stem  # Name without extension

        # Check if already processed
        if check_existing_output(pdf_name):
            logger.info(f"⏭️  {pdf_path.name} → skipping (already processed)")
            continue

        # Get page count
        page_count = get_pdf_page_count(pdf_path)
        file_size_mb = pdf_path.stat().st_size / (1024 * 1024)

        logger.info(f"📄 {pdf_path.name} → sending... ({page_count} pages, ~{file_size_mb:.1f}MB)")

        # Process the PDF
        start_time = time.time()
        markdown_content = process_pdf_with_vision(client, pdf_path)
        elapsed_time = time.time() - start_time

        if markdown_content:
            # Estimate tokens and cost
            estimated_tokens = estimate_tokens(markdown_content)
            estimated_cost_usd = estimate_cost(estimated_tokens)
            estimated_cost_rub = estimated_cost_usd * 90  # Approximate RUB to USD

            # Save to file
            output_path = OUTPUT_DIR / f"{pdf_name}.md"
            if save_markdown(markdown_content, output_path):
                logger.info(f"   ✅ done: {pdf_name}.md ({estimated_tokens} tokens, ~${estimated_cost_usd:.4f} / ~{estimated_cost_rub:.2f} руб, {elapsed_time:.1f}s)")
                successful += 1
            else:
                logger.error(f"   ❌ failed to save: {pdf_name}.md")
                failed += 1
                failed_files.append(pdf_path.name)
        else:
            logger.error(f"   ❌ failed to process: {pdf_path.name}")
            failed += 1
            failed_files.append(pdf_path.name)

        # Delay between requests to avoid rate limiting
        time.sleep(REQUEST_DELAY)

    # Final summary
    logger.info(f"\n{'='*50}")
    logger.info(f"✅ Processed: {successful} successful, {failed} errors")
    if failed_files:
        logger.info(f"Failed files: {', '.join(failed_files)}")
    logger.info(f"{'='*50}")

# ========== MAIN EXECUTION ==========

if __name__ == "__main__":
    # Validate configuration
    if API_KEY == "your-api-key-here":
        logger.error("❌ Please configure API_KEY before running the script")
        logger.error("Edit the configuration section at the top of the file")
        exit(1)

    # Check for required libraries
    try:
        import pdf2image
        import PIL
    except ImportError as e:
        logger.error(f"❌ Missing required library: {e}")
        logger.error("Run: pip install pdf2image pillow openai PyPDF2")
        exit(1)

    # Process all PDFs
    process_all_pdfs()