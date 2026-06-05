from setuptools import setup, find_packages

setup(
    name="triagecore",
    version="0.1.0",
    description="A lightweight, local-compute-first orchestration harness for token-efficient agent workflows.",
    author="Corey",
    packages=find_packages(),
    install_requires=[
        "requests>=2.28.0",
        "python-dotenv>=1.0.0",
        "psutil>=5.9.0",
        "tomli; python_version < '3.11'",
        "pyyaml>=6.0"
    ],
    entry_points={
        "console_scripts": [
            "triagecore=triage_core.cli:main",
        ]
    },
    extras_require={
        "ui": ["customtkinter>=5.2.0", "Pillow>=10.0.0", "pyshortcuts>=1.9.0"],
        "dev": ["pytest", "ruff", "mypy"]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)
