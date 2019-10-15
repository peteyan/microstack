from setuptools import setup, find_packages

setup(
    name="microstack_init",
    description="Optionally interactive init script for Microstack.",
    packages=find_packages(exclude=("tests",)),
    version="0.0.1",
    entry_points={
        'console_scripts': [
            'microstack_init = init.main:main',
            'set_network_info = init.set_network_info:main',
        ],
    },
)
