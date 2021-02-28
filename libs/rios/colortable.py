"""
This module contains routines for dealing with large color 
tables. This module uses the Raster Attribute Table functions 
which are the fastest method to access the color table that
GDAL provides. 

The more general :mod:`rios.ratapplier` and :mod:`rios.ratapplier`  
modules can be used for reading and writing generic Raster 
Attribute Table Columns. 

The getRampNames() and genTable() functions access the built in
color ramps (mainly derived from https://colorbrewer2.org/ - see
this website for more information about the ramps and when to use
them).

The setTable()/getTable() functions write and read color tables
to file formats that support accessing color tables with the
Raster Attribute Table functions. 

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

import sys
import numpy
from osgeo import gdal

def loadBuiltinRamps():
    """
    This function simply loads the built in color ramps into
    a dictionary. 
    From http://colorbrewer.org/ and Python code generated 
    by TuiView's colorbrewer2py.py.
    
    """
    ramp = {}
    ramp['Blues'] = {'author' : 'Cynthia Brewer', 
        'comments' : 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 
        'type' : 'Sequential'}
    ramp['Blues']['description'] = {}
    ramp['Blues']['description']['red'] = '247 222 198 158 107 66 33 8 8'
    ramp['Blues']['description']['green'] = '251 235 219 202 174 146 113 81 48'
    ramp['Blues']['description']['blue'] = '255 247 239 225 214 198 181 156 107'
    ramp['Greys'] = {'author' : 'Cynthia Brewer', 
        'comments' : 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 
        'type' : 'Sequential'}
    ramp['Greys']['description'] = {}
    ramp['Greys']['description']['red'] = '255 240 217 189 150 115 82 37 0'
    ramp['Greys']['description']['green'] = '255 240 217 189 150 115 82 37 0'
    ramp['Greys']['description']['blue'] = '255 240 217 189 150 115 82 37 0'
    ramp['RdBu'] = {'author' : 'Cynthia Brewer', 
        'comments' : 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 
        'type' : 'Diverging'}
    ramp['RdBu']['description'] = {}
    ramp['RdBu']['description']['red'] = '103 178 214 244 253 247 209 146 67 33 5'
    ramp['RdBu']['description']['green'] = '0 24 96 165 219 247 229 197 147 102 48'
    ramp['RdBu']['description']['blue'] = '31 43 77 130 199 247 240 222 195 172 97'
    ramp['RdYlBu'] = {'author' : 'Cynthia Brewer', 
        'comments' : 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 
        'type' : 'Diverging'}
    ramp['RdYlBu']['description'] = {}
    ramp['RdYlBu']['description']['red'] = '165 215 244 253 254 255 224 171 116 69 49'
    ramp['RdYlBu']['description']['green'] = '0 48 109 174 224 255 243 217 173 117 54'
    ramp['RdYlBu']['description']['blue'] = '38 39 67 97 144 191 248 233 209 180 149'
    ramp['RdYlGn'] = {'author' : 'Cynthia Brewer', 
        'comments' : 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 
        'type' : 'Diverging'}
    ramp['RdYlGn']['description'] = {}
    ramp['RdYlGn']['description']['red'] = '165 215 244 253 254 255 217 166 102 26 0'
    ramp['RdYlGn']['description']['green'] = '0 48 109 174 224 255 239 217 189 152 104'
    ramp['RdYlGn']['description']['blue'] = '38 39 67 97 139 191 139 106 99 80 55'
    ramp['Reds'] = {'author' : 'Cynthia Brewer', 
        'comments' : 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 
        'type' : 'Sequential'}
    ramp['Reds']['description'] = {}
    ramp['Reds']['description']['red'] = '255 254 252 252 251 239 203 165 103'
    ramp['Reds']['description']['green'] = '245 224 187 146 106 59 24 15 0'
    ramp['Reds']['description']['blue'] = '240 210 161 114 74 44 29 21 13'
    ramp['Spectral'] = {'author' : 'Cynthia Brewer', 
        'comments' : 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 
        'type' : 'Diverging'}
    ramp['Spectral']['description'] = {}
    ramp['Spectral']['description']['red'] = '158 213 244 253 254 255 230 171 102 50 94'
    ramp['Spectral']['description']['green'] = '1 62 109 174 224 255 245 221 194 136 79'
    ramp['Spectral']['description']['blue'] = '66 79 67 97 139 191 152 164 165 189 162'
    ramp['YlGnBu'] = {'author' : 'Cynthia Brewer', 
        'comments' : 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 
        'type' : 'Sequential'}
    ramp['YlGnBu']['description'] = {}
    ramp['YlGnBu']['description']['red'] = '255 237 199 127 65 29 34 37 8'
    ramp['YlGnBu']['description']['green'] = '255 248 233 205 182 145 94 52 29'
    ramp['YlGnBu']['description']['blue'] = '217 177 180 187 196 192 168 148 88'
    ramp['YlOrRd'] = {'author' : 'Cynthia Brewer', 
        'comments' : 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 
        'type' : 'Sequential'}
    ramp['YlOrRd']['description'] = {}
    ramp['YlOrRd']['description']['red'] = '255 255 254 254 253 252 227 189 128'
    ramp['YlOrRd']['description']['green'] = '255 237 217 178 141 78 26 0 0'
    ramp['YlOrRd']['description']['blue'] = '204 160 118 76 60 42 28 38 38'
    # Viridis palettes
    ramp['viridis'] = {'author' : ' Stefan van der Walt and Nathaniel Smith', 'comments' : '', 
        'type' : 'Diverging'}
    ramp['viridis']['description'] = {}
    ramp['viridis']['description']['red'] = '68 72 67 56 45 37 30 43 81 133 194 253'
    ramp['viridis']['description']['green'] = '1 33 62 89 112 133 155 176 197 213 223 231'
    ramp['viridis']['description']['blue'] = '84 115 133 140 142 142 138 127 106 74 35 37'
    ramp['magma'] = {'author' : ' Stefan van der Walt and Nathaniel Smith', 'comments' : '', 
        'type' : 'Diverging'}
    ramp['magma']['description'] = {}
    ramp['magma']['description']['red'] = '0 18 51 90 125 163 200 233 249 254 254 252'
    ramp['magma']['description']['green'] = '0 13 16 22 36 48 62 85 124 168 211 253'
    ramp['magma']['description']['blue'] = '4 50 104 126 130 126 115 98 93 115 149 191'
    ramp['plasma'] = {'author' : ' Stefan van der Walt and Nathaniel Smith', 'comments' : '',
        'type' : 'Diverging'}
    ramp['plasma']['description'] = {}
    ramp['plasma']['description']['red'] = '13 62 99 135 166 192 213 231 245 253 252 240'
    ramp['plasma']['description']['green'] = '8 4 0 7 32 58 84 111 140 173 210 249'
    ramp['plasma']['description']['blue'] = '135 156 167 166 152 131 110 90 70 50 37 33'
    ramp['inferno'] = {'author' : ' Stefan van der Walt and Nathaniel Smith', 'comments' : '', 
        'type' : 'Diverging'}
    ramp['inferno']['description'] = {}
    ramp['inferno']['description']['red'] = '0 20 58 96 133 169 203 230 247 252 245 252'
    ramp['inferno']['description']['green'] = '0 11 9 19 33 46 65 93 131 173 219 255'
    ramp['inferno']['description']['blue'] = '4 53 99 110 107 94 73 47 17 18 75 164'
    ramp['cividis'] = {'author' : ' Stefan van der Walt and Nathaniel Smith', 'comments' : '', 
        'type' : 'Diverging'}
    ramp['cividis']['description'] = {}
    ramp['cividis']['description']['red'] = '0 0 42 72 94 114 135 158 182 208 234 255'
    ramp['cividis']['description']['green'] = '32 48 64 82 98 115 132 150 169 190 211 234'
    ramp['cividis']['description']['blue'] = '77 111 108 107 110 116 121 119 113 103 87 70'
    # Other tables 
    ramp['gray'] = {'type' : 'Sequential', 'description' : {}}
    ramp['gray']['description']['red'] = '0 255'
    ramp['gray']['description']['green'] = '0 255'
    ramp['gray']['description']['blue'] = '0 255'
    ramp['rainbow'] = {'type' : 'Sequential', 'description' : {}}
    ramp['rainbow']['description']['red'] = '255 0 0'
    ramp['rainbow']['description']['green'] = '0 255 0'
    ramp['rainbow']['description']['blue'] = '0 0 255'
    return ramp

# load ramps into our global var
RAMP = loadBuiltinRamps()
# Special name that isn't a ramp
RANDOM_NAME = 'RANDOM'

if sys.version_info[0] > 2:
    # hack for Python 3 which uses str instead of basestring
    # we just use basestring
    basestring = str

class ColorTableException(Exception):
    "Exception for errors related to color table access"

def getRampNames():
    """
    Get a list of names of the available color ramps
    """
    names = list(RAMP.keys())
    names.append(RANDOM_NAME)
    return names

def genTable(numEntries, colorType, ignoreVal=None):
    """
    Generate the named color table for use with setTable().
    
    colorType should be one of the names returned from 
    getTableNames(). 
    
    numEntries is the size of the table that is generated
    and should correspond to the range of data you have 
    in the output file.
    
    If ignoreVal is specified then the opacity for this
    row is set to 0 - ie totally transparent. Use this for
    preparing images for display so images underneath in a 
    viewer show through where the ignoreVal is set.

    The returned colour table is a numpy array, described in detail
    in the docstring for colortable.setTable(). 
    
    """
    # create an array to hold the table
    ct = numpy.empty((4, numEntries), dtype=numpy.uint8)
    if colorType == RANDOM_NAME:
        # just get some random data
        ct[:3] = numpy.random.randint(0, 255, size=(3, numEntries), 
                        dtype=numpy.uint8)
    else:
        if colorType not in RAMP:
            msg = 'Color ramp {} not found'.format(colorType)
            raise ColorTableException(msg)
    
        # interpolate the given coloramp over numEntries
        for idx, code in enumerate(('red', 'green', 'blue')):
    
            # get the data as string
            colstr = RAMP[colorType]['description'][code]
            # turn it into a list of floats
            # numpy.interp() needs floats
            colList = [float(x) for x in colstr.split()]
            # the x-values of the observations
            # evenly spaced 0-255 with len(colList) obs
            xobs = numpy.linspace(0, 255, len(colList))
            # create an array from our list
            yobs = numpy.array(colList)
            # values to interpolate at 0-255
            # same size as the lut
            xinterp = numpy.linspace(0, 255, numEntries)
            # do the interp
            yinterp = numpy.interp(xinterp, xobs, yobs)
            # put into color table
            ct[idx] = yinterp

    # alpha
    ct[3] = 255
    
    if ignoreVal is not None:
        # just set the whole row to 0 to be sure
        ct[:, int(ignoreVal)] = 0

    return ct

def getTable(imgFile, bandNumber=1):
    """
    Given either an open gdal dataset, or a filename,
    reads the color table as an array that can be passed
    to setColorTable().
    
    The returned colour table is a numpy array, described in detail
    in the docstring for colortable.setTable(). 
    
    """
    if isinstance(imgFile, basestring):
        ds = gdal.Open(str(imgFile))
    elif isinstance(imgFile, gdal.Dataset):
        ds = imgFile

    gdalBand = ds.GetRasterBand(bandNumber)
    attrTbl = gdalBand.GetDefaultRAT()
    
    numEntries = attrTbl.GetRowCount()
    ct = numpy.empty((4, numEntries), dtype=numpy.uint8)
    
    colorUsages = [gdal.GFU_Red, gdal.GFU_Green, gdal.GFU_Blue, gdal.GFU_Alpha]
    for idx, usage in enumerate(colorUsages):
        colNum = attrTbl.GetColOfUsage(usage)
        if colNum == -1:
            msg = 'Cannot find color table in file'
            raise ColorTableException(msg)
            
        ct[idx] = attrTbl.ReadAsArray(colNum)
        
    return ct
    
def setTable(imgFile, colorTable, bandNumber=1):
    """
    Given either an open gdal dataset, or a filename,
    sets the color table as an array.
    
    The colorTable is given as an array of shape (4, numEntries)
    where numEntries is the size of the color table. The order of indices
    in the first axis is:

        * Red
        * Green
        * Blue
        * Opacity
        
    The Red/Green/Blue values are on the range 0-255, with 255 meaning full 
    color, and the opacity is in the range 0-255, with 255 meaning fully 
    opaque. 
    
    This table is useually generated by getTable() or genTable().
    
    """    
    if isinstance(imgFile, basestring):
        ds = gdal.Open(str(imgFile), gdal.GA_Update)
    elif isinstance(imgFile, gdal.Dataset):
        ds = imgFile

    gdalBand = ds.GetRasterBand(bandNumber)
    attrTbl = gdalBand.GetDefaultRAT()
    if attrTbl is None:
        # some formats eg ENVI return None
        # here so we need to be able to cope
        attrTbl = gdal.RasterAttributeTable()
        isFileRAT = False
    else:

        isFileRAT = True

        # but if it doesn't support dynamic writing
        # we still ahve to call SetDefaultRAT
        if not attrTbl.ChangesAreWrittenToFile():
            isFileRAT = False
            
    ncols, numEntries = colorTable.shape
    attrTbl.SetRowCount(numEntries)
    
    # set the columns based on their usage, creating
    # if necessary
    colorUsages = {gdal.GFU_Red : 'Red', gdal.GFU_Green : 'Green', 
        gdal.GFU_Blue : 'Blue', gdal.GFU_Alpha : 'Alpha'}
    for idx, usage in enumerate(colorUsages):
        colNum = attrTbl.GetColOfUsage(usage)
        if colNum == -1:
            name = colorUsages[usage]
            attrTbl.CreateColumn(name, gdal.GFT_Integer, usage)
            colNum = attrTbl.GetColumnCount() - 1
            
        attrTbl.WriteArray(colorTable[idx], colNum)
        
    if not isFileRAT:
        attrTbl.SetDefaultRAT(attrTbl)
