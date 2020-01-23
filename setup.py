from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='pyDewesoft',
    version='1.1a0',
    url='https://github.com/jellespijker/pyDewesoft',
    license='MIT License',
    author='Jelle Spijker',
    author_email='spijker.jelle@gmail.com',
    description='A Python module to read Dewesoft datafiles',
    long_description=long_description,
    long_description_content_type="text/markdown",
    keywords='Measurement, Engineering, DSP, Signal processing',
    packages=find_packages(),
    install_requires=['pint', 'numpy', 'dill'],
    include_package_data=True
)
