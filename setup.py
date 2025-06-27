from setuptools import setup, find_packages

setup(
    name="services",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "openai",
        "requests",
        "cryptography",
        "psycopg2-binary",
        "pgvector",
        "jupyter",
        "python-dotenv",
        "fastapi>=0.104.1",
        "uvicorn[standard]>=0.24.0",
        "pydantic>=2.5.0",
        "PyYAML",
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
