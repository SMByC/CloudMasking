# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CloudMasking
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

import os, sys
import platform
import tempfile
from datetime import datetime
from subprocess import call

from osgeo import gdal
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject, QgsRasterLayer, \
    QgsVectorFileWriter
from qgis.PyQt.QtCore import QCoreApplication, QFileInfo

# from plugins
from CloudMasking.core.utils import get_prefer_name, update_process_bar, binary_combination, check_values_in_image, \
    get_extent, get_layer_by_name, load_layer, unload_layer
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
        self.clipping_with_aoi = False
        self.clipping_with_shape = False
        # save all result files of cloud masking
        self.cloud_masking_files = []

        # get_metadata
        self.landsat_version = int(self.mtl_file['SPACECRAFT_ID'][-1])
        self.landsat_scene = self.mtl_file['LANDSAT_SCENE_ID']
        self.collection = int(self.mtl_file['COLLECTION_NUMBER'])

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
        if self.landsat_version in [8, 9]:
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
        if not self.clipping_with_aoi and not self.clipping_with_shape:
            return in_stack_file

        if process_bar:
            update_process_bar(self.process_bar, 24, self.process_status,
                               self.tr("Clipping..."))

        if os.path.isfile(out_clipped_file):
            os.remove(out_clipped_file)

        if self.clipping_with_aoi:
            tmp_aoi = os.path.join(self.tmp_dir, "aoi_tmp_{}.gpkg".format(datetime.now().strftime("%y%m%d_%H%M%S")))
            QgsVectorFileWriter.writeAsVectorFormat(self.aoi_features, tmp_aoi, "System", self.aoi_features.crs(), "GPKG")
            shape_layer = load_layer(tmp_aoi, add_to_legend=False)
            self.do_clipping_with_shape(in_stack_file, shape_layer, tmp_aoi, out_clipped_file, False, nodata)
            unload_layer(tmp_aoi)
            try: os.remove(tmp_aoi)
            except: pass

        if self.clipping_with_shape:
            shape_layer = get_layer_by_name(os.path.splitext(os.path.basename(self.shape_path))[0])
            if shape_layer is None:
                shape_layer = load_layer(self.shape_path, add_to_legend=False)
                self.do_clipping_with_shape(in_stack_file, shape_layer, os.path.abspath(self.shape_path),
                                            out_clipped_file, self.crop_to_cutline, nodata)
                unload_layer(self.shape_path)
            else:
                self.do_clipping_with_shape(in_stack_file, shape_layer, os.path.abspath(self.shape_path),
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

    def do_clipping_with_shape(self, stack_file, shape_layer, shape_path, clip_file, crop_to_cutline, nodata=0):
        # first cut to shape area extent
        stack_file_trimmed = os.path.join(self.tmp_dir, "stack_file_trimmed.tif")
        stack_layer = QgsRasterLayer(stack_file, QFileInfo(stack_file).baseName())

        # create convert coordinates
        crsSrc = QgsCoordinateReferenceSystem(shape_layer.crs())
        crsDest = QgsCoordinateReferenceSystem(stack_layer.crs())
        xform = QgsCoordinateTransform(crsSrc, crsDest, QgsProject.instance())
        # trim the boundaries using the maximum extent for all features
        box = []
        for f in shape_layer.getFeatures():
            g = f.geometry()
            g.transform(xform)
            f.setGeometry(g)
            if box:
                box.combineExtentWith(f.geometry().boundingBox())
            else:
                box = f.geometry().boundingBox()
        # intersect with the rater file extent
        box = box.intersect(stack_layer.extent())
        # trim
        gdal.Translate(stack_file_trimmed, stack_file, projWin=[box.xMinimum(), box.yMaximum(), box.xMaximum(), box.yMinimum()])

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

        cmd = ['gdal_calc' if platform.system() == 'Windows' else 'gdal_calc.py', '--quiet', '--overwrite',
               '--calc "A*(B>0)+255*logical_or(B==0,A==0)"', '-A "{}"'.format(img_to_mask), '-B "{}"'.format(band_from_mask),
               '--outfile "{}"'.format(img_to_mask)]
        call(" ".join(cmd), shell=True)

        # unset nodata
        cmd = ['gdal_edit' if platform.system() == 'Windows' else 'gdal_edit.py', '"{}"'.format(img_to_mask), '-unsetnodata']
        call(" ".join(cmd), shell=True)

    def do_fmask(self, filters_enabled, min_cloud_size=0, cloud_prob_thresh=0.225, cloud_buffer_size=4,
                 shadow_buffer_size=6, cirrus_prob_ratio=0.04, nir_fill_thresh=0.02, swir2_thresh=0.03,
                 whiteness_thresh=0.7, swir2_water_test=0.03, nir_snow_thresh=0.11, green_snow_thresh=0.1):

        ########################################
        # reflective bands stack

        # tmp file for reflective bands stack
        self.reflective_stack_file = os.path.join(self.tmp_dir, "reflective_stack.tif")

        if not os.path.isfile(self.reflective_stack_file):
            update_process_bar(self.process_bar, 10, self.process_status,
                               self.tr("Making reflective bands stack..."))

            gdal_merge.main(["", "-separate", "-of", "GTiff", "-o",
                             self.reflective_stack_file] + self.reflective_bands)

        ########################################
        # thermal bands stack

        # tmp file for reflective bands stack
        self.thermal_stack_file = os.path.join(self.tmp_dir, "thermal_stack.tif")

        if not os.path.isfile(self.thermal_stack_file):
            update_process_bar(self.process_bar, 20, self.process_status,
                               self.tr("Making thermal bands stack..."))

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
                           self.tr("Making fmask angles file..."))

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
                           self.tr("Making saturation mask file..."))

        if self.landsat_version == 4:
            sensor = config.FMASK_LANDSAT47
        elif self.landsat_version == 5:
            sensor = config.FMASK_LANDSAT47
        elif self.landsat_version == 7:
            sensor = config.FMASK_LANDSAT47
        elif self.landsat_version in [8, 9]:
            sensor = config.FMASK_LANDSATOLI

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
                           self.tr("Making top of Atmosphere ref..."))

        landsatTOA.makeTOAReflectance(self.reflective_stack_for_process, self.mtl_path,
                                      self.angles_file, self.toa_file)

        ########################################
        # cloud mask
        #
        # fmask_usgsLandsatStacked.py

        # tmp file for cloud
        self.cloud_fmask_file = os.path.join(self.tmp_dir, "cloud_fmask_{}.tif".format(datetime.now().strftime('%H%M%S')))

        update_process_bar(self.process_bar, 70, self.process_status,
                           self.tr("Making cloud mask with fmask..."))

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
        elif self.landsat_version in [8, 9]:
            sensor = config.FMASK_LANDSATOLI

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
                           self.tr("DONE"))

    def do_blue_band(self, bb_threshold):
        # tmp file for cloud
        self.cloud_bb_file = os.path.join(self.tmp_dir, "cloud_bb_{}.tif".format(datetime.now().strftime('%H%M%S')))
        update_process_bar(self.process_bar, 50, self.process_status,
                           self.tr("Making the blue band filter..."))

        ########################################
        # select the Blue Band
        if self.landsat_version in [4, 5, 7]:
            # get the reflective file names bands
            self.blue_band_file = os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_1'])
            # fix file name
            self.blue_band_file = get_prefer_name(self.blue_band_file)
            if not os.path.exists(self.blue_band_file):
                self.blue_band_file = os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_SR_1'])
        if self.landsat_version in [8, 9]:
            # get the reflective file names bands
            self.blue_band_file = os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_2'])
            # fix file name
            self.blue_band_file = get_prefer_name(self.blue_band_file)
            if not os.path.exists(self.blue_band_file):
                self.blue_band_file = os.path.join(self.input_dir, self.mtl_file['FILE_NAME_BAND_SR_2'])

        ########################################
        # clipping the Blue Band (only if is activated selected area or shape area)
        self.blue_band_clip_file = os.path.join(self.tmp_dir, "blue_band_clip.tif")
        self.blue_band_for_process = self.clip(self.blue_band_file, self.blue_band_clip_file)

        ########################################
        # do blue band filter
        cmd = ['gdal_calc' if platform.system() == 'Windows' else 'gdal_calc.py', '--quiet', '--overwrite',
               '--calc "1*(A<{threshold})+6*(A>={threshold})"'.format(threshold=bb_threshold),
               '-A "{}"'.format(self.blue_band_for_process), '--outfile "{}"'.format(self.cloud_bb_file),
               '--type="Byte"', '--co COMPRESS=PACKBITS']
        call(" ".join(cmd), shell=True)

        # save final result of masking
        self.cloud_masking_files.append(self.cloud_bb_file)

        ### ending process
        update_process_bar(self.process_bar, 100, self.process_status,
                           self.tr("DONE"))

    def do_cloud_qa_l457(self, cloud_qa_file, checked_items, specific_values=[]):
        # tmp file for cloud
        self.cloud_qa = os.path.join(self.tmp_dir, "cloud_qa_{}.tif".format(datetime.now().strftime('%H%M%S')))
        update_process_bar(self.process_bar, 50, self.process_status,
                           self.tr("Making the Cloud QA filter..."))

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
        gdal_calc.Calc(calc="1*(numpy.all([{nfv}], axis=0)) + 7*(numpy.any([{fv}], axis=0))".format(fv=filter_values,
                                                                                                    nfv=not_filter_values),
                       A=self.cloud_qa_for_process, outfile=self.cloud_qa, type="Byte", NoDataValue=1)
        # unset the nodata, leave the 1 (valid fields)
        cmd = ['gdal_edit' if platform.system() == 'Windows' else 'gdal_edit.py', '"{}"'.format(self.cloud_qa), '-unsetnodata']
        call(" ".join(cmd), shell=True)

        # save final result of masking
        self.cloud_masking_files.append(self.cloud_qa)

        ### ending process
        update_process_bar(self.process_bar, 100, self.process_status,
                           self.tr("DONE"))

    def do_aerosol_l89(self, aerosol_file, checked_items, specific_values=[]):
        # tmp file for cloud
        self.aerosol = os.path.join(self.tmp_dir, "aerosol_{}.tif".format(datetime.now().strftime('%H%M%S')))
        update_process_bar(self.process_bar, 50, self.process_status,
                           self.tr("Making the Aerosol filter..."))

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
        gdal_calc.Calc(calc="1*(numpy.all([{nfv}], axis=0)) + 8*(numpy.any([{fv}], axis=0))".format(fv=filter_values, nfv=not_filter_values),
                       A=self.aerosol_for_process, outfile=self.aerosol, type="Byte", NoDataValue=1)

        # unset nodata
        cmd = ['gdal_edit' if platform.system() == 'Windows' else 'gdal_edit.py',
               '"{}"'.format(self.aerosol), '-unsetnodata']
        call(" ".join(cmd), shell=True)

        # save final result of masking
        self.cloud_masking_files.append(self.aerosol)

        ### ending process
        update_process_bar(self.process_bar, 100, self.process_status,
                           self.tr("DONE"))

    def do_pixel_qa(self, pixel_qa_file, checked_items, specific_values=[]):
        """
        http://landsat.usgs.gov/qualityband.php
        """
        # tmp file for Pixel QA
        self.pixel_qa = os.path.join(self.tmp_dir, "pixel_qa_{}.tif".format(datetime.now().strftime('%H%M%S')))
        update_process_bar(self.process_bar, 50, self.process_status,
                           self.tr("Making the Pixel QA filter..."))

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
        if self.landsat_version in [8, 9]:
            static_bits = [0, 1, 11, 12, 13, 14, 15]

        # generate the values combinations for one bit items selected
        pixel_qa_items_1b = {"Water (bit 2)": [2], "Cloud Shadow (bit 3)": [3],
                             "Snow (bit 4)": [4], "Cloud (bit 5)": [5]}
        if self.landsat_version in [8, 9]:  # add to L89
            pixel_qa_items_1b["Terrain Occlusion (bit 10)"] = [10]

        for item, bits in pixel_qa_items_1b.items():
            binary = [0]*16
            if checked_items[item]:
                binary[(len(binary) - 1) - bits[0]] = 1
                values_combinations += list(binary_combination(binary, static_bits + bits))

        # generate the values combinations for two bits items selected
        if self.landsat_version in [4, 5, 7]:
            pixel_qa_items_2b = {"Cloud Confidence (bits 6-7)": [6, 7]}
        if self.landsat_version in [8, 9]:
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
        gdal_calc.Calc(calc="1*(numpy.all([{nfv}], axis=0)) + 9*(numpy.any([{fv}], axis=0))".format(fv=filter_values, nfv=not_filter_values),
                       A=self.pixel_qa_for_process, outfile=self.pixel_qa, type="Byte", NoDataValue=1)

        # unset nodata
        cmd = ['gdal_edit' if platform.system() == 'Windows' else 'gdal_edit.py',
               '"{}"'.format(self.pixel_qa), '-unsetnodata']
        call(" ".join(cmd), shell=True)

        # save final result of masking
        self.cloud_masking_files.append(self.pixel_qa)

        ### ending process
        update_process_bar(self.process_bar, 100, self.process_status,
                           self.tr("DONE"))

    def do_qaband_c1_l457(self, qabandc1_file, checked_items, specific_values=[]):
        """
        http://landsat.usgs.gov/qualityband.php
        """
        # tmp file for QA Band
        self.qaband = os.path.join(self.tmp_dir, "qaband_c1{}.tif".format(datetime.now().strftime('%H%M%S')))
        update_process_bar(self.process_bar, 50, self.process_status,
                           self.tr("Making the QA Band filter..."))

        ########################################
        # clipping the QA Mask (only if is activated selected area or shape area)
        self.qaband_clip_file = os.path.join(self.tmp_dir, "qaband_clip.tif")
        self.qaband_for_process = self.clip(qabandc1_file, self.qaband_clip_file)

        ########################################
        # convert selected items to binary and decimal values
        values_combinations = []
        # bits not used or not fill
        static_bits = [0, 11, 12, 13, 14, 15]

        # generate the values combinations for one bit items selected
        qaband_items_1b = {"Dropped Pixel (bit 1)": [1], "Cloud (bit 4)": [4]}

        for item, bits in qaband_items_1b.items():
            binary = [0] * 16
            if checked_items[item]:
                binary[(len(binary) - 1) - bits[0]] = 1
                values_combinations += list(binary_combination(binary, static_bits + bits))

        # generate the values combinations for two bits items selected
        qaband_items_2b = {"Radiometric Saturation (bits 2-3)": [2, 3]}
        levels = {"No bands saturated": [0, 0], "1 to 2 bands saturated": [0, 1],
                  "3 to 4 bands saturated": [1, 0], "> 4 bands saturated": [1, 1]}
        for item, bits in qaband_items_2b.items():
            if item in checked_items.keys():
                for level in checked_items[item]:
                    binary = [0] * 16
                    binary[bits[0]:bits[1] + 1] = (levels[level])[::-1]
                    binary.reverse()
                    values_combinations += list(binary_combination(binary, static_bits + bits))

        # generate the values combinations for two bits items selected
        qaband_items_2b = {"Cloud Confidence (bits 5-6)": [5, 6],
                           "Cloud Shadow (bits 7-8)": [7, 8], "Snow/Ice (bits 9-10)": [9, 10]}
        levels = {"0% None": [0, 0], "0-33% Low": [0, 1],
                  "34-66% Medium": [1, 0], "67-100% High": [1, 1]}
        for item, bits in qaband_items_2b.items():
            if item in checked_items.keys():
                for level in checked_items[item]:
                    binary = [0] * 16
                    binary[bits[0]:bits[1] + 1] = (levels[level])[::-1]
                    binary.reverse()
                    values_combinations += list(binary_combination(binary, static_bits + bits))

        # add the specific values
        if specific_values:
            values_combinations += specific_values

        # delete duplicates
        values_combinations = list(set(values_combinations))

        # only left the values inside the image
        values_combinations = check_values_in_image(self.qaband_for_process, values_combinations)

        filter_values = ",".join(["A==" + str(x) for x in values_combinations])
        not_filter_values = ",".join(["A!=" + str(x) for x in values_combinations])

        ########################################
        # do QA Mask filter
        tmp_pqa_file = os.path.join(self.tmp_dir, "qaband.tif")
        gdal_calc.Calc(calc="1*(numpy.all([{nfv}], axis=0)) + 10*(numpy.any([{fv}], axis=0))".format(fv=filter_values,
                                                                                                    nfv=not_filter_values),
                       A=self.qaband_for_process, outfile=tmp_pqa_file, type="Byte", NoDataValue=1)
        # unset the nodata, leave the 1 (valid fields)
        gdal.Translate(self.qaband, tmp_pqa_file, noData="none")
        # delete tmp files
        os.remove(tmp_pqa_file)

        # save final result of masking
        self.cloud_masking_files.append(self.qaband)

        ### ending process
        update_process_bar(self.process_bar, 100, self.process_status,
                           self.tr("DONE"))

    def do_qaband_c1_l89(self, qabandc1_file, checked_items, specific_values=[]):
        """
        http://landsat.usgs.gov/qualityband.php
        """
        # tmp file for QA Band
        self.qaband = os.path.join(self.tmp_dir, "qaband_c1{}.tif".format(datetime.now().strftime('%H%M%S')))
        update_process_bar(self.process_bar, 50, self.process_status,
                           self.tr("Making the QA Band filter..."))

        ########################################
        # clipping the QA Mask (only if is activated selected area or shape area)
        self.qaband_clip_file = os.path.join(self.tmp_dir, "qaband_clip.tif")
        self.qaband_for_process = self.clip(qabandc1_file, self.qaband_clip_file)

        ########################################
        # convert selected items to binary and decimal values
        values_combinations = []
        # bits not used or not fill
        static_bits = [0, 13, 14, 15]

        # generate the values combinations for one bit items selected
        qaband_items_1b = {"Terrain Occlusion (bit 1)": [1], "Cloud (bit 4)": [4]}

        for item, bits in qaband_items_1b.items():
            binary = [0] * 16
            if checked_items[item]:
                binary[(len(binary) - 1) - bits[0]] = 1
                values_combinations += list(binary_combination(binary, static_bits + bits))

        # generate the values combinations for two bits items selected
        qaband_items_2b = {"Radiometric Saturation (bits 2-3)": [2, 3]}
        levels = {"No bands saturated": [0, 0], "1 to 2 bands saturated": [0, 1],
                  "3 to 4 bands saturated": [1, 0], "> 4 bands saturated": [1, 1]}
        for item, bits in qaband_items_2b.items():
            if item in checked_items.keys():
                for level in checked_items[item]:
                    binary = [0] * 16
                    binary[bits[0]:bits[1] + 1] = (levels[level])[::-1]
                    binary.reverse()
                    values_combinations += list(binary_combination(binary, static_bits + bits))

        # generate the values combinations for two bits items selected
        qaband_items_2b = {"Cloud Confidence (bits 5-6)": [5, 6], "Cloud Shadow (bits 7-8)": [7, 8],
                           "Snow/Ice (bits 9-10)": [9, 10], "Cirrus Confidence (bits 11-12)": [11, 12]}
        levels = {"0% None": [0, 0], "0-33% Low": [0, 1],
                  "34-66% Medium": [1, 0], "67-100% High": [1, 1]}
        for item, bits in qaband_items_2b.items():
            if item in checked_items.keys():
                for level in checked_items[item]:
                    binary = [0] * 16
                    binary[bits[0]:bits[1] + 1] = (levels[level])[::-1]
                    binary.reverse()
                    values_combinations += list(binary_combination(binary, static_bits + bits))

        # add the specific values
        if specific_values:
            values_combinations += specific_values

        # delete duplicates
        values_combinations = list(set(values_combinations))

        # only left the values inside the image
        values_combinations = check_values_in_image(self.qaband_for_process, values_combinations)

        filter_values = ",".join(["A==" + str(x) for x in values_combinations])
        not_filter_values = ",".join(["A!=" + str(x) for x in values_combinations])

        ########################################
        # do QA Mask filter
        tmp_pqa_file = os.path.join(self.tmp_dir, "qaband.tif")
        gdal_calc.Calc(calc="1*(numpy.all([{nfv}], axis=0)) + 10*(numpy.any([{fv}], axis=0))".format(fv=filter_values,
                                                                                                    nfv=not_filter_values),
                       A=self.qaband_for_process, outfile=tmp_pqa_file, type="Byte", NoDataValue=1)
        # unset the nodata, leave the 1 (valid fields)
        gdal.Translate(self.qaband, tmp_pqa_file, noData="none")
        # delete tmp files
        os.remove(tmp_pqa_file)

        # save final result of masking
        self.cloud_masking_files.append(self.qaband)

        ### ending process
        update_process_bar(self.process_bar, 100, self.process_status,
                           self.tr("DONE"))

    def do_qaband_c2(self, qabandc2_file, checked_items, specific_values=[]):
        """
        http://landsat.usgs.gov/qualityband.php
        """
        # tmp file for QA Band
        self.qaband = os.path.join(self.tmp_dir, "qaband_c2{}.tif".format(datetime.now().strftime('%H%M%S')))
        update_process_bar(self.process_bar, 50, self.process_status,
                           self.tr("Making the QA Band filter..."))

        ########################################
        # clipping the QA Mask (only if is activated selected area or shape area)
        self.qaband_clip_file = os.path.join(self.tmp_dir, "qaband_clip.tif")
        self.qaband_for_process = self.clip(qabandc2_file, self.qaband_clip_file)

        ########################################
        # convert selected items to binary and decimal values
        values_combinations = []
        # bits not used or not fill
        static_bits = [0, 6]

        # generate the values combinations for one bit items selected
        qaband_items_1b = {"Dilated Cloud (bit 1)": [1], "Cirrus (bit 2)": [2], "Cloud (bit 3)": [3],
                           "Cloud Shadow (bit 4)": [4], "Snow (bit 5)": [5], "Water (bit 7)": [7]}

        for item, bits in qaband_items_1b.items():
            binary = [0]*16
            if checked_items[item]:
                binary[(len(binary) - 1) - bits[0]] = 1
                values_combinations += list(binary_combination(binary, static_bits + bits))

        # generate the values combinations for two bits items selected
        qaband_items_2b = {"Cloud Confidence (bits 8-9)": [8, 9]}
        levels = {"Low": [0, 1], "Medium": [1, 0], "High": [1, 1]}
        for item, bits in qaband_items_2b.items():
            if item in checked_items.keys():
                for level in checked_items[item]:
                    binary = [0] * 16
                    binary[bits[0]:bits[1]+1] = (levels[level])[::-1]
                    binary.reverse()
                    values_combinations += list(binary_combination(binary, static_bits + bits))

        # generate the values combinations for two bits items selected
        qaband_items_2b = {"Cloud Shadow Confidence (bits 10-11)": [10, 11], "Snow/Ice Confidence (bits 12-13)": [12, 13], "Cirrus Confidence (bits 14-15)": [14, 15]}
        levels = {"Low": [0, 1], "High": [1, 1]}
        for item, bits in qaband_items_2b.items():
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
        values_combinations = check_values_in_image(self.qaband_for_process, values_combinations)

        filter_values = ",".join(["A==" + str(x) for x in values_combinations])
        not_filter_values = ",".join(["A!=" + str(x) for x in values_combinations])

        ########################################
        # do QA Mask filter
        tmp_pqa_file = os.path.join(self.tmp_dir, "qaband.tif")
        gdal_calc.Calc(calc="1*(numpy.all([{nfv}], axis=0)) + 10*(numpy.any([{fv}], axis=0))".format(fv=filter_values, nfv=not_filter_values),
                       A=self.qaband_for_process, outfile=tmp_pqa_file, type="Byte", NoDataValue=1)
        # unset the nodata, leave the 1 (valid fields)
        gdal.Translate(self.qaband, tmp_pqa_file, noData="none")
        # delete tmp files
        os.remove(tmp_pqa_file)

        # save final result of masking
        self.cloud_masking_files.append(self.qaband)

        ### ending process
        update_process_bar(self.process_bar, 100, self.process_status,
                           self.tr("DONE"))
