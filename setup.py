#!/usr/bin/env python

import glob
from setuptools import setup, find_packages, Extension
import setuptools

from codecs import open
from os import path
import sys

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

    keywords='ai',

    packages=find_packages(),

    package_data={
    },
    data_files=[
        #('etc', glob.glob('etc/*')),
        #('', ['lib/pyds.so']),
        ],

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files # noqa
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    # data_files=[('my_data', ['data/data_file'])],

    entry_points={
        'console_scripts': [
            #'kscore = kscore.server.main:main',
            #'task_worker = kscore.server.task_worker:main',
        ],
    },

    zip_safe=False,
)

