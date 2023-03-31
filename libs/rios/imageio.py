#!/usr/bin/env python

"""
This file contains definitions that are
common to all the image reading and 
writing modules
"""
# This file is part of RIOS - Raster I/O Simplification
# Copyright (C) 2012  Sam Gillingham, Neil Flood
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import numpy
from osgeo import gdalconst
from osgeo import gdal

from . import rioserrors

INTERSECTION = 0
UNION = 1
BOUNDS_FROM_REFERENCE = 2       # Bounds of working region are taken from given reference grid


class Coord:
    """a simple class that contains one coord"""
    def __init__(self, x, y):
        self.x = x
        self.y = y


def wld2pix(transform, geox, geoy):
    """converts a set of map coords to pixel coords"""
    inv_transform = gdal.InvGeoTransform(transform)
    x, y = gdal.ApplyGeoTransform(inv_transform, geox, geoy)
    return Coord(x, y)


def pix2wld(transform, x, y):
    """converts a set of pixels coords to map coords"""
    geox, geoy = gdal.ApplyGeoTransform(transform, x, y)
    return Coord(geox, geoy)


# Mappings between numpy datatypes and GDAL datatypes.
# Note that ambiguities are resolved by the order - the first one found 
# is the one chosen. 
dataTypeMapping = [
    (numpy.uint8, gdalconst.GDT_Byte),
    (bool, gdalconst.GDT_Byte),
    (numpy.int16, gdalconst.GDT_Int16),
    (numpy.uint16, gdalconst.GDT_UInt16),
    (numpy.int32, gdalconst.GDT_Int32),
    (numpy.uint32, gdalconst.GDT_UInt32),
    (numpy.float32, gdalconst.GDT_Float32),
    (numpy.float64, gdalconst.GDT_Float64)
]

# hack for GDAL 3.5 and later which suppport 64 bit ints
if hasattr(gdalconst, 'GDT_Int64'):
    dataTypeMapping.append((numpy.int64, gdalconst.GDT_Int64))
    dataTypeMapping.append((numpy.uint64, gdalconst.GDT_UInt64))

# With GDAL 3.7, there is a plan to introduce GDT_Int8, so try to cope with it.
# Hopefully OK, because we did not previously have anything to cope with arrays
# of type numpy.int8.
if hasattr(gdalconst, 'GDT_Int8'):
    dataTypeMapping.append((numpy.int8, gdalconst.GDT_Int8))


def GDALTypeToNumpyType(gdaltype):
    """
    Given a gdal data type returns the matching
    numpy data type
    """
    for (numpy_type, test_gdal_type) in dataTypeMapping:
        if test_gdal_type == gdaltype:
            return numpy_type
    raise rioserrors.TypeConversionError("Unknown GDAL datatype: %s"%gdaltype)


def NumpyTypeToGDALType(numpytype):
    """
    For a given numpy data type returns the matching
    GDAL data type
    """
    for (test_numpy_type, gdaltype) in dataTypeMapping:
        if test_numpy_type == numpytype:
            return gdaltype
    raise rioserrors.TypeConversionError("Unknown numpy datatype: %s"%numpytype)
