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
from subprocess import call
from datetime import datetime

from PyQt4.QtGui import QApplication

plugin_folder = os.path.dirname(os.path.dirname(__file__))
if plugin_folder not in sys.path:
    sys.path.append(plugin_folder)

from libs import gdal_merge
from libs.fmask import fmask, landsatTOA, landsatangles, config, saturationcheck
from libs.rios import fileinfo

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
        # bar and status progress
        self.process_status = None
        self.process_bar = None
        # set initial clipping status
        self.clipping_extent = False

        # get_metadata
        self.landsat_version = int(self.mtl_file['SPACECRAFT_ID'].split('_')[-1])
        self.landsat_scene = self.mtl_file['LANDSAT_SCENE_ID']

        # set bands for reflective and thermal
        if self.landsat_version in [4, 5]:
            # get the reflective file names bands
            self.reflective_bands = [
                os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_'+str(N)])
                for N in [1, 2, 3, 4, 5, 7]]
            # get the thermal file names bands
            self.thermal_bands = [
                os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_' + str(N)])
                for N in [6]]

        # set bands for reflective and thermal
        if self.landsat_version == 7:
            # get the reflective file names bands
            self.reflective_bands = [
                os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_'+str(N)])
                for N in [1, 2, 3, 4, 5, 7]]
            # get the thermal file names bands
            self.thermal_bands = [
                os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_6_VCID_' + str(N)])
                for N in [1, 2]]

        # set bands for reflective and thermal
        if self.landsat_version == 8:
            # get the reflective file names bands
            self.reflective_bands = [
                os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_'+str(N)])
                for N in [1, 2, 3, 4, 5, 6, 7, 9]]
            # get the thermal file names bands
            self.thermal_bands = [
                os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_' + str(N)])
                for N in [10, 11]]

    def do_fmask(self, cirrusprobratio=0.04, mincloudsize=0, cloudbufferdistance=150, shadowbufferdistance=300):

        ########################################
        # reflective bands stack

        # tmp file for reflective bands stack
        self.reflective_stack_file = os.path.join(self.tmp_dir, "reflective_stack.tif")

        if not os.path.isfile(self.reflective_stack_file):
            self.process_status.setText("Making reflective bands stack...")
            self.process_bar.setValue(10)
            QApplication.processEvents()

            gdal_merge.main(["", "-separate", "-of", "GTiff", "-co", "COMPRESSED=YES", "-o",
                             self.reflective_stack_file] + self.reflective_bands)

        ########################################
        # thermal bands stack

        # tmp file for reflective bands stack
        self.thermal_stack_file = os.path.join(self.tmp_dir, "thermal_stack.tif")

        if not os.path.isfile(self.thermal_stack_file):
            self.process_status.setText("Making thermal bands stack...")
            self.process_bar.setValue(20)
            QApplication.processEvents()

            gdal_merge.main(["", "-separate", "-of", "GTiff", "-co", "COMPRESSED=YES", "-o",
                             self.thermal_stack_file] + self.thermal_bands)

        ########################################
        # clipping the reflective bands stack

        if self.clipping_extent:
            self.process_status.setText("Clipping the reflective stack...")
            self.process_bar.setValue(24)
            QApplication.processEvents()

            self.reflective_stack_clip_file = os.path.join(self.tmp_dir, "reflective_stack_clip.tif")
            return_code = call(
                'gdal_translate -projwin ' +
                ' '.join([str(x) for x in [self.extent_x1, self.extent_y1, self.extent_x2, self.extent_y2]]) +
                ' -of GTiff ' + self.reflective_stack_file + ' ' + self.reflective_stack_clip_file,
                shell=True)
            self.reflective_stack_for_process = self.reflective_stack_clip_file
        else:
            self.reflective_stack_for_process = self.reflective_stack_file

        ########################################
        # clipping the thermal bands stack

        if self.clipping_extent:
            self.process_status.setText("Clipping the thermal stack...")
            self.process_bar.setValue(27)
            QApplication.processEvents()

            self.thermal_stack_clip_file = os.path.join(self.tmp_dir, "thermal_stack_clip.tif")
            return_code = call(
                'gdal_translate -projwin ' +
                ' '.join([str(x) for x in [self.extent_x1, self.extent_y1, self.extent_x2, self.extent_y2]]) +
                ' -of GTiff ' + self.thermal_stack_file + ' ' + self.thermal_stack_clip_file,
                shell=True)
            self.thermal_stack_for_process = self.thermal_stack_clip_file
        else:
            self.thermal_stack_for_process = self.thermal_stack_file

        ########################################
        # estimates of per-pixel angles for sun
        # and satellite azimuth and zenith
        #
        # fmask_usgsLandsatMakeAnglesImage.py

        # tmp file for angles
        self.angles_file = os.path.join(self.tmp_dir, "angles.tif")

        self.process_status.setText("Making fmask angles file...")
        self.process_bar.setValue(30)
        QApplication.processEvents()

        mtlInfo = config.readMTLFile(self.mtl_path)

        imgInfo = fileinfo.ImageInfo(self.reflective_stack_for_process)
        corners = landsatangles.findImgCorners(self.reflective_stack_for_process, imgInfo)
        nadirLine = landsatangles.findNadirLine(corners)

        extentSunAngles = landsatangles.sunAnglesForExtent(imgInfo, mtlInfo)
        satAzimuth = landsatangles.satAzLeftRight(nadirLine)

        landsatangles.makeAnglesImage(self.reflective_stack_for_process, self.angles_file,
                                      nadirLine, extentSunAngles, satAzimuth, imgInfo)

        ########################################
        # saturation mask
        #
        # fmask_usgsLandsatSaturationMask.py

        # tmp file for angles
        self.saturationmask_file = os.path.join(self.tmp_dir, "saturationmask.tif")

        self.process_status.setText("Making saturation mask file...")
        self.process_bar.setValue(40)
        QApplication.processEvents()

        if self.landsat_version == 4:
            sensor = config.FMASK_LANDSAT47
        elif self.landsat_version == 5:
            sensor = config.FMASK_LANDSAT47
        elif self.landsat_version == 7:
            sensor = config.FMASK_LANDSAT47
        elif self.landsat_version == 8:
            sensor = config.FMASK_LANDSAT8

        # needed so the saturation function knows which
        # bands are visible etc.
        fmaskConfig = config.FmaskConfig(sensor)

        saturationcheck.makeSaturationMask(fmaskConfig, self.reflective_stack_for_process,
                                           self.saturationmask_file)

        ########################################
        # top of Atmosphere reflectance
        #
        # fmask_usgsLandsatTOA.py

        # tmp file for toa
        self.toa_file = os.path.join(self.tmp_dir, "toa.tif")

        self.process_status.setText("Making top of Atmosphere ref...")
        self.process_bar.setValue(50)
        QApplication.processEvents()

        landsatTOA.makeTOAReflectance(self.reflective_stack_for_process, self.mtl_path,
                                      self.angles_file, self.toa_file)

        ########################################
        # cloud mask
        #
        # fmask_usgsLandsatStacked.py

        # tmp file for cloud
        self.cloud_file = os.path.join(self.tmp_dir, "cloud_mask_{}.tif".format(datetime.now().strftime('%H%M%S')))

        self.process_status.setText("Making cloud mask with fmask...")
        self.process_bar.setValue(70)
        QApplication.processEvents()

        # 1040nm thermal band should always be the first (or only) band in a
        # stack of Landsat thermal bands
        thermalInfo = config.readThermalInfoFromLandsatMTL(self.mtl_path)

        anglesInfo = config.AnglesFileInfo(self.angles_file, 3, self.angles_file,
                                           2, self.angles_file, 1, self.angles_file, 0)

        if self.landsat_version == 4:
            sensor = config.FMASK_LANDSAT47
        elif self.landsat_version == 5:
            sensor = config.FMASK_LANDSAT47
        elif self.landsat_version == 7:
            sensor = config.FMASK_LANDSAT47
        elif self.landsat_version == 8:
            sensor = config.FMASK_LANDSAT8

        fmaskFilenames = config.FmaskFilenames()
        fmaskFilenames.setTOAReflectanceFile(self.toa_file)
        fmaskFilenames.setThermalFile(self.thermal_stack_for_process)
        fmaskFilenames.setOutputCloudMaskFile(self.cloud_file)
        fmaskFilenames.setSaturationMask(self.saturationmask_file)  # TODO: optional

        fmaskConfig = config.FmaskConfig(sensor)
        fmaskConfig.setThermalInfo(thermalInfo)
        fmaskConfig.setAnglesInfo(anglesInfo)
        fmaskConfig.setKeepIntermediates(False)
        fmaskConfig.setVerbose(False)
        fmaskConfig.setTempDir(self.tmp_dir)
        fmaskConfig.setMinCloudSize(mincloudsize)
        fmaskConfig.setCirrusProbRatio(cirrusprobratio)

        # Work out a suitable buffer size, in pixels, dependent
        # on the resolution of the input TOA image
        toaImgInfo = fileinfo.ImageInfo(self.toa_file)
        fmaskConfig.setCloudBufferSize(int(cloudbufferdistance / toaImgInfo.xRes))
        fmaskConfig.setShadowBufferSize(int(shadowbufferdistance / toaImgInfo.xRes))

        fmask.doFmask(fmaskFilenames, fmaskConfig)


        ### ending fmask process
        self.process_status.setText("DONE")
        self.process_bar.setValue(100)
        QApplication.processEvents()
