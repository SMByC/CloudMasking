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
import os, sys
import tempfile

from qgis.core import QgsMapLayerRegistry, QgsRasterLayer

plugin_folder = os.path.dirname(os.path.dirname(__file__))
if plugin_folder not in sys.path:
    sys.path.append(plugin_folder)

from libs import gdal_merge


class ColorStack(object):
    """Making the Red-Green-Blue Stack for view the scene
    """

    def __init__(self, mtl_path, mtl_file, tmp_dir=None):
        self.mtl_path = mtl_path
        self.mtl_file = mtl_file
        # dir to input landsat files
        self.input_dir = os.path.dirname(mtl_path)
        # tmp dir for process
        self.tmp_dir = tempfile.mkdtemp(dir=tmp_dir)
        # bar and status progress
        self.process_status = None
        self.process_bar = None

        # get_metadata
        self.landsat_version = int(self.mtl_file['SPACECRAFT_ID'].split('_')[-1])

        # select the bands for color stack
        if self.landsat_version in [4, 5, 7]:
            self.color_bands = [
                os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_'+str(N)])
                for N in [1, 2, 3, 4, 5, 7]]
        if self.landsat_version == 8:
            self.color_bands = [
                os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_'+str(N)])
                for N in [2, 3, 4, 5, 6, 7]]

    def do_color_stack(self):

        # tmp file for color bands stack
        self.color_stack_file = os.path.join(self.tmp_dir, "color_stack.tif")

        gdal_merge.main(["", "-separate", "-of", "GTiff", "-co", "COMPRESSED=YES", "-o",
                         self.color_stack_file] + self.color_bands)

    def load_color_stack(self):
        """Add to QGIS the color stack file
        """
        self.color_stack_rlayer = QgsRasterLayer(self.color_stack_file, "Color Stack " + self.mtl_file['LANDSAT_SCENE_ID'])
        QgsMapLayerRegistry.instance().addMapLayer(self.color_stack_rlayer)

