"""Package configuration for PDF to Markdown converter."""

from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="LectureKiller",
    version="1.0.0",
    author="Alexander",
    author_email="dyrtand@gmail.com",
    description="Convert scanned lecture PDFs to structured Markdown using LLM vision",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ex-alander/LectureKiller",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
    install_requires=[
        "openai>=1.58.0",
        "pdf2image>=1.16.0",
        "pillow>=10.0.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "loguru>=0.7.0",
        "typer>=0.9.0",
    ],
    entry_points={
        "console_scripts": [
            "pdf2md=src.cli:main",
        ],
    },
)