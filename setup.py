from setuptools import setup, find_packages

setup(
    name='gaia-sky-data-mg',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'requests>=2.22.0',
    ],
    entry_points={
        'console_scripts': [
            'gaia-sky-data-mg=gaia_sky_data_mg.cli:main',
        ],
    },
    python_requires='>=3.8',
)
