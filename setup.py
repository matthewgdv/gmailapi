from setuptools import setup, find_packages
from os import path

__version__ = "0.3.1"

here = path.abspath(path.dirname(__file__))

with open(path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

with open(path.join(here, "requirements.txt"), encoding="utf-8") as f:
    dependencies = [line for line in f if line]

setup(
    name="gmailapi",
    version=__version__,
    description="A library providing Python bindings for the Gmail api.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/matthewgdv/gmailapi",
    license="MIT",
    classifiers=[
      "Development Status :: 3 - Alpha",
      "Intended Audience :: Developers",
      "Programming Language :: Python :: 3.8",
    ],
    packages=find_packages(exclude=["tests*"]),
    install_requires=dependencies,
    setup_requires=['setuptools_scm'],
    include_package_data=True,
    author="Matt GdV",
    author_email="matthewgdv@gmail.com"
)
