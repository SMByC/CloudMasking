# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Cloud Filters
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
import os
import tempfile

from qgis.core import QgsProject, QgsRasterLayer

# from plugins
from CloudMasking.core.utils import get_prefer_name
from CloudMasking.libs import gdal_merge


class ColorStack(object):
    """Making the Red-Green-Blue Stack for view the scene
    """

    def __init__(self, mtl_path, mtl_file, bands, tmp_dir=None):
        self.mtl_path = mtl_path
        self.mtl_file = mtl_file
        # dir to input landsat files
        self.input_dir = os.path.dirname(mtl_path)
        # tmp dir for process
        if tmp_dir:
            self.tmp_dir = tmp_dir
        else:
            self.tmp_dir = tempfile.mkdtemp()
        # bar and status progress
        self.process_status = None
        self.process_bar = None
        # set base name
        self.base_name = "RGB ({}-{}-{})".format(*bands)

        # get file names
        self.color_bands = [
            os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_'+str(N)])
            for N in bands]

        # set the prefer file name band for process
        self.color_bands = [get_prefer_name(file_path) for file_path in self.color_bands]

        # when the raw bands not exits user the SR (C2)
        if False in [os.path.exists(layer) for layer in self.color_bands]:
            self.color_bands = [
                os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_SR_' + str(N)])
                for N in bands]

    def do_color_stack(self):

        # tmp file for color bands stack
        self.color_stack_file = os.path.join(self.tmp_dir, self.base_name + "_" +
                                             self.mtl_file['LANDSAT_SCENE_ID'] + ".tif")

        gdal_merge.main(["", "-separate", "-of", "GTiff", "-o",
                         self.color_stack_file] + self.color_bands)

    def load_color_stack(self):
        """Add to QGIS the color stack file
        """
        self.color_stack_rlayer = QgsRasterLayer(self.color_stack_file, self.base_name + " " +
                                                 self.mtl_file['DATE_ACQUIRED'] + " " + self.mtl_file['LANDSAT_SCENE_ID'])
        QgsProject.instance().addMapLayer(self.color_stack_rlayer)

