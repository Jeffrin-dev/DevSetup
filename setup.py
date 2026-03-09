from setuptools import setup, find_packages

setup(
    name="devsetup",
    version="0.0.0",
    description="Automated developer environment setup tool.",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "devsetup=devsetup.cli.main:main",
        ],
    },
    python_requires=">=3.9",
)
