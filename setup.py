from setuptools import setup, find_packages

with open('README.md', 'r') as fh:
    long_description = fh.read()

setup(
    name='dftp',
    version='0.2.0',
    author='Kris Warner',
    author_email='kdwarn@gmail.com',
    description="Command-line interface for Remember the Milk.",
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/kdwarn/dont-forget-the-python',
    packages=find_packages(),
    classifiers=(
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ),
    install_requires=['click>=6.7',
                      'requests>=2.19.1',
                      'arrow>=0.12.1',
                      'reportlab>=3.5.2',
                      'tabulate>=0.8.2'],
    entry_points = {'console_scripts': ['dftp=dftp.app:main']},
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
)
