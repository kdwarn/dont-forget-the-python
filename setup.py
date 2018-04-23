from setuptools import setup

setup(
    name='Remember the Python',
    version='0.1',
    py_modules=['app'],
    install_requires=[
        'Click',
    ],
    entry_points='''
        [console_scripts]
        rtp=app:main
    ''',
)
