#!/usr/bin/env python  #pylint: disable=missing-docstring

import os
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

import aduro

open_ = lambda fname: open(os.path.join(os.path.dirname(__file__), fname))

with open_('requirements.txt') as f:
    requires = f.read().splitlines()

setup(name='Aduro',
      version=aduro.__version__,
      description='Progress tracker for Amazon Kindle',
      author='Matthew Suozzo',
      author_email='matthew.suozzo@gmail.com',
      url='https://github.com/msuozzo/Aduro',
      packages=['aduro'],
      install_requires=requires,
      license='MIT'
     )
