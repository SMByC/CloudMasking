# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CloudMasking
                                 A QGIS plugin
 Cloud masking using different process suck as fmask
                             -------------------
        begin                : 2015-12-17
        copyright            : (C) 2015 by Xavier Corredor Llano, SMBYC
        email                : xcorredorl@ideam.gov.co
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load CloudMasking class from file CloudMasking.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .cloud_masking import CloudMasking
    return CloudMasking(iface)
