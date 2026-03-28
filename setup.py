"""
Gripper
-------

Render local readme files with mermaid diagram support.

::

    $ pip install gripper
    $ cd myproject
    $ gripper

"""

import os
from setuptools import setup, find_packages


def read(filename):
    with open(os.path.join(os.path.dirname(__file__), filename)) as f:
        return f.read()


def read_requirements(filename):
    lines = read(filename).splitlines()
    return [l.strip() for l in lines if l.strip()]


setup(
    name='gripper',
    version='5.0.0',
    description='Render local readme files with mermaid diagram support.',
    long_description=__doc__,
    license='MIT',
    platforms='any',
    packages=find_packages(),
    package_data={'grip': ['static/*.*', 'static/octicons/*']},
    install_requires=[],
    extras_require={'tests': read_requirements('requirements-test.txt')},
    zip_safe=False,
    entry_points={'console_scripts': ['grip = grip:main', 'gripper = grip:main']},
)
