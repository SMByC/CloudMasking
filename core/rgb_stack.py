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


class RGB_Stack(object):
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
        if self.landsat_version == 8:
            # select the bands for RGB
            self.rgb_bands = [
                os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_'+str(N)])
                for N in [4, 5, 6]]
        # TODO: added other landsat version

    def do_rgb_stack(self):

        # tmp file for rgb bands stack
        self.rgb_stack_file = os.path.join(self.tmp_dir, "rgb_stack.tif")

        gdal_merge.main(["", "-separate", "-of", "GTiff", "-co", "COMPRESSED=YES", "-o",
                         self.rgb_stack_file] + self.rgb_bands)

    def load_rgb_stack(self):
        """Add to QGIS the RGB stack file
        """
        self.rgb_stack_rlayer = QgsRasterLayer(self.rgb_stack_file, "RGB stack "+self.mtl_file['LANDSAT_SCENE_ID'])
        QgsMapLayerRegistry.instance().addMapLayer(self.rgb_stack_rlayer)

