from __future__ import print_function
from distutils.command import build_ext as _build_ext
import os
import sys
from os.path import join, dirname
from setuptools import Extension, setup

try:
    from Cython.Distutils import build_ext
except ImportError:
    build_ext = None


def readme(fname):
    """Read text out of a file in the same directory as setup.py.
    """
    return open(join(dirname(__file__), fname)).read()


import numpy as np
include_dirs = [np.get_include()]

if build_ext:
    sensor_module = Extension(
        'cutils.sensors.converter',
        ['cutils/sensors/converter.pyx',
         'cutils/sensors/cmodules/sensor_parse.c',
         ],
        include_dirs=include_dirs,
    )

else:
    sensor_module = Extension(
        'cutils.sensors.converter',
        ['cutils/sensors/converter.pyx',
         'cutils/sensors/cmodules/sensor_parse.c',
         ],
        include_dirs=include_dirs,
    )

    # noinspection PyPep8Naming
    class build_ext(_build_ext.build_ext):
        def initialize_options(self):
            # noinspection PyAttributeOutsideInit
            self.cwd = None
            return _build_ext.build_ext.initialize_options(self)

        def finalize_options(self):
            # noinspection PyAttributeOutsideInit
            self.cwd = os.getcwd()
            return _build_ext.build_ext.finalize_options(self)

        def run(self):
            assert os.getcwd() == self.cwd, \
                'Must be in package root: %s' % self.cwd
            print("""
            --> Cython is not installed. Can not compile .pyx files. <--
            Unfortunately, setuptools does not allow us to install
            Cython prior to this point, so you'll have to do it yourself
            and run this command again, if you want to recompile your
            .pyx files.

            `pip install {cython}` should suffice.

            ------------------------------------------------------------
            """.format(
                cython=CYTHON_REQUIREMENT,
            ))
            assert os.path.exists(
                os.path.join(self.cwd, 'cutils', 'sensors', 'converter.c')), \
                'Source file not found!'
            return _build_ext.build_ext.run(self)


CYTHON_REQUIREMENT = 'Cython==0.19.1'

setup(
    name='cutils',
    version='0.0.1',
    description='Wavelet C Algorithms',
    long_description=readme('cutils/README.md'),
    author='Keivan Majidi, Ehsan Azarnasab',
    author_email='keivan@gmail.com, dashesy@gmail.com',
    url='https://github.com/ekipmanager/wavelet-utils/cutils',
    py_modules=['cutils.__init__', 'cutils.sensors.__init__'],
    include_dirs=include_dirs,
    cmdclass={
        'build_ext': build_ext,
    },
    ext_modules=[
        sensor_module,
    ],
)
