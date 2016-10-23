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
import tempfile

from qgis.core import QgsMapLayerRegistry, QgsRasterLayer

# from plugins
from CloudMasking.core.utils import get_prefer_name
from CloudMasking.libs import gdal_merge


class ColorStack(object):
    """Making the Red-Green-Blue Stack for view the scene
    """

    def __init__(self, mtl_path, mtl_file, color_type, tmp_dir=None):
        self.mtl_path = mtl_path
        self.mtl_file = mtl_file
        self.color_type = color_type
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
        self.base_name = self.color_type.replace("_", " ").title()

        # get_metadata
        self.landsat_version = int(self.mtl_file['SPACECRAFT_ID'].split('_')[-1])

        ### select the bands for color stack for Landsat 4, 5 y 7
        if self.landsat_version in [4, 5, 7]:
            if self.color_type == "natural_color":
                self.color_bands = [
                    os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_'+str(N)])
                    for N in [3, 2, 1]]
            if self.color_type == "false_color":
                self.color_bands = [
                    os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_'+str(N)])
                    for N in [4, 3, 2]]
            if self.color_type == "infrareds":
                self.color_bands = [
                    os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_'+str(N)])
                    for N in [4, 5, 7]]
        ### select the bands for color stack for Landsat 8
        if self.landsat_version == 8:
            if self.color_type == "natural_color":
                self.color_bands = [
                    os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_'+str(N)])
                    for N in [4, 3, 2]]
            if self.color_type == "false_color":
                self.color_bands = [
                    os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_'+str(N)])
                    for N in [5, 4, 3]]
            if self.color_type == "infrareds":
                self.color_bands = [
                    os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_'+str(N)])
                    for N in [5, 6, 7]]

        # set the prefer file name band for process
        self.color_bands = [get_prefer_name(file_path) for file_path in self.color_bands]

    def do_color_stack(self):

        # tmp file for color bands stack
        self.color_stack_file = os.path.join(self.tmp_dir, self.base_name + "_" +
                                             self.mtl_file['LANDSAT_SCENE_ID'] + ".tif")

        gdal_merge.main(["", "-separate", "-of", "GTiff", "-co", "COMPRESSED=YES", "-o",
                         self.color_stack_file] + self.color_bands)

    def load_color_stack(self):
        """Add to QGIS the color stack file
        """
        self.color_stack_rlayer = QgsRasterLayer(self.color_stack_file, self.base_name +
                                                 " " + self.mtl_file['LANDSAT_SCENE_ID'])
        QgsMapLayerRegistry.instance().addMapLayer(self.color_stack_rlayer)

