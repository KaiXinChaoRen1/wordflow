from setuptools import find_packages, setup


setup(
    name="wordflow",
    version="0.1.0",
    description="A terminal spelling trainer for English articles.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    python_requires=">=3.9",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=["textual>=0.58.0,<1.0.0"],
    entry_points={"console_scripts": ["wordflow=wordflow.__main__:main"]},
)
