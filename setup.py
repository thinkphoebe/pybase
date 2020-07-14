#!/usr/bin/env python

from codecs import open
from os import path

from setuptools import find_packages, setup

__version__ = '1.0.0'

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='pybase',
    version='1.0.0',
    description='pybase',
    long_description=long_description,
    url='https://gitlab.com/thinkphoebe/lib-pybase',
    author='thinkphoebe',
    author_email='thinkphoebe@gmail.com',
    license='MIT',

    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 5 - Production/Stable',

        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],

    keywords='base',

    packages=find_packages(),

    package_data={
    },
    data_files=[
    ],

    entry_points={
        'console_scripts': [
        ],
    },

    zip_safe=False,
)
