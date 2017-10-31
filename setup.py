"""A simple service for capturing autoscaling lifecycle hook actions
and notifying another service that it needs a graceful shutdown.

"""
from setuptools import setup, find_packages
import os 

with open('requirements.txt') as f:
    requirements = f.readlines()

setup(
    name='shudder',
    description="Graceful shutdowns using autoscaling lifecycle hooks.",
    version='1.0.15',
    long_description=__doc__,
    packages=find_packages(),
    data_files=[('/etc/init.d', [os.getcwd().split('/build/', 1)[0] + '/pkg_scripts/shudder'])],
    include_package_data=True,
    author='Anthony Grimes',
    author_email='anthony@scopely.com',
    url='https://github.com/scopely/shudder',
    license='Apache 2.0',
    install_requires=requirements
)
