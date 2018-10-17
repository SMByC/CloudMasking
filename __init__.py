# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CloudMasking
                                 A QGIS plugin
 Cloud masking using different process suck as fmask
                              -------------------
        copyright            : (C) 2016-2018 by Xavier Corredor Llano, SMByC
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
from distutils.core import run_setup
from shutil import copy


def fmask_libs():
    try:
        from CloudMasking.libs.fmask import _fillminima, _valueindexes
    except:
        # plugin path
        print("BUILDING libs for CloudMasking plugin...")
        plugin_folder = os.path.dirname(__file__)
        fmask_libs = os.path.join(plugin_folder, 'libs', 'fmask', 'libs')

        os.chdir(fmask_libs)
        run_setup('setup.py', ['build_ext'])

        # search and copy
        for root, dirs, files in os.walk(os.path.join(fmask_libs, "build")):
            if len(files) != 0:
                for f in files:
                    if f.startswith("_fillminima") and f.endswith(".so"):
                        copy(os.path.join(root, f), os.path.join(plugin_folder, 'libs', 'fmask', '_fillminima.so'))
                    if f.startswith("_fillminima") and f.endswith(".pyd"):
                        copy(os.path.join(root, f), os.path.join(plugin_folder, 'libs', 'fmask', '_fillminima.pyd'))
                    if f.startswith("_valueindexes") and f.endswith(".so"):
                        copy(os.path.join(root, f), os.path.join(plugin_folder, 'libs', 'fmask', '_valueindexes.so'))
                    if f.startswith("_valueindexes") and f.endswith(".pyd"):
                        copy(os.path.join(root, f), os.path.join(plugin_folder, 'libs', 'fmask', '_valueindexes.pyd'))


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
