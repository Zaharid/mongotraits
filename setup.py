# -*- coding: utf-8 -*-
"""
Created on Mon Dec 30 21:39:41 2013

@author: zah
"""

import sys
import os
try:
    from distutils.core import setup
except ImportError:
    from setuptools import setup

if sys.version_info[0] == 3:
    LONG_DESCRIPTION = open('README.md', encoding='utf-8').read()
else:
    LONG_DESCRIPTION = open('README.md').read()

def find_packages():
    packages = []
    for dir, dubdir, files in os.walk('mongotraits'):
        package = dir.replace(os.path.sep, '.')
        if '__init__.py' not in files:
            # not a package
            continue
        packages.append(package)
    return packages

if __name__ == '__main__':
    setup(
        name='mongotraits',
        version='0.1.0',
        author='Zahari Dimitrov Kassabov',
        author_email='zaharid@gmail.com',
        packages=find_packages(),
        license='MIT License',
        url='http://zigzag.com/labcore',
        classifiers=[
            'Development Status :: 3 - Alpha',
            'Intended Audience :: Science/Research',
            'License :: OSI Approved :: MIT License',
            'Operating System :: OS Independent',
            'Programming Language :: Python :: 2.7',
            'Topic :: Scientific/Engineering'
        ],
        install_requires = ['IPython>=2.1','pymongo>=2.7.1'],
        description='A liteweight ODM for MongoDB',
        long_description=LONG_DESCRIPTION,
    )
