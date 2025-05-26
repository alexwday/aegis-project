from setuptools import setup, find_packages

setup(
    name="aegis",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "openai",
        "requests",
        "cryptography",
        "psycopg2-binary",
        "jupyter",
        "pysbd",
        "tiktoken",
        "smbclient",
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-cov",
            "black",
            "mypy",
        ],
    },
)
