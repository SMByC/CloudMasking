# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CloudMaskingUtils
                                 A QGIS plugin
 Cloud masking for landsat products using different process suck as fmask
                             -------------------
        copyright            : (C) 2016-2017 by Xavier Corredor Llano, SMBYC
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
"""
# some code initial base on Fmask Configure plugin by Chris Holden

import os


def mtl2dict(filename, to_float=True):
    """ Reads in filename and returns a dict with MTL metadata.
    """

    assert os.path.isfile(filename), '{} is not a file'.format(filename)

    mtl = {}

    # Open filename with context manager
    with open(filename, 'rb') as f:
        # Read all lines in file
        for line in f.readlines():
            # Split KEY = VALUE entries
            key_value = line.strip().split(' = ')

            # Ignore END lines
            if len(key_value) != 2:
                continue

            key = key_value[0].strip()
            value = key_value[1].strip('"')

            # Try to convert to float
            if to_float is True:
                try:
                    value = float(value)
                except:
                    pass
            # add to dict
            mtl[key] = value

    return mtl
