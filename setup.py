#!/usr/bin/env python  #pylint: disable=missing-docstring

import ast
import os
import re
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


def open_(fname, *args, **kwargs):
    return open(os.path.join(os.path.dirname(__file__), fname), *args, **kwargs)

# Extract the version string from aduro/__init__.py
_version_re = re.compile(r'__version__\s+=\s+(.*)')

with open_('aduro/__init__.py', 'rb') as f:
    version = str(ast.literal_eval(_version_re.search(
        f.read().decode('utf-8')).group(1)))

with open_('requirements.txt') as f:
    requires = f.read().splitlines()

setup(name='Aduro',
      version=version,
      description='Progress tracker for Amazon Kindle',
      author='Matthew Suozzo',
      author_email='matthew.suozzo@gmail.com',
      url='https://github.com/msuozzo/Aduro',
      packages=['aduro'],
      install_requires=requires,
      license='MIT'
     )
