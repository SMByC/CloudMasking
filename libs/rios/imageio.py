"""
The only things of value left in this module are the original definitions of
UNION, INTERSECTION and BOUNDS_FROM_REFERENCE.

There are also two functions wld2pix and pix2wld, and the Coord class they use.
These should also be deprecated, in favour of GDAL's ApplyGeoTransform
and InvGeoTransform (which they now use internally anyway).
However, they are used in public-facing ways in the ReaderInfo object,
so removing them would, in principle, be a breaking change.
They are harmless enough, so they have been left here.

In general, this module should be ignored.

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

from osgeo import gdal
from osgeo import gdal_array

from .rioserrors import deprecationWarning

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


# WARNING
# WARNING
# WARNING
# WARNING
# WARNING       All code below this point is deprecated (v2.0.0)
# WARNING
# WARNING
# WARNING
# WARNING


def GDALTypeToNumpyType(gdaltype):
    """
    This function is deprecated.
    Use gdal_array.GDALTypeCodeToNumericTypeCode instead.

    Given a gdal data type returns the matching numpy data type
    """
    deprecationWarning("Future versions of RIOS may remove this function. " +
        "Use gdal_array.GDALTypeCodeToNumericTypeCode instead")
    return gdal_array.GDALTypeCodeToNumericTypeCode(gdaltype)


def NumpyTypeToGDALType(numpytype):
    """
    This function is deprecated.
    Use gdal_array.NumericTypeCodeToGDALTypeCode instead.

    For a given numpy data type returns the matching GDAL data type
    """
    deprecationWarning("Future versions of RIOS may remove this function. " +
        "Use gdal_array.NumericTypeCodeToGDALTypeCode instead")
    return gdal_array.NumericTypeCodeToGDALTypeCode(numpytype)
