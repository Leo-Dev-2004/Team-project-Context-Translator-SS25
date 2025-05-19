from setuptools import setup, find_packages

setup(
    name="teamprojekt",
    version="0.1",
    packages=find_packages(include=['Backend', 'Backend.*']),
    install_requires=[
        "fastapi==0.95.2",
        "uvicorn[standard]==0.22.0",
        "python-multipart==0.0.6",
        "python-dotenv==0.21.1",
        "httpx==0.24.1",
        "pytest-asyncio==0.21.1",
        "websockets==11.0.3"
    ],
    python_requires=">=3.8",
)
