# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CloudMasking
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
from datetime import datetime

from PyQt4.QtCore import QCoreApplication
from PyQt4.QtGui import QApplication

# from plugins
from CloudMasking.core.utils import get_prefer_name, update_process_bar
from CloudMasking.libs import gdal_merge, gdal_calc, gdal_clip

# adding the libs plugin path
libs_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "libs")
if libs_folder not in sys.path:
    sys.path.append(libs_folder)

# from libs
from fmask import fmask, landsatTOA, landsatangles, config, saturationcheck
from rios import fileinfo


class CloudMaskingResult(object):
    """ Object for process, apply filters, masking and storing results
    """

    def __init__(self, mtl_path, mtl_file, tmp_dir=None):
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
        # set initial clipping status
        self.clipping_extent = False
        # save all result files of cloud masking
        self.cloud_masking_files = []

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

        # set the prefer file name band for process
        self.reflective_bands = [get_prefer_name(file_path) for file_path in self.reflective_bands]
        self.thermal_bands = [get_prefer_name(file_path) for file_path in self.thermal_bands]

    def tr(self, string, context=''):
        if context == '':
            context = self.__class__.__name__
        return QCoreApplication.translate(context, string)

    def do_clipping_extent(self, in_file, out_file):
        gdal_clip.main(in_file, out_file, [self.extent_x1, self.extent_x2, self.extent_y2, self.extent_y1])


    def do_fmask(self, min_cloud_size=0, cloud_buffer_size=4, shadow_buffer_size=6, cirrus_prob_ratio=0.04,
                 nir_fill_thresh=0.02, swir2_thresh=0.03, whiteness_thresh=0.7, swir2_water_test=0.03):

        ########################################
        # reflective bands stack

        # tmp file for reflective bands stack
        self.reflective_stack_file = os.path.join(self.tmp_dir, "reflective_stack.tif")

        if not os.path.isfile(self.reflective_stack_file):
            update_process_bar(self.process_bar, 10, self.process_status,
                               self.tr(u"Making reflective bands stack..."))

            gdal_merge.main(["", "-separate", "-of", "GTiff", "-co", "COMPRESSED=YES", "-o",
                             self.reflective_stack_file] + self.reflective_bands)

        ########################################
        # thermal bands stack

        # tmp file for reflective bands stack
        self.thermal_stack_file = os.path.join(self.tmp_dir, "thermal_stack.tif")

        if not os.path.isfile(self.thermal_stack_file):
            update_process_bar(self.process_bar, 20, self.process_status,
                               self.tr(u"Making thermal bands stack..."))

            gdal_merge.main(["", "-separate", "-of", "GTiff", "-co", "COMPRESSED=YES", "-o",
                             self.thermal_stack_file] + self.thermal_bands)

        ########################################
        # clipping the reflective bands stack

        if self.clipping_extent:
            update_process_bar(self.process_bar, 24, self.process_status,
                               self.tr(u"Clipping the reflective stack..."))

            self.reflective_stack_clip_file = os.path.join(self.tmp_dir, "reflective_stack_clip.tif")
            self.do_clipping_extent(self.reflective_stack_file, self.reflective_stack_clip_file)
            self.reflective_stack_for_process = self.reflective_stack_clip_file
        else:
            self.reflective_stack_for_process = self.reflective_stack_file

        ########################################
        # clipping the thermal bands stack

        if self.clipping_extent:
            update_process_bar(self.process_bar, 27, self.process_status,
                               self.tr(u"Clipping the thermal stack..."))

            self.thermal_stack_clip_file = os.path.join(self.tmp_dir, "thermal_stack_clip.tif")
            self.do_clipping_extent(self.thermal_stack_file, self.thermal_stack_clip_file)
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

        update_process_bar(self.process_bar, 30, self.process_status,
                           self.tr(u"Making fmask angles file..."))

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

        update_process_bar(self.process_bar, 40, self.process_status,
                           self.tr(u"Making saturation mask file..."))

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

        update_process_bar(self.process_bar, 50, self.process_status,
                           self.tr(u"Making top of Atmosphere ref..."))

        landsatTOA.makeTOAReflectance(self.reflective_stack_for_process, self.mtl_path,
                                      self.angles_file, self.toa_file)

        ########################################
        # cloud mask
        #
        # fmask_usgsLandsatStacked.py

        # tmp file for cloud
        self.cloud_fmask_file = os.path.join(self.tmp_dir, "cloud_fmask_{}.tif".format(datetime.now().strftime('%H%M%S')))

        update_process_bar(self.process_bar, 70, self.process_status,
                           self.tr(u"Making cloud mask with fmask..."))

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
        fmaskFilenames.setOutputCloudMaskFile(self.cloud_fmask_file)
        fmaskFilenames.setSaturationMask(self.saturationmask_file)  # TODO: optional

        fmaskConfig = config.FmaskConfig(sensor)
        fmaskConfig.setThermalInfo(thermalInfo)
        fmaskConfig.setAnglesInfo(anglesInfo)
        fmaskConfig.setKeepIntermediates(False)
        fmaskConfig.setVerbose(False)
        fmaskConfig.setTempDir(self.tmp_dir)

        # Set the settings fmask filters from widget to FmaskConfig
        fmaskConfig.setMinCloudSize(min_cloud_size)
        fmaskConfig.setCloudBufferSize(int(cloud_buffer_size))
        fmaskConfig.setShadowBufferSize(int(shadow_buffer_size))
        fmaskConfig.setCirrusProbRatio(cirrus_prob_ratio)
        fmaskConfig.setEqn19NIRFillThresh(nir_fill_thresh)
        fmaskConfig.setEqn1Swir2Thresh(swir2_thresh)
        fmaskConfig.setEqn2WhitenessThresh(whiteness_thresh)
        fmaskConfig.setEqn7Swir2Thresh(swir2_water_test)

        fmask.doFmask(fmaskFilenames, fmaskConfig)

        # save final result of masking
        self.cloud_masking_files.append(self.cloud_fmask_file)

        ### ending fmask process
        update_process_bar(self.process_bar, 100, self.process_status,
                           self.tr(u"DONE"))

    def do_blue_band(self, bb_threshold):
        # tmp file for cloud
        self.cloud_bb_file = os.path.join(self.tmp_dir, "cloud_bb_{}.tif".format(datetime.now().strftime('%H%M%S')))

        ########################################
        # select the Blue Band
        if self.landsat_version in [4, 5, 7]:
            # get the reflective file names bands
            self.blue_band_file = os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_1'])
        if self.landsat_version in [8]:
            # get the reflective file names bands
            self.blue_band_file = os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_2'])

        # fix file name
        self.blue_band_file = get_prefer_name(self.blue_band_file)

        ########################################
        # clipping the Blue Band
        if self.clipping_extent:
            update_process_bar(self.process_bar, 27, self.process_status,
                               self.tr(u"Clipping the blue band..."))

            self.blue_band_clip_file = os.path.join(self.tmp_dir, "blue_band_clip.tif")
            self.do_clipping_extent(self.blue_band_file, self.blue_band_clip_file)
            self.blue_band_for_process = self.blue_band_clip_file
        else:
            self.blue_band_for_process = self.blue_band_file

        ########################################
        # do blue band filter
        gdal_calc.main("1*(A<{threshold})+6*(A>={threshold})".format(threshold=bb_threshold),
                       self.cloud_bb_file, [self.blue_band_for_process], output_type="Byte")

        # save final result of masking
        self.cloud_masking_files.append(self.cloud_bb_file)

        ### ending fmask process
        update_process_bar(self.process_bar, 100, self.process_status,
                           self.tr(u"DONE"))
