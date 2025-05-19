from setuptools import setup, find_packages

setup(
    name="teamprojekt",
    version="0.1",
    packages=find_packages(where='.', include=['Backend*']),
    package_dir={'': '.'},
    install_requires=[
        "fastapi>=0.95.0",
        "uvicorn>=0.21.0",
        "python-multipart>=0.0.5",
        "python-dotenv>=0.19.0",
        "httpx>=0.23.0",
        "pytest-asyncio>=0.21.0"
    ],
)
