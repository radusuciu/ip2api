"""Setup script for ip2api."""
from setuptools import setup
import codecs
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))


def read(*parts):
    """Return multiple read calls to different readable objects as a single
    string."""
    return codecs.open(os.path.join(HERE, *parts), 'r').read()

LONG_DESCRIPTION = read('README.rst')


setup(
    name='ip2api',
    version='1.1.1',
    url='http://github.com/radusuciu/ip2api/',
    license='Apache Software License',
    author='Radu Suciu',
    install_requires=read('requirements.txt').splitlines(),
    author_email='radusuciu@gmail.com',
    description='Simple interface for IP2',
    long_description=LONG_DESCRIPTION,
    packages=['ip2api'],
    include_package_data=True,
    platforms='any',
    zip_safe=True,
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Development Status :: 4 - Beta',
        'Natural Language :: English',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Scientific/Engineering',
        'Topic :: Scientific/Engineering :: Bio-Informatics'
    ],
)
