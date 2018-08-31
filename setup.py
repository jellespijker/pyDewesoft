from setuptools import setup, find_packages

setup(
    name='pyDewesoft',
    version='1.0rc0',
    url='http://mti-gitlab.ihc.eu/generic-software/pyDewesoft',
    license='MIT License',
    author='Jelle Spijker',
    author_email='j.spijker@ihcmti.com',
    description='A Python module to read Dewesoft datafiles',
    keywords='Measurement, Engineering, DSP, Signal processing',
    packages=find_packages(),
    install_requires=['pint', 'numpy', 'pip-tools', 'dill', 'pyyaml'],
    include_package_data=True
)
