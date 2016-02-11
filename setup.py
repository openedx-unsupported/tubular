from setuptools import setup


setup(
    name='tubular',
    version='0.0.1',
    description='Continuous Delivery scripts for pipeline evaluation',
    packages=['tubular', 'tubular.gocd', 'tubular.scripts', 'tubular.scripts.github', 'tubular.scripts.hipchat'],
    install_requires=[
        'click>=6.2',
        'requests>=2.9',
    ],
)
