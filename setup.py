"""Setup script for ChessMaster."""
from setuptools import setup, find_packages

setup(
    name="chessmaster",
    version="1.0.0",
    description="Professional desktop chess application (pygame + python-chess + Stockfish).",
    author="ChessMaster Team",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "pygame>=2.5.0",
        "python-chess>=1.999",
        "bcrypt>=4.0.0",
        "Pillow>=10.0.0",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "pdf": ["reportlab>=4.0.0"],
    },
    entry_points={
        "console_scripts": [
            "chessmaster = main:main",
        ],
    },
    python_requires=">=3.10",
)
