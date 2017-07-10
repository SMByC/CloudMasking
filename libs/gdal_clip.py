# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Cloud Filters
                                 A QGIS plugin
 Cloud masking for landsat products using different process suck as fmask
                             -------------------
        copyright            : (C) 2016-2017 by Xavier Corredor Llano, SMBYC
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

 This script was based and adapted from:
 https://github.com/OpenDataAnalytics/gaia/blob/master/gaia/geo/gdal_functions.py
 https://pcjericks.github.io/py-gdalogr-cookbook
"""

from osgeo import gdal, gdalnumeric, gdalconst

# Python bindings do not raise exceptions unless you
# explicitly call UseExceptions()
gdal.UseExceptions()
gdal.PushErrorHandler('CPLQuietErrorHandler')


def main(raster_input, raster_output, extent, nodata=0):
    """
    This function will subset a raster by a vector polygon.
    Adapted from the GDAL/OGR Python Cookbook at
    https://pcjericks.github.io/py-gdalogr-cookbook

    :param raster_input: raster input filepath
    :param raster_output: raster output filepath
    :param polygon_json: polygon as geojson string
    :param nodata: nodata value for output raster file
    :return: GDAL Dataset
    """

    def world_to_pixel(geoMatrix, x, y):
        """
        Uses a gdal geomatrix (gdal.GetGeoTransform()) to calculate
        the pixel location of a geospatial coordinate
        """
        ulX = geoMatrix[0]
        ulY = geoMatrix[3]
        xDist = geoMatrix[1]
        pixel = int((x - ulX) / xDist)
        line = int((ulY - y) / xDist)
        return (pixel, line)

    src_image = get_dataset(raster_input)
    # Load the source data as a gdalnumeric array
    src_array = src_image.ReadAsArray()
    src_dtype = src_array.dtype

    # Also load as a gdal image to get geotransform
    # (world file) info
    geo_trans = src_image.GetGeoTransform()
    nodata_values = []
    for i in range(src_image.RasterCount):
        nodata_value = src_image.GetRasterBand(i+1).GetNoDataValue()
        if not nodata_value:
            nodata_value = nodata
        nodata_values.append(nodata_value)

    # Convert the layer extent to image pixel coordinates
    min_x, max_x, min_y, max_y = extent
    ul_x, ul_y = world_to_pixel(geo_trans, min_x, max_y)
    lr_x, lr_y = world_to_pixel(geo_trans, max_x, min_y)

    bands = src_image.RasterCount

    if bands > 1:
        clip = src_array[:, ul_y:lr_y, ul_x:lr_x]
    else:
        clip = src_array[ul_y:lr_y, ul_x:lr_x]

    # create pixel offset to pass to new image Projection info
    xoffset = ul_x
    yoffset = ul_y

    # Create a new geomatrix for the image
    geo_trans = list(geo_trans)
    geo_trans[0] = min_x
    geo_trans[3] = max_y

    # create output raster
    raster_band = src_image.GetRasterBand(1)
    output_driver = gdal.GetDriverByName('MEM')
    if bands > 1:
        output_dataset = output_driver.Create('', clip.shape[2], clip.shape[1],
                                              src_image.RasterCount, raster_band.DataType)
    else:
        output_dataset = output_driver.Create('', clip.shape[1], clip.shape[0],
                                              src_image.RasterCount, raster_band.DataType)
    output_dataset.SetGeoTransform(geo_trans)
    output_dataset.SetProjection(src_image.GetProjection())
    gdalnumeric.CopyDatasetInfo(src_image, output_dataset,
                                xoff=xoffset, yoff=yoffset)

    if bands > 1:
        for i in range(bands):
            outBand = output_dataset.GetRasterBand(i + 1)
            outBand.SetNoDataValue(nodata_values[i])
            outBand.WriteArray(clip[i])
    else:
        outBand = output_dataset.GetRasterBand(1)
        outBand.SetNoDataValue(nodata_values[0])
        outBand.WriteArray(clip)

    if raster_output:
        output_driver = gdal.GetDriverByName('GTiff')
        outfile = output_driver.CreateCopy(raster_output, output_dataset, False)
        outfile = None

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