"""
Contains the functions needed for opening and reading input files, and the
ReadWorkerMgr class used to manage concurrent read workers.

Also contains the now-deprecated ImageReader class.

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
import os
import sys
import copy
from concurrent import futures
import queue
import threading

import numpy
from osgeo import gdal, gdal_array, osr

from . import imageio
from . import inputcollection
from . import readerinfo
from . import rioserrors
from . import VersionObj
from .structures import BlockAssociations, WorkerErrorRecord
from .fileinfo import ImageInfo, VectorFileInfo
from .pixelgrid import PixelGridDefn, findCommonRegion

if sys.version_info[0] > 2:
    # hack for Python 3 which uses str instead of basestring
    # we just use basestring
    basestring = str

DEFAULTFOOTPRINT = int(os.getenv('RIOS_DFLT_FOOTPRINT', 
                            default=imageio.INTERSECTION))
DEFAULTWINDOWXSIZE = int(os.getenv('RIOS_DFLT_BLOCKXSIZE', default=256))
DEFAULTWINDOWYSIZE = int(os.getenv('RIOS_DFLT_BLOCKYSIZE', default=256))
DEFAULTOVERLAP = int(os.getenv('RIOS_DFLT_OVERLAP', default=0))
DEFAULTLOGGINGSTREAM = sys.stdout


def readBlockAllFiles(infiles, workinggrid, blockDefn, allInfo, gdalObjCache,
        controls, tmpfileMgr, rasterizeMgr):
    """
    Read all input files for a single block.
    Return the complete BlockAssociations object (i.e. 'inputs').
    """
    inputs = BlockAssociations(infiles)
    for (symbolicName, seqNum, filename) in infiles:
        arr = readBlockOneFile(blockDefn, symbolicName, seqNum, filename,
            gdalObjCache, controls, tmpfileMgr, rasterizeMgr, workinggrid,
            allInfo)
        inputs[symbolicName, seqNum] = arr
    return inputs


def readBlockOneFile(blockDefn, symbolicName, seqNum, filename, gdalObjCache,
        controls, tmpfileMgr, rasterizeMgr, workinggrid, allInfo):
    """
    Read the requested block, as per blockDefn, of the requested file,
    as per (symbolicName, seqNum, filename). If the file has already been
    opened, its GDAL objects will be in the gdalObjCache, otherwise
    it will be opened and those objects placed in the cache.

    Return a numpy array for the block, of shape (numBands, numRows, numCols).

    """
    if (symbolicName, seqNum) not in gdalObjCache:
        # The file has not yet been opened, so open it, and cache the
        # GDAL Dataset & Band objects
        fileInfo = allInfo[symbolicName, seqNum]
        (ds, bandObjList) = openForWorkingGrid(filename, workinggrid,
            fileInfo, controls, tmpfileMgr, rasterizeMgr, symbolicName)
        gdalObjCache[symbolicName, seqNum] = (ds, bandObjList)

    (ds, bandObjList) = gdalObjCache[symbolicName, seqNum]

    (left, top, xsize, ysize) = (blockDefn.left, blockDefn.top,
            blockDefn.ncols, blockDefn.nrows)

    # We construct the final output array. It begins as an array full of
    # nulls, then we read in the array for each band. Since the block
    # may be incomplete (i.e. off the edge of the extent), we then slot
    # it in to the right portion of the full array.

    margin = controls.overlap
    nBands = len(bandObjList)
    shape = (nBands, ysize + 2 * margin, xsize + 2 * margin)
    gdalType = bandObjList[0].DataType
    dtype = gdal_array.GDALTypeCodeToNumericTypeCode(gdalType)

    # We need a null value to initialize the array. Figure out
    # what to use, depending on what is available.
    nullvalList = controls.getOptionForImagename('inputnodata',
                symbolicName)
    if nullvalList is not None and not isinstance(nullvalList, list):
        nullvalList = [nullvalList] * len(bandObjList)
    if nullvalList is None:
        nullvalList = [bandObjList[i].GetNoDataValue()
                   for i in range(len(bandObjList))]

    # Now fill each layer with its corresponding null value. We start with
    # zeros, so if any of the null values is None, it will fallback to zero
    outArray = numpy.zeros(shape, dtype=dtype)
    for i in range(len(nullvalList)):
        if nullvalList[i] is not None:
            outArray[i].fill(nullvalList[i])

    for i in range(nBands):
        readIntoArray(outArray[i], ds, bandObjList[i], top, left,
            xsize, ysize, workinggrid, margin)

    return outArray


def readIntoArray(outArray, ds, bandObj, top_wg, left_wg,
            xsize, ysize, workinggrid, margin):
    """
    Read the requested block from the given band/dataset, and place it
    into the given output array. If the block falls off the edge of the
    file extent, the request is trimmed back, and the resulting smaller
    block is placed into the correct part of the array, leaving the
    surrounding array elements unchanged.

    The request coordinates (top, left, xsize, ysize) do not include the
    margin (i.e. overlap), so that is accounted for explicitly here.
    If margin > 0, the array is thus larger by (2*margin) in each direction.

    NOTE: While it may seem that this could be done using a VRT, our tests
    of that approach found that it imposes a substantial overhead, and doing
    it ourselves is much faster. 

    """
    # The row/col shift between working grid and file grid. The shift
    # should be SUBTRACTED from working grid row/col to get file row/col
    fileTransform = ds.GetGeoTransform()
    file_xMin = fileTransform[0]
    file_yMax = fileTransform[3]
    (xRes, yRes) = (workinggrid.xRes, workinggrid.yRes)
    colShift = int(round((file_xMin - workinggrid.xMin) / xRes))
    rowShift = int(round((workinggrid.yMax - file_yMax) / yRes))

    # The file coordinates of the outer-most pixels, including the margin
    fileLeft = left_wg - margin - colShift
    fileRight = left_wg + (xsize - 1) + margin - colShift
    fileTop = top_wg - margin - rowShift
    fileBottom = top_wg + (ysize - 1) + margin - rowShift

    # The number of rows/cols outside file extent in each direction, which
    # thus need to be trimmed off the array to actually read
    trimLeft = max(0, -fileLeft)
    trimRight = max(0, (fileRight + 1 - ds.RasterXSize))
    trimTop = max(0, -fileTop)
    trimBottom = max(0, (fileBottom + 1 - ds.RasterYSize))

    # Specify what to actually read
    left_read = fileLeft + trimLeft
    top_read = fileTop + trimTop
    xsize_read = fileRight + 1 - left_read - trimRight
    ysize_read = fileBottom + 1 - top_read - trimBottom

    if left_read >= 0 and top_read >= 0 and xsize_read > 0 and ysize_read > 0:
        subArr = bandObj.ReadAsArray(left_read, top_read, xsize_read, ysize_read)
        (subRows, subCols) = subArr.shape
        i1 = trimTop
        i2 = trimTop + subRows
        j1 = trimLeft
        j2 = trimLeft + subCols
        outArray[i1:i2, j1:j2] = subArr


def openForWorkingGrid(filename, workinggrid, fileInfo, controls,
        tmpfileMgr, rasterizeMgr, symbolicName):
    """
    If the fileInfo for the given filename is a raster, aligned with
    the working grid, just open it. If it is a raster, but not aligned,
    do a warp VRT that makes it aligned, and open that instead.
    If it is a vector, then first rasterize into a temp file and use that.

    Either way, return a GDAL Dataset object and a list of band objects
    corresponding to the selected bands.

    """
    (xRes, yRes) = (workinggrid.xRes, abs(workinggrid.yRes))

    # If the file is actually a vector, then first rasterize it
    # onto the right pixel size. If it is the wrong projection, it will
    # be reprojected in raster form later on
    if isinstance(fileInfo, VectorFileInfo):
        vectorlayer = controls.getOptionForImagename('vectorlayer',
                symbolicName)

        if isinstance(vectorlayer, int):
            vecNdx = vectorlayer
        else:
            vecNdx = None
            for i in range(fileInfo.layerCount):
                if fileInfo[i].name == vectorlayer:
                    vecNdx = i
            if vecNdx is None:
                raise ValueError("Named vector layer '{}' not found".format(
                    vectorlayer))
        vecName = fileInfo[vecNdx].name

        vecLyrInfo = fileInfo[vecNdx]
        projection = vecLyrInfo.spatialRef.ExportToWkt()
        wgXmin = workinggrid.xMin
        wgYmin = workinggrid.yMin

        # Work out a resolution for the rasterized vector. Try to keep it
        # the same (or similar) to the working grid resolution
        wgSpatialRef = osr.SpatialReference()
        wgSpatialRef.ImportFromWkt(workinggrid.projection)
        (nrows, ncols) = workinggrid.getDimensions()
        wgCtrX = wgXmin + xRes * (ncols // 2)   # Rough centre of grid
        wgCtrY = wgYmin + yRes * (nrows // 2)
        (xRes_vec, yRes_vec) = reprojResolution(xRes, yRes,
            wgCtrX, wgCtrY, wgSpatialRef, vecLyrInfo.spatialRef)

        xMin = PixelGridDefn.snapToGrid(vecLyrInfo.xMin, wgXmin, xRes_vec) - xRes_vec
        xMax = PixelGridDefn.snapToGrid(vecLyrInfo.xMax, wgXmin, xRes_vec) + xRes_vec
        yMin = PixelGridDefn.snapToGrid(vecLyrInfo.yMin, wgYmin, yRes_vec) - yRes_vec
        yMax = PixelGridDefn.snapToGrid(vecLyrInfo.yMax, wgYmin, yRes_vec) + yRes_vec
        vectorPixgrid = PixelGridDefn(projection=projection,
            xMin=xMin, xMax=xMax, yMin=yMin, yMax=yMax,
            xRes=xRes_vec, yRes=yRes_vec)
        gridList = [workinggrid, vectorPixgrid]
        try:
            commonRegion = findCommonRegion(gridList, vectorPixgrid,
                combine=imageio.INTERSECTION)
        except rioserrors.IntersectionError:
            commonRegion = None
        dtype = controls.getOptionForImagename('vectordatatype', symbolicName)
        gdalDtype = gdal_array.NumericTypeCodeToGDALTypeCode(dtype)
        gtiffOptions = ['TILED=YES', 'COMPRESS=DEFLATE', 'BIGTIFF=IF_SAFER']
        if commonRegion is not None:
            outBounds = (commonRegion.xMin, commonRegion.yMin,
                commonRegion.xMax, commonRegion.yMax)
        else:
            outBounds = (wgCtrX, wgCtrY, wgCtrX + xRes_vec, wgCtrY + yRes_vec)
        vecNull = controls.getOptionForImagename('vectornull', symbolicName)
        burnattribute = controls.getOptionForImagename('burnattribute',
                symbolicName)
        burnvalue = None
        if burnattribute is None:
            burnvalue = controls.getOptionForImagename('burnvalue',
                    symbolicName)
        alltouched = controls.getOptionForImagename('alltouched',
                    symbolicName)
        filtersql = controls.getOptionForImagename('filtersql', symbolicName)
        rasterizeOptions = gdal.RasterizeOptions(format='GTiff',
            outputType=gdalDtype, creationOptions=gtiffOptions,
            outputBounds=outBounds, xRes=xRes_vec, yRes=yRes_vec, noData=vecNull,
            initValues=vecNull, burnValues=burnvalue, attribute=burnattribute,
            allTouched=alltouched, SQLStatement=filtersql, layers=vecName)

        tmprast = rasterizeMgr.rasterize(filename, rasterizeOptions,
                tmpfileMgr)
        filename = tmprast
        fileInfo = ImageInfo(filename)

    fileToOpen = filename

    if reprojectionRequired(fileInfo, workinggrid):
        vrtfile = tmpfileMgr.mktempfile(prefix='rios_', suffix='.vrt')

        srcProj = specialProjFixes(fileInfo.projection)
        dstProj = specialProjFixes(workinggrid.projection)
        if VersionObj(gdal.__version__) >= VersionObj('3.8.0'):
            # We restrict the extent of the reprojection VRT to the reprojected
            # extent of the underlying raster
            corners = fileInfo.getCorners(outWKT=dstProj)
            (ul_x, ul_y, ur_x, ur_y, lr_x, lr_y, ll_x, ll_y) = corners
            (xRes, yRes) = (workinggrid.xRes, workinggrid.yRes)
            xMin = min(ul_x, ll_x) - xRes
            xMax = max(ur_x, lr_x) + xRes
            yMin = min(ll_y, lr_y) - yRes
            yMax = max(ul_y, ur_y) + yRes
            xMin = PixelGridDefn.snapToGrid(xMin, workinggrid.xMin, xRes)
            xMax = PixelGridDefn.snapToGrid(xMax, workinggrid.xMin, xRes)
            yMin = PixelGridDefn.snapToGrid(yMin, workinggrid.yMin, yRes)
            yMax = PixelGridDefn.snapToGrid(yMax, workinggrid.yMin, yRes)
            filePixGrid = PixelGridDefn(projection=dstProj, xMin=xMin, yMin=yMin,
                xMax=xMax, yMax=yMax, xRes=xRes, yRes=yRes)

            # Make a pixgrid of the intersection between file grid and
            # working grid
            intersectGrid = workinggrid.intersection(filePixGrid)

            # The bounds of the VRT are from the intersection
            outBounds = (intersectGrid.xMin, intersectGrid.yMin,
                intersectGrid.xMax, intersectGrid.yMax)
        else:
            # In older versions of GDAL, there is some subtle interaction with
            # VRT and block size and extent, which can lead to severe
            # performance degradation when the above approach is used to limit
            # the extent of the VRT. So, for those older GDAL versions, we use
            # a simpler approach where the VRT extent is always identical
            # to the working grid. This also has a small performance penalty,
            # but much less severe, and so seems safer.
            outBounds = (workinggrid.xMin, workinggrid.yMin,
                workinggrid.xMax, workinggrid.yMax)

        # Work out what null value(s) to use, honouring anything set
        # with controls.setInputNoDataValue().
        nullvalList = controls.getOptionForImagename('inputnodata',
                symbolicName)
        if nullvalList is not None and not isinstance(nullvalList, list):
            # Turn a scalar into a list, one for each band in the file
            nullvalList = [nullvalList] * fileInfo.rasterCount
        # If we have None from controls, then use whatever is
        # specified on fileInfo
        if nullvalList is None:
            nullvalList = fileInfo.nodataval

        # The WarpOptions constructor has weird expectations about the
        # null values, so construct what it requires. It accepts other
        # forms, but they result in performance penalties, sometimes
        # quite severe. Not sure if this is the best form, but it is the
        # best I could find.
        if all([n is None for n in nullvalList]):
            nullval = None
        else:
            nullval = ' '.join([repr(n) for n in nullvalList])

        overviewLevel = 'NONE'
        if controls.getOptionForImagename('allowOverviewsGdalwarp',
                symbolicName):
            overviewLevel = 'AUTO'
        resampleMethod = controls.getOptionForImagename('resampleMethod',
            symbolicName)
        warpOptions = gdal.WarpOptions(format="VRT", outputBounds=outBounds,
            xRes=xRes, yRes=yRes, srcNodata=nullval, srcSRS=srcProj,
            dstSRS=dstProj, dstNodata=nullval, overviewLevel=overviewLevel,
            resampleAlg=resampleMethod)
        # Have to remove the vrtfile, because gdal.Warp won't over-write.
        os.remove(vrtfile)
        gdal.Warp(vrtfile, filename, options=warpOptions)
        fileToOpen = vrtfile

    ds = gdal.Open(fileToOpen)
    layerselection = controls.getOptionForImagename('layerselection',
            symbolicName)
    if layerselection is None:
        # Default to all bands
        layerselection = [(i + 1) for i in range(ds.RasterCount)]

    bandObjList = [ds.GetRasterBand(i) for i in layerselection]

    return (ds, bandObjList)


def reprojectionRequired(imgInfo, workinggrid):
    """
    Compare the details of the given imgInfo and the workinggrid,
    to work out if a reprojection is required. Return True if so.
    """
    proj = specialProjFixes(imgInfo.projection)
    pixGrid = PixelGridDefn(projection=proj,
        xMin=imgInfo.xMin, xMax=imgInfo.xMax, xRes=imgInfo.xRes,
        yMin=imgInfo.yMin, yMax=imgInfo.yMax, yRes=imgInfo.yRes)

    allEqual = (workinggrid.equalPixSize(pixGrid) and
                workinggrid.equalProjection(pixGrid) and
                workinggrid.alignedWith(pixGrid))
    reprojReqd = not allEqual
    return reprojReqd


def specialProjFixes(projwkt):
    """
    Does any special fixes required for the projection. Returns the fixed
    projection WKT string.

    Specifically this does two things, both of which are to cope with rubbish
    that Imagine has put into the projection. Firstly, it removes the
    crappy TOWGS84 parameters which Imagine uses for GDA94, and secondly
    removes the crappy name which Imagine gives to the correct GDA94.

    If neither of these things is found, returns the string unchanged.

    """
    dodgyTOWGSstring = "TOWGS84[-16.237,3.51,9.939,1.4157e-06,2.1477e-06,1.3429e-06,1.91e-07]"
    properTOWGSstring = "TOWGS84[0,0,0,0,0,0,0]"
    if projwkt.find('"GDA94"') > 0 or projwkt.find('"Geocentric_Datum_of_Australia_1994"') > 0:
        newWkt = projwkt.replace(dodgyTOWGSstring, properTOWGSstring)
    else:
        newWkt = projwkt

    # Imagine's name for the correct GDA94 also causes problems, so
    # replace it with something more standard.
    newWkt = newWkt.replace('GDA94-ICSM', 'GDA94')

    return newWkt


def reprojResolution(xRes, yRes, x, y, srcSRS, tgtSRS):
    """
    Return a reprojected version of the given resolution. The (xRes yRes)
    values are given in the srcSRS project, and are translated to something
    as similar as possible in the tgtSRS projection. The rough location
    is given by (x, y) (in the src projection), so the transformation is
    at its best around that point, and would be progressively worse the
    further one gets from there (due to the increased distortion from the
    different projections).

    """
    t = osr.CoordinateTransformation(srcSRS, tgtSRS)
    (tl_x, tl_y, z) = t.TransformPoint(x, y)
    (tr_x, tr_y, z) = t.TransformPoint(x + xRes, y)
    (bl_x, bl_y, z) = t.TransformPoint(x, y - yRes)
    tgtXres = tr_x - tl_x
    tgtYres = tl_y - bl_y
    return (tgtXres, tgtYres)


class ReadWorkerMgr:
    """
    Simple class to hold all the things we need to sustain for
    the read worker threads
    """
    def __init__(self):
        self.threadPool = None
        self.workerList = None
        self.readTaskQue = None
        self.forceExit = None
        self.isActive = False

    def startReadWorkers(self, blockList, infiles, allInfo, controls,
            tmpfileMgr, rasterizeMgr, workinggrid, inBlockBuffer, timings,
            exceptionQue):
        """
        Start the requested number of read worker threads, within the current
        process. All threads will read single blocks from individual files
        and place them into the inBlockBuffer.

        Return value is an instance of ReadWorkerMgr, which must remain
        active until all reading is complete.

        """
        numWorkers = controls.concurrency.numReadWorkers
        threadPool = futures.ThreadPoolExecutor(max_workers=numWorkers)
        readTaskQue = queue.Queue()

        # Put all read tasks into the queue. A single task is one block of
        # input for one input file.
        for blockDefn in blockList:
            for (symName, seqNum, filename) in infiles:
                task = (blockDefn, symName, seqNum, filename)
                readTaskQue.put(task)

        workerList = []
        forceExit = threading.Event()
        for i in range(numWorkers):
            worker = threadPool.submit(self.readWorkerFunc, readTaskQue,
                inBlockBuffer, controls, tmpfileMgr, rasterizeMgr, workinggrid,
                allInfo, timings, forceExit, exceptionQue)
            workerList.append(worker)

        self.threadPool = threadPool
        self.workerList = workerList
        self.readTaskQue = readTaskQue
        self.forceExit = forceExit
        self.isActive = True

    @staticmethod
    def readWorkerFunc(readTaskQue, blockBuffer, controls, tmpfileMgr,
            rasterizeMgr, workinggrid, allInfo, timings, forceExit,
            exceptionQue):
        """
        This function runs in each read worker thread. The readTaskQue gives
        it tasks to perform (i.e. single blocks of data to read), and it loops
        until there are no more to do. Each block is sent back through
        the blockBuffer.

        """
        # Each instance of this readWorkerFunc has its own set of GDAL objects,
        # as these cannot be shared between threads.
        gdalObjCache = {}

        try:
            try:
                readTask = readTaskQue.get(block=False)
            except queue.Empty:
                readTask = None
            while readTask is not None and not forceExit.is_set():
                (blockDefn, symName, seqNum, filename) = readTask
                with timings.interval('reading'):
                    arr = readBlockOneFile(blockDefn, symName, seqNum,
                        filename, gdalObjCache, controls, tmpfileMgr,
                        rasterizeMgr, workinggrid, allInfo)

                with timings.interval('insert_readbuffer'):
                    blockBuffer.addBlockData(blockDefn, symName, seqNum, arr)

                try:
                    readTask = readTaskQue.get(block=False)
                except queue.Empty:
                    readTask = None
        except Exception as e:
            exceptionRecord = WorkerErrorRecord(e, 'read')
            exceptionQue.put(exceptionRecord)

    def shutdown(self):
        """
        Shut down the read worker manager
        """
        self.forceExit.set()
        self.threadPool.shutdown()
        self.isActive = False

    def __del__(self):
        "Destructor"
        if self.isActive:
            # If we have not already done shutdown, then do it
            self.shutdown()


# WARNING
# WARNING
# WARNING
# WARNING
# WARNING       All code below this point is deprecated (v2.0.0)
# WARNING
# WARNING
# WARNING
# WARNING


class ImageIterator(object):
    """
    Class to allow iteration across an ImageReader instance.
    Do not instantiate this class directly - it is created
    by ImageReader.__iter__().
    
    See http://docs.python.org/library/stdtypes.html#typeiter
    for a description of how this works. There is another way,
    see: http://docs.python.org/reference/expressions.html#yieldexpr
    but it seemed too much like Windows 3.1 programming which
    scared me!
    
    Returns a tuple containing an ReaderInfo class, plus a numpy
    array for each iteration
    
    """
    def __init__(self, reader):
        # reader = an ImageReader instance
        self.reader = reader
        self.nblock = 0  # start at first block
        
    def __iter__(self):
        # For iteration support - just return self.
        return self

    def next(self):
        # for Python 2.x
        return self.__next__()
        
    def __next__(self):
        # for iteration support. Raises a StopIteration
        # if we have read beyond the end of the image
        try:
            # get ImageReader.readBlock() to do the work
            # this raises a OutsideImageBounds exception,
            # but the iteration protocol expects a 
            # StopIteration exception.
            returnTuple = self.reader.readBlock(self.nblock)
        except rioserrors.OutsideImageBoundsError:
            raise StopIteration()
            
        # look at the next block next time
        self.nblock += 1
        
        return returnTuple


class ImageReader(object):
    """
    Class that reads a single file, a list or dictionary of files and 
    iterates through them block by block

    **Example**
    
    ::
    
        import sys
        from rios.imagereader import ImageReader

        reader = ImageReader(sys.argv[1]) 
        for (info, block) in reader:     
            block2 = block * 2

    """
    def __init__(self, imageContainer,
            footprint=DEFAULTFOOTPRINT,
            windowxsize=DEFAULTWINDOWXSIZE, windowysize=DEFAULTWINDOWYSIZE,
            overlap=DEFAULTOVERLAP, 
            loggingstream=sys.stdout, layerselection=None):
        """
        imageContainer is a filename or list or dictionary that contains
        the filenames of the images to be read.
        If a list is passed, a list of blocks is returned at 
        each iteration, if a dictionary a dictionary is
        returned at each iteration with the same keys.
        
        footprint can be either INTERSECTION, UNION or BOUNDS_FROM_REFERENCE
        
        windowxsize and windowysize specify the size
        of the block to be read at each iteration
        
        overlap specifies the number of pixels to overlap
        between each block
        
        Set loggingstream to a file like object if you wish
        logging about resampling to be sent somewhere else
        rather than stdout.
        
        layerselection, if given, should be of the same type as imageContainer, 
        that is, if imageContainer is a dictionary, then layerselection 
        should be a dictionary with the same keys, and if imageContainer 
        is a list, then layerselection should be a list of the same length. 
        The elements in layerselection should always be lists of layer numbers, 
        used to select only particular layers to read from the corresponding 
        input image. Layer numbers use GDAL conventions, i.e. start at 1. 
        Default reads all layers. 
        
        """
        msg = "The ImageReader class is now deprecated (v2.0.0)"
        rioserrors.deprecationWarning(msg)

        # grab the imageContainer so we can always know what 
        # type of container they passed in
        self.imageContainer = imageContainer
      
        if isinstance(imageContainer, dict):
            # Convert the given imageContainer into a list suitable for
            # the standard InputCollection. 
            imageList = []
            self.layerselectionList = []
            # The image names, in a fixed order, so that everything can use the same order. 
            self.imagenamesOrdered = sorted(imageContainer.keys())
            
            for name in self.imagenamesOrdered:
                filename = imageContainer[name]
                if isinstance(filename, list):
                    # We have actually been given a list of filenames, so tack then all on to the imageList
                    imageList.extend(filename)
                elif isinstance(filename, basestring):
                    # We just have a single filename
                    imageList.append(filename)
                else:
                    msg = "Dictionary must contain either lists or strings. Got '%s' instead" % type(filename)
                    raise rioserrors.ParameterError(msg)

                # Layer selection for this filename. 
                thisLayerSelection = None
                if layerselection is not None and name in layerselection:
                    thisLayerSelection = layerselection[name]

                if isinstance(filename, list):
                    self.layerselectionList.extend([thisLayerSelection for fn in filename])
                else:
                    self.layerselectionList.append(thisLayerSelection)

        elif isinstance(imageContainer, basestring):
            # they passed a string, just make a list out of it
            imageList = [imageContainer]
            if layerselection is not None:
                self.layerselectionList = [layerselection]
            else:
                self.layerselectionList = [None]
        else:
            # we hope they passed a tuple or list. Don't need to do much
            imageList = imageContainer
            if layerselection is not None:
                self.layerselectionList = layerselection
            else:
                self.layerselectionList = [None for fn in imageList]
        
        # create an InputCollection with our inputs
        self.inputs = inputcollection.InputCollection(imageList, loggingstream=loggingstream)
        
        # save the other vars
        self.footprint = footprint
        self.windowxsize = windowxsize
        self.windowysize = windowysize
        self.overlap = overlap
        self.loggingstream = loggingstream
        
        # these are None until prepare() is called
        self.workingGrid = None
        self.info = None

    def __len__(self):
        # see http://docs.python.org/reference/datamodel.html#emulating-container-types
        
        # need self.info to be created so run prepare()
        if self.info is None:
            self.prepare()

        # get the total number of blocks for image            
        (xtotalblocks, ytotalblocks) = self.info.getTotalBlocks()
        
        # return the total number of blocks as our len()
        return xtotalblocks * ytotalblocks
        
    def __getitem__(self, key):
        # see http://docs.python.org/reference/datamodel.html#emulating-container-types
        # for indexing, returns tuple from readBlock()

        # need self.info to be created so run prepare()
        if self.info is None:
            self.prepare()

        # if they have passed a negative block - count
        # back from the end           
        if key < 0:
            # get total number of blocks
            (xtotalblocks, ytotalblocks) = self.info.getTotalBlocks()
            # add the key (remember, its negative)
            key = (xtotalblocks * ytotalblocks) + key
            if key < 0:
                # still negative - not enough blocks
                raise KeyError()
        
        try:
            # get readBlock() to do the work
            # this raises a OutsideImageBounds exception,
            # but the container protocol expects a 
            # KeyError exception.
            returnTuple = self.readBlock(key)
        except rioserrors.OutsideImageBoundsError:
            raise KeyError()
            
        return returnTuple

    def __iter__(self):
        # see http://docs.python.org/reference/datamodel.html#emulating-container-types

        # need self.info to be created so run prepare()
        if self.info is None:
            self.prepare()

        # return in ImageIterator instance
        # with a reference to this object            
        return ImageIterator(self)

    def allowResample(self, resamplemethod="near", refpath=None, refgeotrans=None, 
            refproj=None, refNCols=None, refNRows=None, refPixgrid=None, 
            tempdir='.', useVRT=False, allowOverviewsGdalwarp=False):
        """
        By default, resampling is disabled (all datasets must
        match). Calling this enables it. 
        Either refgeotrans, refproj, refNCols and refNRows must be passed, 
        or refpath passed and the info read from that file.

        tempdir is the temporary directory where the resampling happens. By 
        default the current directory.

        resamplemethod is the method used - must be supported by gdalwarp.
        This can be a single string if all files are to be resampled by the
        same method, or a list or dictionary (to match what passed to the 
        constructor) contain the methods for each file.
        
        If resampling is needed it will happen before the call returns.
        
        """
        # set the reference in our InputCollection
        self.inputs.setReference(refpath, refgeotrans, refproj,
                refNCols, refNRows, refPixgrid)
             
        if isinstance(resamplemethod, basestring):
            # turn it into a list with the same method repeated
            resamplemethodlist = [resamplemethod] * len(self.inputs)
        elif isinstance(resamplemethod, dict):
            # dictionary - check they passed a dictionary to the constructor
            # and the keys match
            if not isinstance(self.imageContainer, dict):
                msg = 'Can only pass a dictionary if a dictionary passed to the constructor'
                raise rioserrors.ParameterError(msg)
            elif sorted(self.imageContainer.keys()) != sorted(resamplemethod.keys()):
                msg = ('Dictionary keys must match those passed to the constructor, '+
                    'constructor keys = %s, resample keys = %s') % (self.imageContainer.keys(),
                    resamplemethod.keys())
                raise rioserrors.ParameterError(msg)
            else:
                # create a list out of the dictionary in the same way as the constructor does
                resamplemethodlist = []
                for name in self.imagenamesOrdered:
                    method = resamplemethod[name]
                    if isinstance(method, list):
                        # We have actually been given a list of method, so tack then all on to the resamplemethodlist
                        resamplemethodlist.extend(method)
                    elif isinstance(method, basestring):
                        # We just have a single method
                        resamplemethodlist.append(method)
                    else:
                        msg = "Dictionary must contain either lists or strings. Got '%s' instead" % type(method)
                        raise rioserrors.ParameterError(msg)

        else:
            # we assume they have passed a list/tuple
            if len(resamplemethod) != len(self.inputs):
                msg = 'must pass correct number of resample methods'
                raise rioserrors.ParameterError(msg)
            resamplemethodlist = resamplemethod

        try:   
            # resample all in collection to reference
            self.inputs.resampleAllToReference(self.footprint, resamplemethodlist, tempdir, useVRT,
                allowOverviewsGdalwarp)
        finally:
            # if the user interrupted, then ensure all temp
            # files removed.
            self.inputs.cleanup()
        
    def prepare(self, workingGrid=None):
        """
        Prepare to read from images. These steps are not
        done in the constructor, but are done just before
        reading in case allowResample() is called which
        will resample the inputs.
        
        The pixelGrid instance to use as the working grid can
        be passed in case it is not to be derived from the images
        to be read or is different from that passed to allowResample
        """
    
        # if resampled has happened then they should all match
        if not self.inputs.checkAllMatch():
            msg = 'Inputs do not match - must enable resampling'
            raise rioserrors.ResampleNeededError(msg)
        
        if workingGrid is None:
            # set the working grid based on the footprint
            self.workingGrid = self.inputs.findWorkingRegion(self.footprint)
        else:
            # user supplied
            self.workingGrid = workingGrid
        
        # create a ReaderInfo class with the info it needs
        # a copy of this class is passed with each iteration
        self.info = readerinfo.ReaderInfo(self.workingGrid, 
                        self.windowxsize, self.windowysize, self.overlap, self.loggingstream)
        
    def readBlock(self, nblock):
        """
        Read a block. This is normally called from the
        __getitem__ method when this class is indexed, 
        or from the ImageIterator when this class is 
        being iterated through.
        
        A block is read from each image and returned
        in a tuple along with a ReaderInfo instance.
        
        nblock is a single index, and will be converted
        to row/column.
        
        """
        
        # need self.info to be created so run prepare()
        if self.info is None:
            self.prepare()
           
        # do a shallow copy of the ReaderInfo.
        # this copy will have the fields filled in
        # that relate to the whole image.
        # We will then fill in the fields that relate
        # to this block. 
        # This means that calls to read other blocks
        # wont clobber the per block info, and user 
        # writing back into the object wont stuff up
        # the system 
        info = copy.copy(self.info)
        
        # get the size of the are we are to read
        (xsize, ysize) = info.getTotalSize()
        
        # get the number of blocks are to read
        (xtotalblocks, ytotalblocks) = info.getTotalBlocks()
        
        # check they asked for block is valid
        if nblock >= (xtotalblocks * ytotalblocks):
            raise rioserrors.OutsideImageBoundsError()
        
        # convert the block to row/column
        yblock = nblock // xtotalblocks
        xblock = nblock % xtotalblocks
        
        # set this back to our copy of the info object
        info.setBlockCount(xblock, yblock)
    
        # calculate the coords of this block in pixels
        xcoord = xblock * self.windowxsize
        ycoord = yblock * self.windowysize
        
        # convert this to world coords
        blocktl = imageio.pix2wld(info.getTransform(), xcoord, ycoord)

        # work out the bottom right coord for this block
        nBlockBottomX = ((xblock + 1) * self.windowxsize)
        nBlockBottomY = ((yblock + 1) * self.windowysize)
        
        # make adjuctment if we are at the edge of the image
        # and there are smaller blocks
        if nBlockBottomX > xsize:
            nBlockBottomX = xsize
        if nBlockBottomY > ysize:
            nBlockBottomY = ysize

        # work out the world coords for the bottom right
        blockbr = imageio.pix2wld(info.getTransform(), nBlockBottomX, nBlockBottomY)
        
        # set this back to our copy of the info object
        info.setBlockBounds(blocktl, blockbr)

        # work out number of pixels of this block
        blockwidth = nBlockBottomX - xcoord
        blockheight = nBlockBottomY - ycoord
        
        # set this back to our copy of the info object
        info.setBlockSize(blockwidth, blockheight)
        
        # start creating our tuple. Start with an empty list
        # and append the blocks.
        blockList = []
        
        try:
            i = 0
            
            # read all the files using our iterable InputCollection
            for (image, ds, pixgrid, nullValList, datatype) in self.inputs:
            
                # get the pixel coords for this block for this file
                tl = imageio.wld2pix(pixgrid.makeGeoTransform(), blocktl.x, blocktl.y)
            
                # just read in the dataset (will return how many layers it has)
                # will just use the datatype of the image
                block = self.readBlockWithMargin(ds, int(round(tl.x)), int(round(tl.y)),
                    blockwidth, blockheight, datatype, margin=self.overlap, 
                    nullValList=nullValList, 
                    layerselection=self.layerselectionList[i])

                # add this block to our list
                blockList.append(block)
                
                i += 1
                
        finally:
            # if there is any exception thrown here, make
            # sure temporary resampled files are deleted.
            # doesn't seem the destructor is called in this case.
            self.inputs.cleanup()

        if isinstance(self.imageContainer, dict):
            # we need to use the original keys passed in
            # to the constructor and return a dictionary
            blockDict = {}
            i = 0
            for name in self.imagenamesOrdered:
                filename = self.imageContainer[name]
                if isinstance(filename, list):
                    listLen = len(filename)
                    blockDict[name] = []
                    for j in range(listLen):
                        blockDict[name].append(blockList[i])
                        i += 1
                elif isinstance(filename, basestring):
                    blockDict[name] = blockList[i]
                    i += 1
                                    
            # blockContainer is a dictionary
            blockContainer = blockDict
         
        elif isinstance(self.imageContainer, basestring):
            # blockContainer is just a single block
            blockContainer = blockList[0]

        else:   
            # blockContainer is a tuple
            blockContainer = tuple(blockList)
            
        # return a tuple with the info object and
        # our blockContainer
        return (info, blockContainer)

    @staticmethod
    def readBlockWithMargin(ds, xoff, yoff, xsize, ysize, datatype, margin=0, nullValList=None,
            layerselection=None):
        """
        A 'drop-in' look-alike for the ReadAsArray function in GDAL,
        but with the option of specifying a margin width, such that
        the block actually read and returned will be larger by that many pixels. 
        The returned array will ALWAYS contain these extra rows/cols, and 
        if they do not exist in the file (e.g. because the margin would push off 
        the edge of the file) then they will be filled with the given nullVal. 
        Otherwise they will be read from the file along with the rest of the block. 
        
        Variables within this function which have _margin as suffix are intended to 
        designate variables which include the margin, as opposed to those without. 
        
        This routine will cope with any specified region, even if it is entirely outside
        the given raster. The returned block would, in that case, be filled
        entirely with the null value. 
        
        """
        if layerselection is None:
            layerselection = [i + 1 for i in range(ds.RasterCount)]
        nLayers = len(layerselection)
        
        # Create the final array, with margin, but filled with the null value. 
        xSize_margin = xsize + 2 * margin
        ySize_margin = ysize + 2 * margin
        outBlockShape = (nLayers, ySize_margin, xSize_margin)
        
        # Create the empty output array, filled with the appropriate null value. 
        block_margin = numpy.zeros(outBlockShape, dtype=datatype)
        if nullValList is not None and len(nullValList) > 0:
            # We really need something as a fill value, so if any of the 
            # null values in the list is None, then replace it with 0. 
            fillValList = [nullVal for nullVal in nullValList]
            for i in range(len(fillValList)):
                if fillValList[i] is None:
                    fillValList[i] = 0
            # Now use the appropriate null value for each layer as the 
            # initial value in the output array for the block. 
            if len(outBlockShape) == 2:
                block_margin.fill(fillValList[0])
            else:
                for i in range(nLayers):
                    block_margin[i].fill(fillValList[layerselection[i] - 1])
#                for (i, fillVal) in enumerate(fillValList):
#                    block_margin[i].fill(fillVal)

        # Calculate the bounds of the block which we will actually read from the file,
        # based on what we have been asked for, what margin size, and how close we
        # are to the edge of the file. 
        
        # The bounds of the whole image in the file
        imgLeftBound = 0
        imgTopBound = 0
        imgRightBound = ds.RasterXSize
        imgBottomBound = ds.RasterYSize
        
        # The region we will, in principle, read from the file. Note that xSize_margin 
        # and ySize_margin are already calculated above
        xoff_margin = xoff - margin
        yoff_margin = yoff - margin
        
        # Restrict this to what is available in the file
        xoff_margin_file = max(xoff_margin, imgLeftBound)
        xoff_margin_file = min(xoff_margin_file, imgRightBound)
        xright_margin_file = xoff_margin + xSize_margin
        xright_margin_file = min(xright_margin_file, imgRightBound)
        xSize_margin_file = xright_margin_file - xoff_margin_file

        yoff_margin_file = max(yoff_margin, imgTopBound)
        yoff_margin_file = min(yoff_margin_file, imgBottomBound)
        ySize_margin_file = min(ySize_margin, imgBottomBound - yoff_margin_file)
        ybottom_margin_file = yoff_margin + ySize_margin
        ybottom_margin_file = min(ybottom_margin_file, imgBottomBound)
        ySize_margin_file = ybottom_margin_file - yoff_margin_file
        
        # How many pixels on each edge of the block we end up NOT reading from 
        # the file, and thus have to leave as null in the array
        notRead_left = xoff_margin_file - xoff_margin
        notRead_right = xSize_margin - (notRead_left + xSize_margin_file)
        notRead_top = yoff_margin_file - yoff_margin
        notRead_bottom = ySize_margin - (notRead_top + ySize_margin_file)
        
        # The upper bounds on the slices specified to receive the data
        slice_right = xSize_margin - notRead_right
        slice_bottom = ySize_margin - notRead_bottom
        
        if xSize_margin_file > 0 and ySize_margin_file > 0:
            # Now read in the part of the array which we can actually read from the file.
            # Read each layer separately, to honour the layerselection
            
            # The part of the final array we are filling
            imageSlice = (slice(notRead_top, slice_bottom), slice(notRead_left, slice_right))
            
            for i in range(nLayers):
                band = ds.GetRasterBand(layerselection[i])
                block_margin[i][imageSlice] = band.ReadAsArray(xoff_margin_file, yoff_margin_file, 
                    xSize_margin_file, ySize_margin_file)

        return block_margin
        
    def close(self):
        """
        Closes all open datasets
        """
        self.inputs.close()
