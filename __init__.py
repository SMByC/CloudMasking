# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CloudMasking
                                 A QGIS plugin
 Cloud masking using different process suck as fmask
                              -------------------
        copyright            : (C) 2016-2022 by Xavier Corredor Llano, SMByC
        email                : xcorredorl@ideam.gov.co
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 3 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""
import os
from shutil import copy, rmtree
from subprocess import call


def fmask_libs():
    plugin_folder = os.path.dirname(__file__)
    fmask_path = os.path.join(plugin_folder, 'libs', 'fmask')
    # first try copying the binary libs
    try:
        from CloudMasking.libs.fmask import _fillminima, _valueindexes
    except:
        import sys, platform
        is_64bits = sys.maxsize > 2 ** 32
        if is_64bits:
            if sys.version_info[0:2] == (3, 9):  # py39
                if platform.system() == "Darwin":
                    from CloudMasking.libs.fmask.ios64_py39 import _fillminima, _valueindexes
                    copy(os.path.join(fmask_path, 'ios64_py39', '_fillminima.so'), fmask_path)
                    copy(os.path.join(fmask_path, 'ios64_py39', '_valueindexes.so'), fmask_path)
                if platform.system() == "Windows":
                    from CloudMasking.libs.fmask.win64_py39 import _fillminima, _valueindexes
                    copy(os.path.join(fmask_path, 'win64_py39', '_fillminima.pyd'), fmask_path)
                    copy(os.path.join(fmask_path, 'win64_py39', '_valueindexes.pyd'), fmask_path)
                if platform.system() == "Linux":
                    from CloudMasking.libs.fmask.lin64_py39 import _fillminima, _valueindexes
                    copy(os.path.join(fmask_path, 'lin64_py39', '_fillminima.so'), fmask_path)
                    copy(os.path.join(fmask_path, 'lin64_py39', '_valueindexes.so'), fmask_path)
            if sys.version_info[0:2] == (3, 8):  # py38
                if platform.system() == "Darwin":
                    from CloudMasking.libs.fmask.ios64_py38 import _fillminima, _valueindexes
                    copy(os.path.join(fmask_path, 'ios64_py38', '_fillminima.so'), fmask_path)
                    copy(os.path.join(fmask_path, 'ios64_py38', '_valueindexes.so'), fmask_path)
                if platform.system() == "Windows":
                    from CloudMasking.libs.fmask.win64_py38 import _fillminima, _valueindexes
                    copy(os.path.join(fmask_path, 'win64_py38', '_fillminima.pyd'), fmask_path)
                    copy(os.path.join(fmask_path, 'win64_py38', '_valueindexes.pyd'), fmask_path)
                if platform.system() == "Linux":
                    from CloudMasking.libs.fmask.lin64_py38 import _fillminima, _valueindexes
                    copy(os.path.join(fmask_path, 'lin64_py38', '_fillminima.so'), fmask_path)
                    copy(os.path.join(fmask_path, 'lin64_py38', '_valueindexes.so'), fmask_path)
            if sys.version_info[0:2] == (3, 7):  # py37
                if platform.system() == "Darwin":
                    from CloudMasking.libs.fmask.ios64_py37 import _fillminima, _valueindexes
                    copy(os.path.join(fmask_path, 'ios64_py37', '_fillminima.so'), fmask_path)
                    copy(os.path.join(fmask_path, 'ios64_py37', '_valueindexes.so'), fmask_path)
                if platform.system() == "Windows":
                    from CloudMasking.libs.fmask.win64_py37 import _fillminima, _valueindexes
                    copy(os.path.join(fmask_path, 'win64_py37', '_fillminima.pyd'), fmask_path)
                    copy(os.path.join(fmask_path, 'win64_py37', '_valueindexes.pyd'), fmask_path)
                if platform.system() == "Linux":
                    from CloudMasking.libs.fmask.lin64_py37 import _fillminima, _valueindexes
                    copy(os.path.join(fmask_path, 'lin64_py37', '_fillminima.so'), fmask_path)
                    copy(os.path.join(fmask_path, 'lin64_py37', '_valueindexes.so'), fmask_path)
            if sys.version_info[0:2] == (3, 6):  # py36
                if platform.system() == "Darwin":
                    from CloudMasking.libs.fmask.ios64_py36 import _fillminima, _valueindexes
                    copy(os.path.join(fmask_path, 'ios64_py36', '_fillminima.so'), fmask_path)
                    copy(os.path.join(fmask_path, 'ios64_py36', '_valueindexes.so'), fmask_path)
                if platform.system() == "Linux":
                    from CloudMasking.libs.fmask.lin64_py36 import _fillminima, _valueindexes
                    copy(os.path.join(fmask_path, 'lin64_py36', '_fillminima.so'), fmask_path)
                    copy(os.path.join(fmask_path, 'lin64_py36', '_valueindexes.so'), fmask_path)
                if platform.system() == "Windows":
                    from CloudMasking.libs.fmask.win64_py36 import _fillminima, _valueindexes
                    copy(os.path.join(fmask_path, 'win64_py36', '_fillminima.pyd'), fmask_path)
                    copy(os.path.join(fmask_path, 'win64_py36', '_valueindexes.pyd'), fmask_path)
        else:
            if platform.system() == "Windows":
                from CloudMasking.libs.fmask.win32_py36 import _fillminima, _valueindexes
                copy(os.path.join(fmask_path, 'win32_py36', '_fillminima.pyd'), fmask_path)
                copy(os.path.join(fmask_path, 'win32_py36', '_valueindexes.pyd'), fmask_path)
    # second try building from source
    try:
        from CloudMasking.libs.fmask import _fillminima, _valueindexes
    except:
        # plugin path
        print("BUILDING libs for CloudMasking plugin...")
        fmask_libs = os.path.join(fmask_path, 'libs')
        call(['python3', 'setup.py', 'build_ext'], cwd=fmask_libs)
        # search and copy
        for root, dirs, files in os.walk(os.path.join(fmask_libs, "build")):
            if len(files) != 0:
                for f in files:
                    if f.startswith("_fillminima") and f.endswith(".so"):
                        copy(os.path.join(root, f), os.path.join(fmask_path, '_fillminima.so'))
                    if f.startswith("_fillminima") and f.endswith(".pyd"):
                        copy(os.path.join(root, f), os.path.join(fmask_path, '_fillminima.pyd'))
                    if f.startswith("_valueindexes") and f.endswith(".so"):
                        copy(os.path.join(root, f), os.path.join(fmask_path, '_valueindexes.so'))
                    if f.startswith("_valueindexes") and f.endswith(".pyd"):
                        copy(os.path.join(root, f), os.path.join(fmask_path, '_valueindexes.pyd'))
        rmtree(os.path.join(fmask_libs, "build"), ignore_errors=True)
        rmtree(os.path.join(fmask_libs, "temp"), ignore_errors=True)


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load CloudMasking class from file CloudMasking.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    # check if the fillminima and valueindexes are build, else compile it
    fmask_libs()

    from .cloud_masking import CloudMasking
    return CloudMasking(iface)
