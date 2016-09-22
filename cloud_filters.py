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
from subprocess import call
from PyQt4.QtGui import QApplication

from libs import gdal_merge


class CloudMaskingResult(object):
    """ Object for process, apply filters, masking and storing results
    """

    def __init__(self, mtl_path, mtl_file, tmp_dir=None):
        self.mtl_path = mtl_path
        self.mtl_file = mtl_file
        # dir to input landsat files
        self.input_dir = os.path.dirname(mtl_path)
        # tmp dir for process
        self.tmp_dir = tempfile.mkdtemp(dir=tmp_dir)

        # get_metadata
        self.landsat_version = int(self.mtl_file['SPACECRAFT_ID'].split('_')[-1])
        if self.landsat_version == 8:
            # get the reflective file names bands
            self.reflective_bands = [
                os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_'+str(N)])
                for N in [1,2,3,4,5,6,7,9]]
            # get the thermal file names bands
            self.thermal_bands = [
                os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_' + str(N)])
                for N in [10,11]]

    def do_fmask(self, processMaskStatus):

        ########################################
        # reflective bands stack

        # tmp file for reflective bands stack
        self.reflective_stack = os.path.join(self.tmp_dir, "reflective_stack.tif")

        processMaskStatus.setText("Making reflective bands stack...")
        QApplication.processEvents()

        gdal_merge.main(["", "-separate", "-of", "GTiff", "-co", "COMPRESSED=YES", "-o",
                         self.reflective_stack] + self.reflective_bands)

        ########################################
        # thermal bands stack

        # tmp file for reflective bands stack
        self.thermal_stack = os.path.join(self.tmp_dir, "thermal_stack.tif")

        processMaskStatus.setText("Making thermal bands stack...")
        QApplication.processEvents()

        gdal_merge.main(["", "-separate", "-of", "GTiff", "-co", "COMPRESSED=YES", "-o",
                         self.thermal_stack] + self.thermal_bands)




        processMaskStatus.setText("DONE")
        QApplication.processEvents()
