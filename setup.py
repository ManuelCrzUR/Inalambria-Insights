"""
setup.py - Configuración del paquete para PyPI/setuptools
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="sms-template-pipeline",
    version="0.1.0",
    description="SMS Template Extraction and Classification Pipeline",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Manuel Cruz",
    author_email="manuel@inalambria.com",
    url="https://github.com/inalambria/sms-template-pipeline",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "pandas>=1.3.0",
        "pyarrow>=4.0.0",  # para parquet
        "numpy>=1.21.0",
        "rich>=10.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.12.0",
            "pytest-asyncio>=0.21.0",
            "black>=21.0",
            "flake8>=3.9.0",
            "mypy>=0.910",
        ],
        "prod": [
            "fastapi>=0.70.0",
            "uvicorn>=0.15.0",
            "celery>=5.1.0",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
