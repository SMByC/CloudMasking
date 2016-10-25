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

 This script was based and adapted from:
 https://github.com/OpenDataAnalytics/gaia/blob/master/gaia/geo/gdal_functions.py
 https://pcjericks.github.io/py-gdalogr-cookbook
"""

import re
import string
import os
import gdalconst
import numpy
import gdal
try:
    import gdalnumeric
except ImportError:
    from osgeo import gdalnumeric
import osr
from osgeo.gdal_array import BandReadAsArray, BandWriteArray


# Python bindings do not raise exceptions unless you
# explicitly call UseExceptions()
gdal.UseExceptions()
gdal.PushErrorHandler('CPLQuietErrorHandler')

#: Map of raster data types to max values
ndv_lookup = {
    'Byte': 255,
    'UInt16': 65535,
    'Int16': -32767,
    'UInt32': 4294967293,
    'Int32': -2147483647,
    'Float32': 1.175494351E-38,
    'Float64': 1.7976931348623158E+308
}


def gdal_reproject(src, dst,
                   epsg=3857,
                   error_threshold=0.125,
                   resampling=gdal.GRA_NearestNeighbour):
    """
    Reproject a raster image

    :param src: The source image
    :param dst: The filepath/name of the output image
    :param epsg: The EPSG code to reproject to
    :param error_threshold: Default is 0.125 (same as gdalwarp commandline)
    :param resampling: Default method is Nearest Neighbor
    """
    # Open source dataset
    src_ds = get_dataset(src)

    # Define target SRS
    dst_srs = osr.SpatialReference()
    dst_srs.ImportFromEPSG(int(epsg))
    dst_wkt = dst_srs.ExportToWkt()

    # Resampling might be passed as a string
    if not isinstance(resampling, int):
        resampling = getattr(gdal, resampling)

    # Call AutoCreateWarpedVRT() to fetch default values
    # for target raster dimensions and geotransform
    reprojected_ds = gdal.AutoCreateWarpedVRT(src_ds,
                                              None,
                                              dst_wkt,
                                              resampling,
                                              error_threshold)

    # Create the final warped raster
    if dst:
        gdal.GetDriverByName('GTiff').CreateCopy(dst, reprojected_ds)
    return reprojected_ds


def gdal_resize(raster, dimensions, projection, transform):
    """
    Transform a dataset to the specified dimensions and projection/bounds

    :param dataset: Dataset to be resized
    :param dimensions: dimensions to resize to (X, Y)
    :param projection: Projection of of resized dataset
    :param transform: Geotransform of resized dataset
    :return: Resized dataset
    """
    dataset = get_dataset(raster)
    datatype = dataset.GetRasterBand(1).DataType
    resized_ds = gdal.GetDriverByName('MEM').Create(
        '', dimensions[0], dimensions[1],  dataset.RasterCount, datatype)
    for i in range(1, resized_ds.RasterCount+1):
        nodatavalue = dataset.GetRasterBand(i).GetNoDataValue()
        resized_band = resized_ds.GetRasterBand(i)
        resized_arr = resized_band.ReadAsArray()
        resized_arr[resized_arr == 0] = nodatavalue
        resized_band.WriteArray(resized_arr)
        resized_band.SetNoDataValue(nodatavalue)

    resized_ds.SetGeoTransform(transform)
    resized_ds.SetProjection(projection)

    gdal.ReprojectImage(dataset, resized_ds)
    return resized_ds


def main(calculation, raster_output, rasters,
              bands=None, nodata=None, allBands=False, output_type=None):
    """
    Adopted from GDAL 1.10 gdal_calc.py script.

    :param calculation: equation to calculate, such as A + (B / 2)
    :param raster_output: Raster file to save output as
    :param rasters: array of rasters, should equal # of letters in calculation
    :param bands: array of band numbers, one for each raster in rasters array
    :param nodata: NoDataValue to use in output raster
    :param allBands: use all bands of specified raster by index
    :param output_type: data type for output raster ('Float32', 'Uint16', etc)
    :return: gdal Dataset
    """

    calculation = re.sub(r'(logical_|bitwise_)', r'numpy.\1', calculation)

    # set up some lists to store data for each band
    datasets = [get_dataset(raster) for raster in rasters]
    if not bands:
        bands = [1 for raster in rasters]
    datatypes = []
    datatype_nums = []
    nodata_vals = []
    dimensions = None
    alpha_list = string.ascii_uppercase[:len(rasters)]

    # loop through input files - checking dimensions
    for i, (raster, alpha, band) in enumerate(zip(datasets, alpha_list, bands)):
        raster_band = raster.GetRasterBand(band)
        datatypes.append(gdal.GetDataTypeName(raster_band.DataType))
        datatype_nums.append(raster_band.DataType)
        nodata_vals.append(raster_band.GetNoDataValue())
        # check that the dimensions of each layer are the same as the first
        if dimensions:
            if dimensions != [datasets[i].RasterXSize, datasets[i].RasterYSize]:
                datasets[i] = gdal_resize(raster,
                                          dimensions,
                                          datasets[0].GetProjection(),
                                          datasets[0].GetGeoTransform())
        else:
            dimensions = [datasets[0].RasterXSize, datasets[0].RasterYSize]

    # process allBands option
    allbandsindex = 0
    allbandscount = 1
    if allBands:
        allbandscount = datasets[allbandsindex].RasterCount
        if allbandscount <= 1:
            allbandsindex = None

    ################################################################
    # set up output file
    ################################################################

    # open output file exists
    # remove existing file and regenerate
    if os.path.isfile(raster_output):
        os.remove(raster_output)

    # find data type to use
    if not output_type:
        # use the largest type of the input files
        output_type = gdal.GetDataTypeName(max(datatype_nums))

    # create file
    output_driver = gdal.GetDriverByName('MEM')
    output_dataset = output_driver.Create(
        '', dimensions[0], dimensions[1], allbandscount,
        gdal.GetDataTypeByName(output_type))

    # set output geo info based on first input layer
    output_dataset.SetGeoTransform(datasets[0].GetGeoTransform())
    output_dataset.SetProjection(datasets[0].GetProjection())

    if nodata is None:
        nodata = ndv_lookup[output_type]

    for i in range(1, allbandscount+1):
        output_band = output_dataset.GetRasterBand(i)
        output_band.SetNoDataValue(nodata)
        # write to band
        output_band = None

    ################################################################
    # find block size to chop grids into bite-sized chunks
    ################################################################

    # use the block size of the first layer to read efficiently
    block_size = datasets[0].GetRasterBand(bands[0]).GetBlockSize()
    # store these numbers in variables that may change later
    n_x_valid = block_size[0]
    n_y_valid = block_size[1]
    # find total x and y blocks to be read
    n_x_blocks = int((dimensions[0] + block_size[0] - 1) / block_size[0])
    n_y_blocks = int((dimensions[1] + block_size[1] - 1) / block_size[1])
    buffer_size = block_size[0]*block_size[1]

    ################################################################
    # start looping through each band in allbandscount
    ################################################################
    for band_num in range(1, allbandscount+1):

        ################################################################
        # start looping through blocks of data
        ################################################################
        # loop through X-lines
        for x in range(0, n_x_blocks):
            # in the rare (impossible?) case that the blocks don't fit perfectly
            # change the block size of the final piece
            if x == n_x_blocks-1:
                n_x_valid = dimensions[0] - x * block_size[0]
                buffer_size = n_x_valid*n_y_valid

            # find X offset
            x_offset = x*block_size[0]

            # reset buffer size for start of Y loop
            n_y_valid = block_size[1]
            buffer_size = n_x_valid*n_y_valid

            # loop through Y lines
            for y in range(0, n_y_blocks):
                # change the block size of the final piece
                if y == n_y_blocks-1:
                    n_y_valid = dimensions[1] - y * block_size[1]
                    buffer_size = n_x_valid*n_y_valid

                # find Y offset
                y_offset = y*block_size[1]

                # create empty buffer to mark where nodata occurs
                nodatavalues = numpy.zeros(buffer_size)
                nodatavalues.shape = (n_y_valid, n_x_valid)

                # fetch data for each input layer
                for i, alpha in enumerate(alpha_list):

                    # populate lettered arrays with values
                    if allbandsindex is not None and allbandsindex == i:
                        this_band = band_num
                    else:
                        this_band = bands[i]
                    band_vals = BandReadAsArray(
                        datasets[i].GetRasterBand(this_band),
                        xoff=x_offset,
                        yoff=y_offset,
                        win_xsize=n_x_valid,
                        win_ysize=n_y_valid)

                    # fill in nodata values
                    nodatavalues = 1*numpy.logical_or(
                        nodatavalues == 1, band_vals == nodata_vals[i])

                    # create an array of values for this block
                    exec("%s=band_vals" % alpha)
                    band_vals = None

                # try the calculation on the array blocks
                try:
                    calc_result = eval(calculation)
                except Exception as e:
                    raise e

                # propogate nodata values
                # (set nodata cells to 0 then add nodata value to these cells)
                calc_result = ((1 * (nodatavalues == 0)) * calc_result) + \
                              (nodata * nodatavalues)

                # write data block to the output file
                output_band = output_dataset.GetRasterBand(band_num)
                BandWriteArray(output_band, calc_result,
                               xoff=x_offset, yoff=y_offset)

    if raster_output:
        output_driver = gdal.GetDriverByName('GTiff')
        outfile = output_driver.CreateCopy(raster_output, output_dataset, False)
    return output_dataset


def get_dataset(object):
    """
    Given an object, try returning a GDAL Dataset

    :param object: GDAL Dataset or file path to raster image
    :return: GDAL Dataset
    """
    if type(object).__name__ == 'Dataset':
        return object
    else:
        return gdal.Open(object, gdalconst.GA_ReadOnly)
