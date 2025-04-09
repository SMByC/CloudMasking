"""
Contains functions used to write output files from applier.apply.

Also contains the now-deprecated ImageWriter class

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

from __future__ import print_function, division

import os
import math

from osgeo import gdal
from osgeo import gdal_array

from . import rioserrors
from . import rat
from . import calcstats
from . import fileinfo


def setDefaultDriver():
    """
    Sets some default values into global variables, defining
    what defaults we should use for GDAL driver. On any given
    output file these can be over-ridden, and can be over-ridden globally
    using the environment variables

        * $RIOS_DFLT_DRIVER
        * $RIOS_DFLT_DRIVEROPTIONS
        * $RIOS_DFLT_CREOPT_<drivername>
    
    If RIOS_DFLT_DRIVER is set, then it should be a gdal short driver name. 
    If RIOS_DFLT_DRIVEROPTIONS is set, it should be a space-separated list
    of driver creation options, e.g. "COMPRESS=LZW TILED=YES", and should
    be appropriate for the selected GDAL driver. This can also be 'None'
    in which case an empty list of creation options is passed to the driver.
    
    The same rules apply to the driver-specific creation options given
    using $RIOS_DFLT_CREOPT_<driver>. These options are a later paradigm, and 
    are intended to supercede the previous generic driver defaults. 
    
    If not otherwise supplied, the default is to use the HFA driver, with compression. 
    
    The code here is more complex than desirable, because it copes with legacy behaviour
    in the absence of the environment variables, and in the absence of the driver-specific
    option variables. 
        
    """
    global DEFAULTDRIVERNAME, DEFAULTCREATIONOPTIONS
    DEFAULTDRIVERNAME = os.getenv('RIOS_DFLT_DRIVER', default='HFA')
    creationOptionsStr = os.getenv('RIOS_DFLT_DRIVEROPTIONS')
    if creationOptionsStr is not None:
        if creationOptionsStr == 'None':
            # hack for KEA which needs no creation options
            # and LoadLeveler which deletes any env variables
            # set to an empty values
            DEFAULTCREATIONOPTIONS = []
        else:
            DEFAULTCREATIONOPTIONS = creationOptionsStr.split()
    else:
        # To cope with the old behaviour, set something sensible for HFA, but not
        # otherwise
        if DEFAULTDRIVERNAME == "HFA":
            DEFAULTCREATIONOPTIONS = ['COMPRESSED=TRUE', 'IGNOREUTM=TRUE']
        else:
            DEFAULTCREATIONOPTIONS = []
    
    # In the new paradigm, default creation options are specific to each driver, and
    # are loaded into a dictionary
    global dfltDriverOptions
    dfltDriverOptions = {}
    # Start with the old generic default options, applied to the default driver
    dfltDriverOptions[DEFAULTDRIVERNAME] = DEFAULTCREATIONOPTIONS
    # Load some others which we wish to have as defaults, even if not set by the environment
    dfltDriverOptions['GTiff'] = ['TILED=YES', 'COMPRESS=LZW', 'INTERLEAVE=BAND', 'BIGTIFF=IF_SAFER']
    # Now load any which are specified by environment variables, of the
    # form RIOS_DFLT_CREOPT_<drivername>
    driverOptVarPrefix = 'RIOS_DFLT_CREOPT_'
    for varname in os.environ:
        if varname.startswith(driverOptVarPrefix):
            drvrName = varname[len(driverOptVarPrefix):]
            optionsStr = os.getenv(varname)
            if optionsStr == 'None':
                # Repeat that ridiculous hack for the KEA/LoadLeveler combination
                dfltDriverOptions[drvrName] = []
            else:
                dfltDriverOptions[drvrName] = optionsStr.split()


setDefaultDriver()


def writeBlock(gdalOutObjCache, blockDefn, outfiles, outputs, controls,
        workinggrid, singlePassMgr, timings):
    """
    Write the given block to the files given in outfiles
    """
    for (symbolicName, seqNum, filename) in outfiles:
        arr = outputs[symbolicName, seqNum]
        # Trim the margin
        m = controls.getOptionForImagename('overlap', symbolicName)
        if m > 0:
            arr = arr[:, m:-m, m:-m]

        key = (symbolicName, seqNum)
        if key not in gdalOutObjCache:
            ds = openOutfile(symbolicName, filename, controls, arr,
                    workinggrid)
            gdalOutObjCache[symbolicName, seqNum] = ds
            singlePassMgr.initFor(ds, symbolicName, seqNum, arr)

        ds = gdalOutObjCache[symbolicName, seqNum]

        with timings.interval('writing'):
            # Write the base raster data
            ds.WriteArray(arr, blockDefn.left, blockDefn.top)

        # If appropriate, do single-pass actions for this block
        calcstats.handleSinglePassActions(ds, arr, singlePassMgr,
            symbolicName, seqNum, blockDefn.left, blockDefn.top, timings)


def openOutfile(symbolicName, filename, controls, arr, workinggrid):
    """
    Open the requested output file
    """
    # RIOS only works with 3-d image arrays, where the first dimension is
    # the number of bands. Check that this is what the user gave us to write.
    if len(arr.shape) != 3:
        msg = ("Shape of array to write must be 3-d. " +
            "Shape is actually {}").format(repr(arr.shape))
        raise rioserrors.ArrayShapeError(msg)

    deleteIfExisting(filename)

    driverName = controls.getOptionForImagename('drivername', symbolicName)
    creationoptions = controls.getOptionForImagename('creationoptions',
        symbolicName)
    if creationoptions is None:
        creationoptions = dfltDriverOptions.get(driverName, [])
    doubleCheckCreationOptions(driverName, creationoptions, controls,
        workinggrid)

    numBands = arr.shape[0]
    gdalDatatype = gdal_array.NumericTypeCodeToGDALTypeCode(arr.dtype)
    (nrows, ncols) = workinggrid.getDimensions()
    geotransform = workinggrid.makeGeoTransform()
    projWKT = workinggrid.projection
    thematic = controls.getOptionForImagename('thematic', symbolicName)
    nullVal = controls.getOptionForImagename('statsIgnore', symbolicName)
    layernames = controls.getOptionForImagename('layernames', symbolicName)

    drvr = gdal.GetDriverByName(driverName)
    ds = drvr.Create(filename, ncols, nrows, numBands, gdalDatatype,
        creationoptions)
    if ds is None:
        msg = 'Unable to create output file {}'.format(filename)
        raise rioserrors.ImageOpenError(msg)
    ds.SetGeoTransform(geotransform)
    ds.SetProjection(projWKT)

    for i in range(numBands):
        band = ds.GetRasterBand(i + 1)
        if thematic:
            band.SetMetadataItem('LAYER_TYPE', 'thematic')
        if nullVal is not None:
            band.SetNoDataValue(nullVal)
        if layernames is not None:
            band.SetDescription(layernames[i])

    return ds


def closeOutfiles(gdalOutObjCache, outfiles, controls, singlePassMgr, timings):
    """
    Close all the output files
    """
    # getOpt is just a little local shortcut
    getOpt = controls.getOptionForImagename

    for (symbolicName, seqNum, filename) in outfiles:
        omitPyramids = getOpt('omitPyramids', symbolicName)
        omitBasicStats = getOpt('omitBasicStats', symbolicName)
        omitHistogram = getOpt('omitHistogram', symbolicName)
        overviewLevels = getOpt('overviewLevels', symbolicName)
        overviewMinDim = getOpt('overviewMinDim', symbolicName)
        overviewAggType = getOpt('overviewAggType', symbolicName)
        approxStats = getOpt('approxStats', symbolicName)
        autoColorTableType = getOpt('autoColorTableType', symbolicName)
        progress = getOpt('progress', symbolicName)
        if progress is None:
            from .cuiprogress import SilentProgress
            progress = SilentProgress()

        ds = gdalOutObjCache[symbolicName, seqNum]
        with timings.interval('writing'):
            # Ensure that all data has been written
            ds.FlushCache()

        if (not singlePassMgr.doSinglePassPyramids(symbolicName) and
                not omitPyramids):
            # Pyramids have not been done single-pass, and are not being
            # omitted, so do them on closing (i.e. the old way)
            with timings.interval('pyramids'):
                calcstats.addPyramid(ds, progress, levels=overviewLevels,
                    minoverviewdim=overviewMinDim,
                    aggregationType=overviewAggType)

        if singlePassMgr.doSinglePassStatistics(symbolicName):
            with timings.interval('basicstats'):
                calcstats.finishSinglePassStats(ds, singlePassMgr,
                    symbolicName, seqNum)
            # Make the minMaxList from values already on singlePassMgr
            minMaxList = makeMinMaxList(singlePassMgr, symbolicName, seqNum)
        elif not omitBasicStats:
            with timings.interval('basicstats'):
                minMaxList = calcstats.addBasicStatsGDAL(ds, approxStats)

        if singlePassMgr.doSinglePassHistogram(symbolicName):
            with timings.interval('histogram'):
                calcstats.finishSinglePassHistogram(ds, singlePassMgr,
                    symbolicName, seqNum)
        elif not omitHistogram:
            with timings.interval('histogram'):
                calcstats.addHistogramsGDAL(ds, minMaxList, approxStats)

        # This is doing everything I can to ensure the file gets fully closed
        # at this point.
        ds.FlushCache()
        gdalOutObjCache.pop((symbolicName, seqNum))
        del ds

        # Check whether we will need to add an auto color table
        if autoColorTableType is not None:
            # Does nothing if layers are not thematic
            addAutoColorTable(filename, autoColorTableType)


def makeMinMaxList(singlePassMgr, symbolicName, seqNum):
    """
    Make a list of min/max values per band, for the nominated output file,
    from values already present on singlePassMgr.
    Mimicing the list returned by addBasicStatsGDAL, for use with
    addHistogramsGDAL.

    """
    accumList = singlePassMgr.accumulators[symbolicName, seqNum]
    minMaxList = []
    for i in range(len(accumList)):
        accum = accumList[i]
        (minval, maxval) = (accum.minval, accum.maxval)
        minMaxList.append((minval, maxval))
    return minMaxList


def deleteIfExisting(filename):
    """
    Delete the filename if it already exists. If possible, use the
    appropriate GDAL driver to do so, to ensure that any associated
    files will also be deleted.

    """
    if os.path.exists(filename):
        drvr = gdal.IdentifyDriver(filename)
        if drvr is not None:
            drvr.Delete(filename)
        else:
            # Apparently not a valid GDAL file, for whatever reason,
            # so just remove the file directly.
            os.remove(filename)


def doubleCheckCreationOptions(drivername, creationoptions, controls,
        workinggrid):
    """
    Try to ensure that the given creation options are compatible with
    RIOS operations. Does not attempt to ensure they are totally valid, as
    that is GDAL's job.

    If it finds any incompatibility, an exception is raised.

    """
    if drivername == 'GTiff':
        # The GDAL GTiff driver is incapable of reclaiming space within the
        # file. This means that if a block is re-written, then the space
        # already used is left dangling, and the total file size gets larger
        # accordingly. If the RIOS block size is not a multiple of the TIFF
        # block size, then each RIOS block will require the re-writing of at
        # least one TIFF block (usually several). This turns out to be a
        # disaster for file sizes. So, here, we do our best to check these
        # things, and prevent such a result. The recommended configuration
        # is that the $RIOS_DFLT_BLOCKXSIZE and $RIOS_DFLT_BLOCKYSIZE be
        # set to a power of 2, and everything else will follow.

        # Work out what block size values the GTiff driver will use
        tiffBlockX = None
        tiffBlockY = None
        tiled = False
        for optStr in creationoptions:
            optTokens = optStr.split('=')
            if optTokens[0] == 'BLOCKXSIZE':
                tiffBlockX = int(optStr[11:])
            elif optTokens[0] == 'BLOCKYSIZE':
                tiffBlockY = int(optStr[11:])
            elif optTokens[0] == 'TILED':
                tiled = True

        # Apply default TIFF block sizes if not explicitly requested. These are
        # as defined by GDAL at
        #   https://gdal.org/drivers/raster/gtiff.html#creation-options
        # assuming I have read it correctly.
        (nRows, nCols) = workinggrid.getDimensions()
        if tiffBlockX is None:
            if tiled:
                tiffBlockX = 256
            else:
                # If not TILED=YES then GTiff uses blocks which are full width
                tiffBlockX = nCols
        if tiffBlockY is None:
            if tiled:
                tiffBlockY = 256
            else:
                # If not tiled, then default strip height is such that one
                # strip is 8K (which I assume is a count of pixels)
                tiffBlockY = int(8 * 1024 / tiffBlockX)

        # Require that tiff block sizes be a factor of the RIOS block size, so
        # that whole TIFF blocks are always written exactly once, with no
        # re-writing.
        riosBlockX = controls.windowxsize
        riosBlockY = controls.windowysize
        if ((riosBlockX < tiffBlockX) or ((riosBlockX % tiffBlockX) != 0) or
                (riosBlockY < tiffBlockY) or ((riosBlockY % tiffBlockY) != 0)):
            msg = ("RIOS block dimensions {} should be multiples of GTiff " +
                "block dimensions {}, otherwise vast amounts of space are " +
                "wasted rewriting blocks which are not reclaimed.").format(
                (riosBlockX, riosBlockY), (tiffBlockX, tiffBlockY))
            raise rioserrors.ImageOpenError(msg)


def addAutoColorTable(filename, autoColorTableType):
    """
    If autoColorTable has been set up for this output, then generate
    a color table of the requested type, and add it to the current
    file. This is called AFTER the Dataset has been closed, so is performed on
    the filename. This only applies to thematic layers, so when we open the file
    and find that the layers are athematic, we do nothing. 

    """
    imgInfo = fileinfo.ImageInfo(filename)
    if imgInfo.layerType == "thematic":
        imgStats = fileinfo.ImageFileStats(filename)
        ds = gdal.Open(filename, gdal.GA_Update)

        for i in range(imgInfo.rasterCount):
            numEntries = int(imgStats[i].max + 1)
            clrTbl = rat.genColorTable(numEntries, autoColorTableType)
            band = ds.GetRasterBand(i + 1)
            ratObj = band.GetDefaultRAT()
            redIdx, redNew = calcstats.findOrCreateColumn(ratObj, gdal.GFU_Red, "Red", gdal.GFT_Integer)
            greenIdx, greenNew = calcstats.findOrCreateColumn(ratObj, gdal.GFU_Green, "Green", gdal.GFT_Integer)
            blueIdx, blueNew = calcstats.findOrCreateColumn(ratObj, gdal.GFU_Blue, "Blue", gdal.GFT_Integer)
            alphaIdx, alphaNew = calcstats.findOrCreateColumn(ratObj, gdal.GFU_Alpha, "Alpha", gdal.GFT_Integer)
            # were any of these not already existing?
            if redNew or greenNew or blueNew or alphaNew:
                ratObj.WriteArray(clrTbl[:, 0], redIdx)
                ratObj.WriteArray(clrTbl[:, 1], greenIdx)
                ratObj.WriteArray(clrTbl[:, 2], blueIdx)
                ratObj.WriteArray(clrTbl[:, 3], alphaIdx)
            if not ratObj.ChangesAreWrittenToFile():
                band.SetDefaultRAT(ratObj)


# WARNING
# WARNING
# WARNING
# WARNING
# WARNING       All code below this point is deprecated (v2.0.0)
# WARNING
# WARNING
# WARNING
# WARNING


def allnotNone(items):
    for i in items:
        if i is None:
            return False
    return True


def anynotNone(items):
    for i in items:
        if i is not None:
            return True
    return False


class ImageWriter(object):
    """
    This class is the opposite of the ImageReader class and is designed
    to be used in conjunction. The easiest way to use it is pass the
    info returned by the ImageReader for first iteration to the constructor.
    Otherwise, image size etc must be passed in.
    
    The write() method can be used to write a block (numpy array)at a 
    time to the output image - this is designed to be used at each 
    iteration through the ImageReader object. Otherwise, the writeAt() 
    method can be used to write blocks to arbitary locations.

    **Example**
    
    ::

        import sys
        from rios.imagereader import ImageReader
        from rios.imagewriter import ImageWriter

        inputs = [sys.argv[1],sys.argv[2]]
        reader = ImageReader(inputs) 
        writer = None 
        for (info, blocks) in reader:     
            block1,block2 = blocks
            out = block1 * 4 + block2
            if writer is None:
                writer = ImageWriter(sys.argv[3],info=info,
                    firstblock=out)
            else:
                writer.write(out)

        writer.close(calcStats=True)
    
    """
    def __init__(self, filename, drivername=DEFAULTDRIVERNAME, creationoptions=None,
            nbands=None, gdaldatatype=None, firstblock=None, 
            info=None, xsize=None, ysize=None, transform=None, projection=None,
            windowxsize=None, windowysize=None, overlap=None):
        """
        filename is the output file to be created. Set driver to name of
        GDAL driver, default it HFA. creationoptions will also need to be
        set if not using HFA since the default probably does not make sense
        for other drivers.
        
        Either pass nbands and gdaldatatype OR firstblock. If you pass 
        firstblock, nbands and gdaldataype will be determined from that block
        and that block written to file.
        
        Also, either pass info (the first argument returned from each iteration
        through ImageReader, generally create this class on the first iteration)
        or xsize, ysize, transform, projection, windowxsize, windowysize and overlap
        If you pass info, these other values will be determined from that
        
        """
        msg = "The ImageWriter class is now deprecated (v2.0.0)"
        rioserrors.deprecationWarning(msg)

        self.filename = filename
        noninfoitems = [xsize, ysize, transform, projection, windowxsize,
            windowysize, overlap]
        if info is None:
            # check we have the other args
            if not allnotNone(noninfoitems):
                msg = 'If not passing info object, must pass all other image info'
                raise rioserrors.ParameterError(msg)

            # just save these values directly
            self.overlap = overlap
            self.windowxsize = windowxsize
            self.windowysize = windowysize
            self.xtotalblocks = int(math.ceil(float(xsize) / windowxsize))
            self.ytotalblocks = int(math.ceil(float(ysize) / windowysize))
            
        else:
            if anynotNone(noninfoitems):
                msg = 'Passed info object, but other args not None'
                raise rioserrors.ParameterError(msg)
                    
            # grab what we need from the info object
            (xsize, ysize) = info.getTotalSize()
            transform = info.getTransform()
            projection = info.getProjection()
            (self.windowxsize, self.windowysize) = info.getWindowSize()
            self.overlap = info.getOverlapSize()
            (self.xtotalblocks, self.ytotalblocks) = info.getTotalBlocks()

        if firstblock is None and not allnotNone([nbands, gdaldatatype]):
            msg = 'if not passing firstblock, must pass nbands and gdaltype'
            raise rioserrors.ParameterError(msg)
                        
        elif firstblock is not None and anynotNone([nbands, gdaldatatype]):
            msg = 'Must pass one either firstblock or nbands and gdaltype, not all of them'
            raise rioserrors.ParameterError(msg)
                        
        if firstblock is not None:
            # RIOS only works with 3-d image arrays, where the first dimension is 
            # the number of bands. Check that this is what the user gave us to write. 
            if len(firstblock.shape) != 3:
                raise rioserrors.ArrayShapeError(
                    "Shape of array to write must be 3-d. Shape is actually %s"%repr(firstblock.shape))

            # get the number of bands out of the block
            (nbands, y, x) = firstblock.shape
            # and the datatype
            gdaldatatype = gdal_array.NumericTypeCodeToGDALTypeCode(firstblock.dtype)

        if creationoptions is None:
            if drivername in dfltDriverOptions:
                creationoptions = dfltDriverOptions[drivername]
            else:
                creationoptions = []
        creationoptions = self.doubleCheckCreationOptions(drivername, creationoptions)
        
        self.deleteIfExisting(filename)
                    
        # Create the output dataset
        driver = gdal.GetDriverByName(drivername)
        self.ds = driver.Create(str(filename), xsize, ysize, nbands, gdaldatatype, creationoptions)
        if self.ds is None:
            msg = 'Unable to create output file %s' % filename
            raise rioserrors.ImageOpenError(msg)
                    
        self.ds.SetProjection(projection)
        self.ds.SetGeoTransform(transform)
            
        # start writing at the first block
        self.blocknum = 0
            
        # if we have a first block then write it
        if firstblock is not None:
            self.write(firstblock)
            
    @staticmethod
    def deleteIfExisting(filename):
        """
        Delete the filename if it already exists.
        If possible, use the appropriate GDAL driver to do so, to ensure
        that any associated files will also be deleted. 

        """
        if os.path.exists(filename):
            # Save the current exception-use state
            usingExceptions = gdal.GetUseExceptions()
            if not usingExceptions:
                gdal.UseExceptions()

            # Try opening it for read, to find out whether it is 
            # a valid GDAL file, and which driver it goes with
            try:
                ds = gdal.Open(str(filename))
            except RuntimeError:
                ds = None
            finally:
                # Restore exception-use state
                if not usingExceptions:
                    gdal.DontUseExceptions()

            if ds is not None:
                # It is apparently a valid GDAL file, so get the driver appropriate for it.
                drvr = ds.GetDriver()
                del ds
                # Use this driver to delete the file
                drvr.Delete(filename)
            else:
                # Apparently not a valid GDAL file, for whatever reason, so just remove the file
                # directly. 
                os.remove(filename)

    def getGDALDataset(self):
        """
        Returns the underlying GDAL dataset object
        """
        return self.ds
        
    def getCurrentBlock(self):
        """
        Returns the number of the current block
        """
        return self.blocknum
                    
    def setThematic(self):
        """
        Sets the output file to thematic. If file is multi-layer,
        then all bands are set to thematic. 
        """
        for i in range(1, self.ds.RasterCount + 1):
            band = self.ds.GetRasterBand(i)
            band.SetMetadataItem('LAYER_TYPE', 'thematic')
                        
    def setLayerNames(self, names):
        """
        Sets the output layer names. Pass a list
        of layer names, one for each output band
        """
        bandindex = 1
        for name in names:
            bh = self.ds.GetRasterBand(bandindex)
            bh.SetDescription(name)            
            bandindex += 1
        
    def write(self, block):
        """
        Writes the numpy block to the current location in the file,
        and updates the location pointer for next write
        """
        
        # convert the block to row/column
        yblock = self.blocknum // self.xtotalblocks
        xblock = self.blocknum % self.xtotalblocks
        
        # calculate the coords of this block in pixels
        xcoord = xblock * self.windowxsize
        ycoord = yblock * self.windowysize
        
        self.writeAt(block, xcoord, ycoord)
        
        # so next time we write the next block
        self.blocknum += 1
        
    def writeAt(self, block, xcoord, ycoord):
        """
        writes the numpy block to the specified pixel coords
        in the file
        """
        # check they asked for block is valid
        brxcoord = xcoord + block.shape[-1] - self.overlap * 2
        brycoord = ycoord + block.shape[-2] - self.overlap * 2
        if brxcoord > self.ds.RasterXSize or brycoord > self.ds.RasterYSize:
            raise rioserrors.OutsideImageBoundsError()
            
        # check they did actually pass a 3d array
        # (all arrays are 3d now - PyModeller had 2 and 3d)
        if block.ndim != 3:
            raise rioserrors.ParameterError("Only 3 dimensional arrays are accepted now")
            
        # write each band
        for band in range(self.ds.RasterCount):
        
            bh = self.ds.GetRasterBand(band + 1)
            slice_bottomMost = block.shape[-2] - self.overlap
            slice_rightMost = block.shape[-1] - self.overlap
            
            # take off overlap if present
            outblock = block[band, self.overlap:slice_bottomMost, self.overlap:slice_rightMost]
                
            bh.WriteArray(outblock, xcoord, ycoord)

    def reset(self):
        """
        Resets the location pointer so that the next
        write() call writes to the start of the file again
        """
        self.blocknum = 0
    
    def close(self, calcStats=False, statsIgnore=None, progress=None, omitPyramids=False,
            overviewLevels=calcstats.DEFAULT_OVERVIEWLEVELS,
            overviewMinDim=calcstats.DEFAULT_MINOVERVIEWDIM, 
            overviewAggType=None, autoColorTableType=rat.DEFAULT_AUTOCOLORTABLETYPE,
            approx_ok=False):
        """
        Closes the open dataset
        """
        if statsIgnore is not None:
            # This also gets set inside addStatistics. That is a 
            # historical anomaly. This is the correct place to do it. 
            calcstats.setNullValue(self.ds, statsIgnore)

        if calcStats:
            from .cuiprogress import SilentProgress
            if progress is None:
                progress = SilentProgress()
            
            if not omitPyramids:
                calcstats.addPyramid(self.ds, progress, minoverviewdim=overviewMinDim,
                    levels=overviewLevels, aggregationType=overviewAggType)

            calcstats.addStatistics(self.ds, progress, statsIgnore, approx_ok=approx_ok) 
        
        self.ds.FlushCache()
        del self.ds
        self.ds = None
        
        # Check whether we will need to add an auto color table
        if autoColorTableType is not None:
            # Does nothing if layers are not thematic
            self.addAutoColorTable(autoColorTableType)
    
    def addAutoColorTable(self, autoColorTableType):
        """
        If autoColorTable has been set up for this output, then generate
        a color table of the requested type, and add it to the current
        file. This is called AFTER the Dataset has been closed, so is performed on
        the filename. This only applies to thematic layers, so when we open the file
        and find that the layers are athematic, we do nothing. 
        
        """
        imgInfo = fileinfo.ImageInfo(self.filename)
        if imgInfo.layerType == "thematic":
            imgStats = fileinfo.ImageFileStats(self.filename)
            ds = gdal.Open(self.filename, gdal.GA_Update)

            for i in range(imgInfo.rasterCount):
                numEntries = int(imgStats[i].max + 1)
                clrTbl = rat.genColorTable(numEntries, autoColorTableType)
                band = ds.GetRasterBand(i + 1)
                ratObj = band.GetDefaultRAT()
                redIdx, redNew = calcstats.findOrCreateColumn(ratObj, gdal.GFU_Red, "Red", gdal.GFT_Integer)
                greenIdx, greenNew = calcstats.findOrCreateColumn(ratObj, gdal.GFU_Green, "Green", gdal.GFT_Integer)
                blueIdx, blueNew = calcstats.findOrCreateColumn(ratObj, gdal.GFU_Blue, "Blue", gdal.GFT_Integer)
                alphaIdx, alphaNew = calcstats.findOrCreateColumn(ratObj, gdal.GFU_Alpha, "Alpha", gdal.GFT_Integer)
                # were any of these not already existing?
                if redNew or greenNew or blueNew or alphaNew:
                    ratObj.WriteArray(clrTbl[:, 0], redIdx)
                    ratObj.WriteArray(clrTbl[:, 1], greenIdx)
                    ratObj.WriteArray(clrTbl[:, 2], blueIdx)
                    ratObj.WriteArray(clrTbl[:, 3], alphaIdx)
                if not ratObj.ChangesAreWrittenToFile():
                    band.SetDefaultRAT(ratObj)

    def doubleCheckCreationOptions(self, drivername, creationoptions):
        """
        Try to ensure that the given creation options are not incompatible with RIOS
        operations. Does not attempt to ensure they are totally valid, as that is GDAL's
        job. 
        
        Returns a copy of creationoptions, possibly modified, or raises ImageOpenError
        in cases where the problem is not fixable. 
        
        """
        newCreationoptions = creationoptions
        
        if drivername == 'GTiff':
            # The GDAL GTiff driver is incapable of reclaiming space within the file. This means that
            # if a block is re-written, then the space already used is left dangling, and the total
            # file size gets larger accordingly. If the RIOS block size is not a multiple of the 
            # TIFF block size, then each RIOS block will require the re-writing of at least one
            # TIFF block (usually several). This turns out to be a disaster for file sizes. So,
            # here, we do our best to check these things, and prevent such a result. 
            # The recommended configuration is that the $RIOS_DFLT_BLOCKXSIZE and 
            # $RIOS_DFLT_BLOCKYSIZE be set to a power of 2, and everything else will follow. 
            
            tiffBlockX = None
            tiffBlockY = None
            riosBlockX = self.windowxsize
            riosBlockY = self.windowysize
            
            # First copy the existing options, but keep aside any explicitly specified block size
            newCreationoptions = []
            for optStr in creationoptions:
                if optStr[:11] == 'BLOCKXSIZE=':
                    tiffBlockX = int(optStr[11:])
                elif optStr[:11] == 'BLOCKYSIZE=':
                    tiffBlockY = int(optStr[11:])
                else:
                    newCreationoptions.append(optStr)
            
            # If no tiff blocksizes were explictly requested, then set them the same as the 
            # RIOS block sizes
            resettingTiffBlocksize = False
            if tiffBlockX is None:
                tiffBlockX = riosBlockX
                resettingTiffBlocksize = True
            if tiffBlockY is None:
                tiffBlockY = riosBlockY
                resettingTiffBlocksize = True
            
            # Require that tiff block sizes be a factor of the RIOS block size, so that whole
            # TIFF blocks are always written exactly once, with no re-writing. 
            if (((riosBlockX % tiffBlockX) != 0) or ((riosBlockY % tiffBlockY) != 0)):
                msg = "GTiff block sizes {} should be factors of RIOS block sizes {}, ".format(
                    (tiffBlockX, tiffBlockY), (riosBlockX, riosBlockY))
                msg += "otherwise vast amounts of space are wasted rewriting blocks which are not reclaimed. "
                raise rioserrors.ImageOpenError(msg)

            # The GDAL GTiff driver will complain if GTiff block sizes are not powers of 2
            def isPowerOf2(n):
                return (((n - 1) & n) == 0)
            if not (isPowerOf2(tiffBlockX) and isPowerOf2(tiffBlockY)):
                msg = "GTiff block sizes are {}. Must be powers of 2. ".format((tiffBlockX, tiffBlockY))
                if resettingTiffBlocksize:
                    msg += "GTiff block size(s) have been reset to match RIOS block sizes, so recommend adjusting RIOS block sizes. "
                else:
                    msg += "Recommend resetting explicit GTiff block sizes. "
                raise rioserrors.ImageOpenError(msg)

            # Now append what we want the block size to be. 
            newCreationoptions.append('BLOCKXSIZE={}'.format(self.windowxsize))
            newCreationoptions.append('BLOCKYSIZE={}'.format(self.windowysize))

        return newCreationoptions
