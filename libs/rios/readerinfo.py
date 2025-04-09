
"""
This module contains the ReaderInfo class
which holds information about the area being
read and info on the current block

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

import math

import numpy

from . import imageio, fileinfo


def makeReaderInfo(workinggrid, blockDefn, controls, infiles, inputs, allInfo):
    """
    Construct a ReaderInfo object for the current block.

    In earlier versions of RIOS, this was constructed more organically
    during the block iteration process (although it was rather obscure,
    even then). In newer versions, we are putting it together from
    other information, to maintain full compatibility when this is passed
    to the user function. It is not used for any other purpose within RIOS.

    """
    info = ReaderInfo(workinggrid, controls.windowxsize,
            controls.windowysize, controls.overlap, controls.loggingstream)
    info.setBlockSize(blockDefn.ncols, blockDefn.nrows)
    transform = workinggrid.makeGeoTransform()
    (top, left) = (blockDefn.top, blockDefn.left)
    blocktl = imageio.pix2wld(transform, left, top)
    (right, bottom) = (left + blockDefn.ncols, top + blockDefn.nrows)
    blockbr = imageio.pix2wld(transform, right, bottom)
    info.setBlockBounds(blocktl, blockbr)
    xblock = int(round(left / controls.windowxsize))
    yblock = int(round(top / controls.windowysize))
    info.setBlockCount(xblock, yblock)

    # Make the lookups keyed by array id() value, to service getNoDataValueFor
    # and getFilenameFor
    info.filenameLookup = {}
    info.nullvalLookup = {}
    for (symbolicName, seqNum, filename) in infiles:
        key = (symbolicName, seqNum)
        arr = inputs[key]
        arrID = id(arr)
        info.filenameLookup[arrID] = filename
        imgInfo = allInfo[key]

        if isinstance(imgInfo, fileinfo.ImageInfo):
            # Store all null values for the (possibly reduced) set of bands.
            # See getNoDataValueFor() for details on how this interacts with
            # controls.selectInputImageLayers().
            layerselection = controls.getOptionForImagename(
                'layerselection', symbolicName)
            if layerselection is None:
                layerselection = numpy.arange(1, imgInfo.rasterCount + 1)

            # Work out what null value(s) to use, honouring anything set
            # with controls.setInputNoDataValue().
            nullvalList = controls.getOptionForImagename('inputnodata',
                    symbolicName)
            if nullvalList is not None and not isinstance(nullvalList, list):
                # Turn a scalar into a list, one for each band in the file
                nullvalList = [nullvalList] * len(layerselection)

            # If we have None from controls, then use whatever is
            # specified on imgInfo, while also honouring layerselection
            if nullvalList is None:
                nullvalList = [imgInfo.nodataval[bandNum - 1]
                    for bandNum in layerselection]

            info.nullvalLookup[arrID] = nullvalList

    return info


class ReaderInfo(object):
    """
    ReaderInfo class. Holds information about the area being
    read and info on the current block
    
    """
    def __init__(self, workingGrid, 
            windowxsize, windowysize, overlap, loggingstream):
                    
        self.loggingstream = loggingstream
        # grab the working grid
        self.workingGrid = workingGrid
        
        # save the window size and overlap
        self.windowxsize = windowxsize
        self.windowysize = windowysize
        self.overlap = overlap
        
        # work out the area being read
        self.xsize = int(round((self.workingGrid.xMax - 
                        self.workingGrid.xMin) / self.workingGrid.xRes))
        self.ysize = int(round((self.workingGrid.yMax - 
                        self.workingGrid.yMin) / self.workingGrid.yRes))
        
        # total number of blocks
        self.xtotalblocks = int(math.ceil(float(self.xsize) / self.windowxsize))
        self.ytotalblocks = int(math.ceil(float(self.ysize) / self.windowysize))
        
        # The fields below apply to a particular block
        # and are filled in after this object is copied 
        # to make it specific for each block
        self.blockwidth = None
        self.blockheight = None
        
        self.blocktl = None
        self.blockbr = None
        
        self.xblock = None
        self.yblock = None
        
        # dictionary keyed by id() of the number array
        # value is a tuple with the GDAL dataset object 
        # that corresponds to it, and the original filename
        self.blocklookup = {}
        
    def setBlockDataset(self, block, dataset, filename):
        """
        Saves a match between the numpy block read
        and it's GDAL dataset. So we can look up the
        dataset later given a block.
        
        This routine is for internal use by RIOS. Its use in any other
        context is not sensible. 
        
        This is no longer implemented, and raises an exception if called.
        """
        msg = "setBlockDataset is obsolete, and no longer implemented"
        raise NotImplementedError(msg)
        
    def getWindowSize(self):
        """
        Returns the size of the current window. Returns a 
        tuple (numCols, numRows)
        
        """
        return (self.windowxsize, self.windowysize)
        
    def getOverlapSize(self):
        """
        Returns the size of the pixel overlap between
        each window. This is the number of pixels added as 
        margin around each block
        """
        return self.overlap
        
    def getTotalSize(self):
        """
        Returns the total size (in pixels) of the dataset
        being processed
        """
        return (self.xsize, self.ysize)
        
    def getTransform(self):
        """
        Return the current transform between world
        and pixel coords. This is as defined by GDAL. 
        """
        return self.workingGrid.makeGeoTransform()
        
    def getProjection(self):
        """
        Return the WKT describing the current
        projection system
        """
        return self.workingGrid.projection

    def getTotalBlocks(self):
        """
        Returns the total number of blocks the dataset
        has been split up into for processing
        """
        return (self.xtotalblocks, self.ytotalblocks)

    def setBlockSize(self, blockwidth, blockheight):
        """
        Sets the size of the current block

        This routine is for internal use by RIOS. Its use in any other
        context is not sensible. 
        
        """
        self.blockwidth = blockwidth
        self.blockheight = blockheight

    def getBlockSize(self):
        """
        Get the size of the current block. Returns a tuple::

            (numCols, numRows)

        for the current block. Mostly the same as the window size, 
        except on the edge of the raster. 
        """
        return (self.blockwidth, self.blockheight)

    def setBlockBounds(self, blocktl, blockbr):
        """
        Sets the coordinate bounds of the current block

        This routine is for internal use by RIOS. Its use in any other
        context is not sensible. 
        
        """
        self.blocktl = blocktl
        self.blockbr = blockbr

    def getBlockCoordArrays(self):
        """
        Return a tuple of the world coordinates for every pixel
        in the current block. Each array has the same shape as the 
        current block. Return value is a tuple::

            (xBlock, yBlock)

        where the values in xBlock are the X coordinates of the centre
        of each pixel, and similarly for yBlock. 
        
        The coordinates returned are for the pixel centres. This is 
        slightly inconsistent with usual GDAL usage, but more likely to
        be what one wants. 
        
        """
        (tl, _) = (self.blocktl, self.blockbr)
        (nCols, nRows) = self.getBlockSize()
        nCols += 2 * self.overlap
        nRows += 2 * self.overlap
        (xRes, yRes) = self.getPixelSize()
        (rowNdx, colNdx) = numpy.mgrid[0:nRows, 0:nCols]
        xBlock = tl.x - self.overlap * xRes + xRes / 2.0 + colNdx * xRes
        yBlock = tl.y + self.overlap * yRes - yRes / 2.0 - rowNdx * yRes
        return (xBlock, yBlock)
        
    def setBlockCount(self, xblock, yblock):
        """
        Sets the count of the current block

        This routine is for internal use by RIOS. Its use in any other
        context is not sensible. 
        
        """
        self.xblock = xblock
        self.yblock = yblock

    def getBlockCount(self):
        """
        Gets the count of the current block
        """
        return (self.xblock, self.yblock)
    
    def getPixelSize(self):
        """
        Gets the current pixel size and returns it as a tuple (x and y)
        """
        return (self.workingGrid.xRes, self.workingGrid.yRes)
    
    def getPixRowColBlock(self, x, y):
        """
        Return the row/column numbers, within the current block,
        for the pixel which contains the given (x, y) coordinate.
        The coordinates of (x, y) are in the world coordinate
        system of the reference grid. The row/col numbers are 
        suitable to use as array indices in the array(s) for the 
        current block. If the nominated pixel is not contained
        within the current block, the row and column numbers are
        both None (hence this should be checked). 
        
        Return value is a tuple of 2 int values
            (row, col)
        
        """
        transform = self.workingGrid.makeGeoTransform()
        imgRowCol = imageio.wld2pix(transform, x, y)
        imgRow = imgRowCol.y
        imgCol = imgRowCol.x
        
        blockStartRow = self.yblock * self.windowysize - self.overlap
        blockStartCol = self.xblock * self.windowxsize - self.overlap
        
        blockRow = int(imgRow - blockStartRow)
        blockCol = int(imgCol - blockStartCol)
        
        if ((blockRow < 0 or blockRow > (self.windowysize + 2 * self.overlap)) or
           (blockCol < 0 or blockCol > (self.windowxsize + 2 * self.overlap))):
            blockRow = None
            blockCol = None
        
        return (blockRow, blockCol)
    
    def getPixColRow(self, x, y):
        """
        This function is for internal use only. The user should
        be looking at getBlockCoordArrays() or getPixRowColBlock()
        for dealing with blocks and coordinates.
        
        Get the (col, row) relative to the current image grid,
        for the nominated pixel within the current block. The
        given (x, y) are column/row numbers (starting at zero),
        and the return is a tuple::

            (column, row)

        where these are relative to the whole of the current
        working grid. If working with a single raster, this is the same
        as for that raster, but if working with multiple rasters, 
        the working grid is the intersection or union of them. 
        
        Note that this function will give incorrect/misleading results
        if used in conjunction with a block overlap. 
         
        """
        col = self.xblock * self.windowxsize + x
        row = self.yblock * self.windowysize + y
        return (col, row)

    def isFirstBlock(self):
        """
        Returns True if this is the first block to be processed
        """
        return self.xblock == 0 and self.yblock == 0

    def isLastBlock(self):
        """
        Returns True if this is the last block to be processed
        """
        xtotalblocksminus1 = self.xtotalblocks - 1
        ytotalblocksminus1 = self.ytotalblocks - 1
        return self.xblock == xtotalblocksminus1 and self.yblock == ytotalblocksminus1

    def getFilenameFor(self, block):
        """
        Get the input filename of a dataset

        """
        return self.filenameLookup[id(block)]

    def getGDALDatasetFor(self, block):
        """
        Get the underlying GDAL handle of a dataset

        This is no longer implemented, and raises an exception if called.
        """
        msg = "getGDALDatasetFor is obsolete, and no longer implemented"
        raise NotImplementedError(msg)

    def getGDALBandFor(self, block, band):
        """
        Get the underlying GDAL handle for a band of a dataset

        This is no longer implemented, and raises an exception if called.
        """
        msg = "getGDALBandFor is obsolete, and no longer implemented"
        raise NotImplementedError(msg)

    def getNoDataValueFor(self, block, band=1):
        """
        Returns the 'no data' value for the dataset underlying the block.
        This should be the same as what was set for the stats ignore value
        when that dataset was created. The value is cast to the same data
        type as the dataset.

        The band number starts at 1, following GDAL's convention.

        Note, however, that if controls.selectInputImageLayers() was used to
        read a reduced set of input layers from the file, then these numbers
        are of the reduced set. For example, 1 will refer to the first of the
        selected layers, which may not be the first in the file.

        This is not the preferred method for the user function to access
        the null value for an input file. A more transparent approach is to
        make such values available on the otherArgs object. This function is
        maintained for backward compatibility.

        """
        nullvalList = self.nullvalLookup[id(block)]
        nullval = nullvalList[band - 1]
        if nullval is not None:
            nullval = numpy.asarray(nullval, dtype=block.dtype)
        return nullval
        
    def getPercent(self):
        """
        Returns the percent complete. 
        """
        percent = int(float(self.yblock * self.xtotalblocks + self.xblock) / 
                    float(self.xtotalblocks * self.ytotalblocks) * 100)
        return percent

