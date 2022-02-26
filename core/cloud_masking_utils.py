# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CloudMaskingUtils
                                 A QGIS plugin
 Cloud masking for landsat products using different process suck as fmask
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
"""
# some code initial base on Fmask Configure plugin by Chris Holden

import os


def mtl2dict(filename, to_float=True):
    """ Reads in filename and returns a dict with MTL metadata.
    """

    assert os.path.isfile(filename), '{} is not a file'.format(filename)

    mtl = {}

    # Open filename with context manager
    with open(filename, 'r') as f:
        # Read all lines in file
        for line in f.readlines():
            # Split KEY = VALUE entries
            key_value = line.strip().split(' = ')

            # Ignore END lines
            if len(key_value) != 2:
                continue

            key = key_value[0].strip()
            value = key_value[1].strip('"')

            # not overwrite these variables
            if (key == "PROCESSING_LEVEL" and "PROCESSING_LEVEL" in mtl) or \
               (key == "FILE_NAME_QUALITY_L1_PIXEL" and "FILE_NAME_QUALITY_L1_PIXEL" in mtl):
                continue

            # storage surface reflectance products (C2) in a different variables
            if ("GROUP" in mtl and mtl["GROUP"] == "PRODUCT_CONTENTS" and
                "COLLECTION_NUMBER" in mtl and mtl["COLLECTION_NUMBER"] == 2 and
                key.startswith("FILE_NAME_BAND_")):

                if mtl["LANDSAT_PRODUCT_ID"].startswith(("LE7", "LE07")) and key == "FILE_NAME_BAND_ST_B6":
                    key = "FILE_NAME_BAND_SR_6"
                else:
                    key = key.replace("FILE_NAME_BAND_", "FILE_NAME_BAND_SR_")

            # Try to convert to float
            if to_float is True:
                try:
                    value = float(value)
                except:
                    pass
            # add to dict
            mtl[key] = value

        # fix Landsat 7 band 6 variable
        if "FILE_NAME_BAND_6_VCID_1" in mtl:
            mtl["FILE_NAME_BAND_6"] = mtl["FILE_NAME_BAND_6_VCID_1"]

    return mtl
