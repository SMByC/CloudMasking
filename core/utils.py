# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Cloud Filters
                                 A QGIS plugin
 Cloud masking for landsat products using different process suck as fmask
                             -------------------
        copyright            : (C) 2016 by Xavier Corredor Llano, SMBYC
        email                : xcorredorl@ideam.gov.co
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import os

from PyQt4 import QtGui
import qgis.core


def get_prefer_name(file_path):
    """Search the prefer name for band: band1 > B1"""
    path_dir, band_file = os.path.split(file_path)
    # prefer thermal band61/2 over B6_VCID_1/2 in Landsat 7
    if band_file.startswith("LE7"):
        file_sr_bandN = band_file.replace("_B6_VCID_", "_band6").replace(".TIF", ".tif")
        if os.path.isfile(os.path.join(path_dir, file_sr_bandN)):
            return os.path.join(path_dir, file_sr_bandN)
    # prefer bandN over BN (i.e. band1.tif over B1.TIF)
    file_bandN = band_file.replace("_B", "_band").replace(".TIF", ".tif")
    if os.path.isfile(os.path.join(path_dir, file_bandN)):
        return os.path.join(path_dir, file_bandN)
    # return original
    return file_path


def apply_symbology(rlayer, symbology, symbology_enabled, transparent=255):
    """ Apply classification symbology to raster layer """
    # See: QgsRasterRenderer* QgsSingleBandPseudoColorRendererWidget::renderer()
    # https://github.com/qgis/QGIS/blob/master/src/gui/raster/qgssinglebandpseudocolorrendererwidget.cpp
    # Get raster shader
    raster_shader = qgis.core.QgsRasterShader()
    # Color ramp shader
    color_ramp_shader = qgis.core.QgsColorRampShader()
    # Loop over Fmask values and add to color item list
    color_ramp_item_list = []
    for name, value, enable in zip(['land', 'cloud', 'shadow', 'snow', 'water', 'blue band'],
                                   [1, 2, 3, 4, 5, 6],
                                   symbology_enabled):
        if enable is False:
            continue
        color = symbology[name]
        # Color ramp item - color, label, value
        color_ramp_item = qgis.core.QgsColorRampShader.ColorRampItem(
            value,
            QtGui.QColor(color[0], color[1], color[2], color[3]),
            name
        )
        color_ramp_item_list.append(color_ramp_item)
    # After getting list of color ramp items
    color_ramp_shader.setColorRampItemList(color_ramp_item_list)
    # Exact color ramp
    color_ramp_shader.setColorRampType('EXACT')
    # Add color ramp shader to raster shader
    raster_shader.setRasterShaderFunction(color_ramp_shader)
    # Create color renderer for raster layer
    renderer = qgis.core.QgsSingleBandPseudoColorRenderer(
        rlayer.dataProvider(),
        1,
        raster_shader)
    # Set renderer for raster layer
    rlayer.setRenderer(renderer)

    # Set NoData transparency
    if not isinstance(transparent, list):
        transparent = [transparent]
    nodata = [qgis.core.QgsRasterRange(t, t) for t in transparent]
    rlayer.dataProvider().setUserNoDataValue(1, nodata)

    # Repaint
    if hasattr(rlayer, 'setCacheImage'):
        rlayer.setCacheImage(None)
    rlayer.triggerRepaint()
