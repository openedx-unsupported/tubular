from setuptools import setup
import os

PATH = os.path.dirname(os.path.abspath(__file__)) + "/tubular/scripts/"

setup(
    name='tubular',
    version='0.0.1',
    description='Continuous Delivery scripts for pipeline evaluation',
    packages=['tubular', 'tubular.gocd', 'tubular.scripts', 'tubular.scripts.github', 'tubular.scripts.hipchat'],
    install_requires=[
        'boto==2.39.0',
        'click>=6.2',
        'requests>=2.9',
    ],
    scripts=[os.path.join(dp, f) for dp, dn, filenames in os.walk(PATH) for f in filenames if os.path.splitext(f)[1] == '.py' and not f == '__init__.py']
)
