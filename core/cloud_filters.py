# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CloudMasking
                                 A QGIS plugin
 Cloud masking for landsat products using different process suck as fmask
                             -------------------
        copyright            : (C) 2016-2018 by Xavier Corredor Llano, SMBYC
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

import os, sys
import tempfile
from datetime import datetime
from subprocess import call

from osgeo import gdal
from PyQt4.QtCore import QCoreApplication

# from plugins
from CloudMasking.core.utils import get_prefer_name, update_process_bar, binary_combination, check_values_in_image, \
    get_extent
from CloudMasking.libs import gdal_merge, gdal_calc

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
        self.clipping_with_shape = False
        # save all result files of cloud masking
        self.cloud_masking_files = []

        # get_metadata
        self.landsat_version = int(self.mtl_file['SPACECRAFT_ID'][-1])
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

    def clip(self, in_stack_file, out_clipped_file, nodata=0, process_bar=True):
        """
        Clipping the stack file only if is activated selected area or shape area,
        else return the original image
        """
        if not self.clipping_extent and not self.clipping_with_shape:
            return in_stack_file

        if process_bar:
            update_process_bar(self.process_bar, 24, self.process_status,
                               self.tr(u"Clipping the reflective stack..."))

        if self.clipping_extent:
            self.do_clipping_extent(in_stack_file, out_clipped_file)

        if self.clipping_with_shape:
            self.do_clipping_with_shape(in_stack_file, os.path.abspath(self.shape_path),
                                        out_clipped_file, self.crop_to_cutline, nodata)

        return out_clipped_file

    def do_clipping_extent(self, in_file, out_file):
        # check and adjust the maximum/minimum values for extent selected
        # based on the original image
        in_extent = get_extent(in_file)
        if self.extent_x1 < in_extent[0]: self.extent_x1 = in_extent[0]
        if self.extent_y1 > in_extent[1]: self.extent_y1 = in_extent[1]
        if self.extent_x2 > in_extent[2]: self.extent_x2 = in_extent[2]
        if self.extent_y2 < in_extent[3]: self.extent_y2 = in_extent[3]

        gdal.Translate(out_file, in_file, projWin=[self.extent_x1, self.extent_y1, self.extent_x2, self.extent_y2])

    def do_clipping_with_shape(self, stack_file, shape_path, clip_file, crop_to_cutline, nodata=0):
        # first cut to shape area extent
        shape_extent = [self.shape_extent.xMinimum(), self.shape_extent.yMaximum(),
                        self.shape_extent.xMaximum(), self.shape_extent.yMinimum()]
        stack_file_trimmed = os.path.join(self.tmp_dir, "stack_file_trimmed.tif")
        gdal.Translate(stack_file_trimmed, stack_file, projWin=shape_extent)

        if crop_to_cutline:
            #  -crop_to_cutline
            call('gdalwarp -multi -wo NUM_THREADS=ALL_CPUS --config GDALWARP_IGNORE_BAD_CUTLINE YES -cutline "{}" '
                 '-dstnodata 0 "{}" "{}"'.format(shape_path, stack_file_trimmed, clip_file), shell=True)
        else:
            call('gdalwarp -multi -wo NUM_THREADS=ALL_CPUS --config GDALWARP_IGNORE_BAD_CUTLINE YES -cutline "{}" '
                 '-dstnodata {} "{}" "{}"'.format(shape_path, nodata, stack_file_trimmed, clip_file), shell=True)
        os.remove(stack_file_trimmed)

    def do_nodata_mask(self, img_to_mask):
        band_1 = get_prefer_name(os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_1']))

        band_from_mask = self.clip(band_1, os.path.join(self.tmp_dir, "band_from_mask.tif"), process_bar=False)

        gdal_calc.Calc(calc="A*(B>0)+255*logical_or(B==0,A==0)", outfile=img_to_mask.replace(".tif", "1.tif"),
                       A=img_to_mask, B=band_from_mask, NoDataValue=255)

        # unset the nodata
        os.remove(img_to_mask)
        if os.path.isfile(os.path.join(self.tmp_dir, "band_from_mask.tif")):
            os.remove(os.path.join(self.tmp_dir, "band_from_mask.tif"))
        gdal.Translate(img_to_mask, img_to_mask.replace(".tif", "1.tif"), noData="none")

    def do_fmask(self, filters_enabled, min_cloud_size=0, cloud_prob_thresh=0.225, cloud_buffer_size=4,
                 shadow_buffer_size=6, cirrus_prob_ratio=0.04, nir_fill_thresh=0.02, swir2_thresh=0.03,
                 whiteness_thresh=0.7, swir2_water_test=0.03, nir_snow_thresh=0.11, green_snow_thresh=0.1):

        ########################################
        # reflective bands stack

        # tmp file for reflective bands stack
        self.reflective_stack_file = os.path.join(self.tmp_dir, "reflective_stack.tif")

        if not os.path.isfile(self.reflective_stack_file):
            update_process_bar(self.process_bar, 10, self.process_status,
                               self.tr(u"Making reflective bands stack..."))

            gdal_merge.main(["", "-separate", "-of", "GTiff", "-o",
                             self.reflective_stack_file] + self.reflective_bands)

        ########################################
        # thermal bands stack

        # tmp file for reflective bands stack
        self.thermal_stack_file = os.path.join(self.tmp_dir, "thermal_stack.tif")

        if not os.path.isfile(self.thermal_stack_file):
            update_process_bar(self.process_bar, 20, self.process_status,
                               self.tr(u"Making thermal bands stack..."))

            gdal_merge.main(["", "-separate", "-of", "GTiff", "-o",
                             self.thermal_stack_file] + self.thermal_bands)

        ########################################
        # clipping the reflective bands stack (only if is activated selected area or shape area)
        self.reflective_stack_clip_file = os.path.join(self.tmp_dir, "reflective_stack_clip.tif")
        self.reflective_stack_for_process = self.clip(self.reflective_stack_file, self.reflective_stack_clip_file)

        ########################################
        # clipping the thermal bands stack (only if is activated selected area or shape area)
        self.thermal_stack_clip_file = os.path.join(self.tmp_dir, "thermal_stack_clip.tif")
        self.thermal_stack_for_process = self.clip(self.thermal_stack_file, self.thermal_stack_clip_file)

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
        fmaskConfig.setVerbose(True)
        fmaskConfig.setTempDir(self.tmp_dir)

        # Set the settings fmask filters from widget to FmaskConfig
        fmaskConfig.setMinCloudSize(min_cloud_size)
        fmaskConfig.setEqn17CloudProbThresh(cloud_prob_thresh)
        fmaskConfig.setCloudBufferSize(int(cloud_buffer_size))
        fmaskConfig.setShadowBufferSize(int(shadow_buffer_size))
        fmaskConfig.setCirrusProbRatio(cirrus_prob_ratio)
        fmaskConfig.setEqn19NIRFillThresh(nir_fill_thresh)
        fmaskConfig.setEqn1Swir2Thresh(swir2_thresh)
        fmaskConfig.setEqn2WhitenessThresh(whiteness_thresh)
        fmaskConfig.setEqn7Swir2Thresh(swir2_water_test)
        fmaskConfig.setEqn20NirSnowThresh(nir_snow_thresh)
        fmaskConfig.setEqn20GreenSnowThresh(green_snow_thresh)

        # set to 1 for all Fmask filters disabled
        if filters_enabled["Fmask Cloud"]:
            fmask.OUTCODE_CLOUD = 2
        else:
            fmask.OUTCODE_CLOUD = 1

        if filters_enabled["Fmask Shadow"]:
            fmask.OUTCODE_SHADOW = 3
        else:
            fmask.OUTCODE_SHADOW = 1

        if filters_enabled["Fmask Snow"]:
            fmask.OUTCODE_SNOW = 4
        else:
            fmask.OUTCODE_SNOW = 1

        if filters_enabled["Fmask Water"]:
            fmask.OUTCODE_WATER = 5
        else:
            fmask.OUTCODE_WATER = 1

        # process Fmask
        fmask.doFmask(fmaskFilenames, fmaskConfig)

        # save final result of masking
        self.cloud_masking_files.append(self.cloud_fmask_file)

        ### ending fmask process
        update_process_bar(self.process_bar, 100, self.process_status,
                           self.tr(u"DONE"))

    def do_blue_band(self, bb_threshold):
        # tmp file for cloud
        self.cloud_bb_file = os.path.join(self.tmp_dir, "cloud_bb_{}.tif".format(datetime.now().strftime('%H%M%S')))
        update_process_bar(self.process_bar, 50, self.process_status,
                           self.tr(u"Making the blue band filter..."))

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
        # clipping the Blue Band (only if is activated selected area or shape area)
        self.blue_band_clip_file = os.path.join(self.tmp_dir, "blue_band_clip.tif")
        self.blue_band_for_process = self.clip(self.blue_band_file, self.blue_band_clip_file)

        ########################################
        # do blue band filter
        gdal_calc.Calc(calc="1*(A<{threshold})+6*(A>={threshold})".format(threshold=bb_threshold),
                       A=self.blue_band_for_process, outfile=self.cloud_bb_file, type="Byte")

        # save final result of masking
        self.cloud_masking_files.append(self.cloud_bb_file)

        ### ending process
        update_process_bar(self.process_bar, 100, self.process_status,
                           self.tr(u"DONE"))

    def do_cloud_qa_l457(self, cloud_qa_file, checked_items, specific_values=[]):
        # tmp file for cloud
        self.cloud_qa = os.path.join(self.tmp_dir, "cloud_qa_{}.tif".format(datetime.now().strftime('%H%M%S')))
        update_process_bar(self.process_bar, 50, self.process_status,
                           self.tr(u"Making the Cloud QA filter..."))

        ########################################
        # clipping the QA Mask (only if is activated selected area or shape area)
        self.cloud_qa_clip_file = os.path.join(self.tmp_dir, "cloud_qa_clip.tif")
        self.cloud_qa_for_process = self.clip(cloud_qa_file, self.cloud_qa_clip_file)

        ########################################
        # convert selected items to binary and decimal values
        values_combinations = []
        # bits not used or not fill
        static_bits = [6, 7]

        # generate the values combinations for one bit items selected
        cloud_qa_items_1b = {"Dark Dense Vegetation (bit 0)": [0], "Cloud (bit 1)": [1], "Cloud Shadow (bit 2)": [2],
                             "Adjacent to cloud (bit 3)": [3], "Snow (bit 4)": [4], "Water (bit 5)": [5]}

        for item, bits in cloud_qa_items_1b.items():
            binary = [0] * 8
            if checked_items[item]:
                binary[(len(binary) - 1) - bits[0]] = 1
                values_combinations += list(binary_combination(binary, static_bits + bits))

        # add the specific values
        if specific_values:
            values_combinations += specific_values

        # delete duplicates
        values_combinations = list(set(values_combinations))

        # only left the values inside the image
        values_combinations = check_values_in_image(self.cloud_qa_for_process, values_combinations)

        filter_values = ",".join(["A==" + str(x) for x in values_combinations])
        not_filter_values = ",".join(["A!=" + str(x) for x in values_combinations])

        ########################################
        # do QA Mask filter
        tmp_cqa_file = os.path.join(self.tmp_dir, "cloud_qa.tif")
        gdal_calc.Calc(calc="1*(numpy.all([{nfv}], axis=0)) + 7*(numpy.any([{fv}], axis=0))".format(fv=filter_values,
                                                                                                    nfv=not_filter_values),
                       A=self.cloud_qa_for_process, outfile=tmp_cqa_file, type="Byte", NoDataValue=1)
        # unset the nodata, leave the 1 (valid fields)
        gdal.Translate(self.cloud_qa, tmp_cqa_file, noData="none")
        # delete tmp files
        os.remove(tmp_cqa_file)

        # save final result of masking
        self.cloud_masking_files.append(self.cloud_qa)

        ### ending process
        update_process_bar(self.process_bar, 100, self.process_status,
                           self.tr(u"DONE"))

    def do_aerosol_l8(self, aerosol_file, checked_items, specific_values=[]):
        # tmp file for cloud
        self.aerosol = os.path.join(self.tmp_dir, "aerosol_{}.tif".format(datetime.now().strftime('%H%M%S')))
        update_process_bar(self.process_bar, 50, self.process_status,
                           self.tr(u"Making the Aerosol filter..."))

        ########################################
        # clipping the QA Mask (only if is activated selected area or shape area)
        self.aerosol_clip_file = os.path.join(self.tmp_dir, "aerosol_clip.tif")
        self.aerosol_for_process = self.clip(aerosol_file, self.aerosol_clip_file)

        ########################################
        # convert selected items to binary and decimal values
        values_combinations = []
        # bits not used or not fill
        static_bits = [0, 4, 5]

        # generate the values combinations for one bit items selected
        aerosol_items_1b = {"Aerosol Retrieval - Valid (bit 1)": [1],
                            "Aerosol Retrieval - Interpolated (bit 2)": [2],
                            "Water Pixel (bit 3)": [3]}

        for item, bits in aerosol_items_1b.items():
            binary = [0]*8
            if checked_items[item]:
                binary[(len(binary) - 1) - bits[0]] = 1
                values_combinations += list(binary_combination(binary, static_bits + bits))

        # generate the values combinations for two bits items selected
        aerosol_items_2b = {"Aerosol Content (bits 6-7)": [6, 7]}
        levels = {"Climatology content": [0, 0], "Low content": [0, 1],
                  "Average content": [1, 0], "High content": [1, 1]}

        for item, bits in aerosol_items_2b.items():
            if item in checked_items.keys():
                for level in checked_items[item]:
                    binary = [0]*8
                    binary[bits[0]:bits[1]+1] = (levels[level])[::-1]
                    binary.reverse()
                    values_combinations += list(binary_combination(binary, static_bits + bits))

        # add the specific values
        if specific_values:
            values_combinations += specific_values

        # delete duplicates
        values_combinations = list(set(values_combinations))

        # only left the values inside the image
        values_combinations = check_values_in_image(self.aerosol_for_process, values_combinations)

        filter_values = ",".join(["A=="+str(x) for x in values_combinations])
        not_filter_values = ",".join(["A!="+str(x) for x in values_combinations])

        ########################################
        # do QA Mask filter
        tmp_cqa_file = os.path.join(self.tmp_dir, "aerosol.tif")
        gdal_calc.Calc(calc="1*(numpy.all([{nfv}], axis=0)) + 8*(numpy.any([{fv}], axis=0))".format(fv=filter_values, nfv=not_filter_values),
                       A=self.aerosol_for_process, outfile=tmp_cqa_file, type="Byte", NoDataValue=1)
        # unset the nodata, leave the 1 (valid fields)
        gdal.Translate(self.aerosol, tmp_cqa_file, noData="none")
        # delete tmp files
        os.remove(tmp_cqa_file)

        # save final result of masking
        self.cloud_masking_files.append(self.aerosol)

        ### ending process
        update_process_bar(self.process_bar, 100, self.process_status,
                           self.tr(u"DONE"))

    def do_pixel_qa(self, pixel_qa_file, checked_items, specific_values=[]):
        """
        http://landsat.usgs.gov/qualityband.php
        """
        # tmp file for Pixel QA
        self.pixel_qa = os.path.join(self.tmp_dir, "pixel_qa_{}.tif".format(datetime.now().strftime('%H%M%S')))
        update_process_bar(self.process_bar, 50, self.process_status,
                           self.tr(u"Making the Pixel QA filter..."))

        ########################################
        # clipping the QA Mask (only if is activated selected area or shape area)
        self.pixel_qa_clip_file = os.path.join(self.tmp_dir, "pixel_qa_clip.tif")
        self.pixel_qa_for_process = self.clip(pixel_qa_file, self.pixel_qa_clip_file)

        ########################################
        # convert selected items to binary and decimal values
        values_combinations = []
        # bits not used or not fill
        if self.landsat_version in [4, 5, 7]:
            static_bits = [0, 1, 8, 9, 10, 11, 12, 13, 14, 15]
        if self.landsat_version in [8]:
            static_bits = [0, 1, 11, 12, 13, 14, 15]

        # generate the values combinations for one bit items selected
        pixel_qa_items_1b = {"Water (bit 2)": [2], "Cloud Shadow (bit 3)": [3],
                             "Snow (bit 4)": [4], "Cloud (bit 5)": [5]}
        if self.landsat_version in [8]:  # add to L8
            pixel_qa_items_1b["Terrain Occlusion (bit 10)"] = [10]

        for item, bits in pixel_qa_items_1b.items():
            binary = [0]*16
            if checked_items[item]:
                binary[(len(binary) - 1) - bits[0]] = 1
                values_combinations += list(binary_combination(binary, static_bits + bits))

        # generate the values combinations for two bits items selected
        if self.landsat_version in [4, 5, 7]:
            pixel_qa_items_2b = {"Cloud Confidence (bits 6-7)": [6, 7]}
        if self.landsat_version in [8]:
            pixel_qa_items_2b = {"Cloud Confidence (bits 6-7)": [6, 7], "Cirrus Confidence (bits 8-9)": [8, 9]}
        levels = {"0% None": [0, 0], "0-33% Low": [0, 1],
                  "34-66% Medium": [1, 0], "67-100% High": [1, 1]}

        for item, bits in pixel_qa_items_2b.items():
            if item in checked_items.keys():
                for level in checked_items[item]:
                    binary = [0] * 16
                    binary[bits[0]:bits[1]+1] = (levels[level])[::-1]
                    binary.reverse()
                    values_combinations += list(binary_combination(binary, static_bits + bits))

        # add the specific values
        if specific_values:
            values_combinations += specific_values

        # delete duplicates
        values_combinations = list(set(values_combinations))

        # only left the values inside the image
        values_combinations = check_values_in_image(self.pixel_qa_for_process, values_combinations)

        filter_values = ",".join(["A==" + str(x) for x in values_combinations])
        not_filter_values = ",".join(["A!=" + str(x) for x in values_combinations])

        ########################################
        # do QA Mask filter
        tmp_pqa_file = os.path.join(self.tmp_dir, "pixel_qa.tif")
        gdal_calc.Calc(calc="1*(numpy.all([{nfv}], axis=0)) + 9*(numpy.any([{fv}], axis=0))".format(fv=filter_values, nfv=not_filter_values),
                       A=self.pixel_qa_for_process, outfile=tmp_pqa_file, type="Byte", NoDataValue=1)
        # unset the nodata, leave the 1 (valid fields)
        gdal.Translate(self.pixel_qa, tmp_pqa_file, noData="none")
        # delete tmp files
        os.remove(tmp_pqa_file)

        # save final result of masking
        self.cloud_masking_files.append(self.pixel_qa)

        ### ending process
        update_process_bar(self.process_bar, 100, self.process_status,
                           self.tr(u"DONE"))
