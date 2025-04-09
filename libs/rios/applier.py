"""
Basic tools for setting up a function to be applied over 
a raster processing chain. The :func:`rios.applier.apply` function is the main
point of entry in this module. 

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
import queue

import numpy
from osgeo import gdal

# Some symbols are imported to here for easy access by the user, even
# though they are not used in this module. Hence the "# noqa: F401"
from . import rioserrors
from .imagereader import DEFAULTFOOTPRINT, DEFAULTWINDOWXSIZE
from .imagereader import DEFAULTWINDOWYSIZE, DEFAULTOVERLAP
from .imagereader import DEFAULTLOGGINGSTREAM                         # noqa: F401
from .imagereader import readBlockAllFiles, ReadWorkerMgr, specialProjFixes
from .imagewriter import DEFAULTDRIVERNAME, DEFAULTCREATIONOPTIONS    # noqa: F401
from .imagewriter import writeBlock, closeOutfiles, dfltDriverOptions  # noqa: F401
from .imageio import INTERSECTION, UNION, BOUNDS_FROM_REFERENCE       # noqa: F401
from .calcstats import DEFAULT_OVERVIEWLEVELS, DEFAULT_MINOVERVIEWDIM
from .calcstats import DEFAULT_OVERVIEWAGGREGRATIONTYPE               # noqa: F401
from .calcstats import SinglePassManager
from .rat import DEFAULT_AUTOCOLORTABLETYPE
from .structures import FilenameAssociations, BlockAssociations, OtherInputs  # noqa: F401
from .structures import BlockBuffer, Timers, TempfileManager, ApplierReturn
from .structures import ApplierBlockDefn, RasterizationMgr, WorkerErrorRecord
from .structures import CW_NONE, CW_THREADS, CW_PBS, CW_SLURM, CW_AWSBATCH
from .structures import CW_SUBPROC                                    # noqa: F401
from .structures import ConcurrencyStyle
from .fileinfo import ImageInfo, VectorFileInfo
from .pixelgrid import PixelGridDefn, findCommonRegion
from .readerinfo import makeReaderInfo
from .computemanager import getComputeWorkerManager


DEFAULT_RESAMPLEMETHOD = "near"


class ApplierControls(object):
    """
    Controls for the operation of rios, for use with 
    the :func:`rios.applier.apply` function. 
    
    This object starts with default values for all controls, and 
    has methods for setting each of them to something else. 
    
    Default values are provided for all attributes, and can then be over-ridden
    with the 'set' methods given.

    Some 'set' methods take an optional imagename argument. If given, this shouldbe 
    the same internal name used for a given image as in the :class:`rios.structures.FilenameAssociations`
    objects. This is the internal name for that image, and the method will set
    the parameter in question for that specific image, which will over-ride the
    global value set when no imagename is given.

    Attributes are:
        * **windowxsize**     X size of rios block (pixels)
        * **windowysize**     Y size of rios block (pixels)
        * **overlap**         Number of pixels in margin for block overlaps
        * **footprint**       :data:`rios.applier.INTERSECTION` or :data:`rios.applier.UNION` or :data:`rios.applier.BOUNDS_FROM_REFERENCE`
        * **drivername**      GDAL driver short name for output
        * **creationoptions** GDAL creation options for output
        * **thematic**        True/False for thematic outputs
        * **layernames**      List of layer names for outputs
        * **referenceImage**  Image for reference projection and grid that inputs will be resampled to.
        * **referencePixgrid** pixelGrid for reference projection and grid
        * **loggingstream**   file-like for logging of messages
        * **progress**        progress object
        * **statsIgnore**     global stats ignore value for output (i.e. null value)
        * **inputnodata**     Over-ride of null value for input file, in reprojecting
        * **calcStats**       Obsolete. See setCalcStats() docstring
        * **omitPyramids**    Boolean to omit pyramid layers in outputs
        * **omitBasicStats**  Boolean to omit basic statistics in outputs
        * **omitHistogram**   Boolean to omit histogram in outputs
        * **overviewLevels**  List of level factors used when calculating output image overviews
        * **overviewMinDim**  Minimum dimension of highest overview level
        * **overviewAggType** Aggregation type for calculating overviews
        * **singlePassPyramids**    Boolean to do pyramids on outputs in a single pass
        * **singlePassBasicStats**  Boolean to do basic stats on outputs in a single pass
        * **singlePassHistogram**   Boolean to do histogram on outputs in a single pass
        * **tempdir**         Name of directory for temp files (resampling, etc.)
        * **resampleMethod**  String for resample method, when required (as per GDAL)
        * **numThreads**      Deprecated. Number of parallel threads used for processing each image block
        * **jobManagerType**  Deprecated. Which :class:`rios.parallel.jobmanager.JobManager` sub-class to use for parallel processing (by name)
        * **concurrency**     Instance of :class:`rios.structures.ConcurrencyStyle` (use instead of numThreads/jobManagerType)
        * **autoColorTableType** Type of color table to be automatically added to thematic output rasters
        * **allowOverviewsGdalwarp** Allow use of overviews in input resample (dangerous, do not use)
        * **approxStats**       Allow approx stats (much faster)
        * **layerselection**  List of selected layer numbers for input
        * **jobName**         String name for this job, for cosmetic use only
    
    Options relating to vector input files
        * **burnvalue**       Value to burn into raster from vector
        * **filtersql**       SQL where clause used to filter vector features
        * **alltouched**      Boolean. If True, all pixels touched are included in vector. 
        * **burnattribute**   Name of vector attribute used to supply burnvalue
        * **vectorlayer**     Number (or name) of vector layer
        * **vectordatatype**  Numpy datatype to use for raster created from vector
        * **vectornull**      Rasterised vector is initialised to this value, before burning
    
    """
    def __init__(self):
        self.loggingstream = sys.stdout
        self.drivername = DEFAULTDRIVERNAME
        self.overlap = DEFAULTOVERLAP
        self.windowxsize = DEFAULTWINDOWXSIZE
        self.windowysize = DEFAULTWINDOWYSIZE
        self.footprint = DEFAULTFOOTPRINT
        self.referenceImage = None
        self.referencePixgrid = None
        self.progress = None
        self.creationoptions = None
        self.statsIgnore = 0
        self.inputnodata = None
        self.calcStats = True
        self.omitPyramids = False
        self.omitBasicStats = False
        self.omitHistogram = False
        self.overviewLevels = DEFAULT_OVERVIEWLEVELS
        self.overviewMinDim = DEFAULT_MINOVERVIEWDIM
        self.overviewAggType = None
        self.singlePassPyramids = None
        self.singlePassBasicStats = None
        self.singlePassHistogram = None
        self.thematic = False
        self.layernames = None
        self.tempdir = '.'
        self.resampleMethod = DEFAULT_RESAMPLEMETHOD
        self.numThreads = 1
        self.jobManagerType = os.getenv('RIOS_DFLT_JOBMGRTYPE', default=None)
        self.concurrency = ConcurrencyStyle()
        self.autoColorTableType = DEFAULT_AUTOCOLORTABLETYPE
        self.allowOverviewsGdalwarp = False
        self.approxStats = False
        self.layerselection = None
        self.jobName = None

        # Vector fields
        self.burnvalue = 1
        self.vectornull = 0
        self.burnattribute = None
        self.filtersql = None
        self.alltouched = False
        self.vectordatatype = numpy.uint8
        self.vectorlayer = 0

        # Options specific to a named image. This was added on later, and is 
        # only valid for some of the attributes, so it looks a bit out-of-place.
        # Instead of the options being attributes of self, they are keys in a
        # dictionary. This dictionary is managed by the two methods
        # setOptionForImagename() and getOptionForImagename(). 
        self.optionsByImage = {}
    
    def setOptionForImagename(self, option, imagename, value):
        """
        Set the given option specifically for the given imagename. This 
        method is for internal use only. If you wish to set a particular 
        attribute, use the corresponding 'set' method. 
        """
        if imagename is None:
            setattr(self, option, value)
        else:
            if option not in self.optionsByImage:
                self.optionsByImage[option] = {}
            self.optionsByImage[option][imagename] = value
            
    def getOptionForImagename(self, option, imagename):
        """
        Returns the value of a particular option for the 
        given imagename. If only the global option has been set,
        then that is returned, but if a specific value has been set for 
        the given imagename, then use that. 
        
        The imagename is the same internal name as used for the image
        in the :class:`rios.structures.FilenameAssociations` objects. 
        
        """
        value = getattr(self, option)
        if option in self.optionsByImage:
            if imagename in self.optionsByImage[option]:
                value = self.optionsByImage[option][imagename]
        return value

    def _checks(self, infiles, outfiles):
        """
        Run a few simple checks on settings on the controls object.
        Raise an exception if an error is found.
        """
        # Check that the imagename arguments given are all found as symbolic
        # names on either infiles or outfiles
        for option in self.optionsByImage:
            for imagename in self.optionsByImage[option]:
                found = ((imagename in infiles) or (imagename in outfiles))
                if not found:
                    msg = ("For controls option '{}', symbolic name '{}' " +
                           "not found on infiles or outfiles")
                    msg = msg.format(option, imagename)
                    raise ValueError(msg)

        # Check output files for a number of conditions
        outImageList = [symbName for (symbName, seqNum, filename) in
            outfiles]
        outImageList = list(set(outImageList))
        for imagename in outImageList:
            thematic = self.getOptionForImagename('thematic', imagename)
            approxStats = self.getOptionForImagename('approxStats', imagename)
            omitPyramids = self.getOptionForImagename('omitPyramids', imagename)

            if thematic and approxStats:
                msg = ("Warning: Output image {} is thematic, and also " +
                       "uses approximate statistics. This is not " +
                       "recommended").format(imagename)
                print(msg, file=sys.stderr)

            if omitPyramids and approxStats:
                msg = ("Approximate stats requires pyramid layers, " +
                       "which have been omitted")
                raise ValueError(msg)

    def setLoggingStream(self, loggingstream):
        """
        Set the rios logging stream to the given file-like object.

        This is now deprecated (v2.0.0), and has no effect. The loggingstream
        is no longer used within RIOS.

        """
        msg = "The loggingstream is deprecated and ignored (v2.0.0)"
        rioserrors.deprecationWarning(msg)
        self.loggingstream = loggingstream
        
    def setOverlap(self, overlap):
        """
        Set the overlap to the given value.

        Overlap is a number of pixels, and is somewhat mis-named. It refers
        to the amount of margin added to each block of input, so that the
        blocks will overlap, hence the actual amount of overlap is really
        double this value.

        The margin can result in pixels which are outside the extent of
        the given input images. These pixels will be filled with the null
        value for that input file, or zero if no null value is set on
        that file.

        """
        self.overlap = overlap
        
    def setOutputDriverName(self, drivername, imagename=None):
        """
        Set the output driver name to the given GDAL shortname.
        
        Note that the GDAL creation options have defaults suitable only 
        for the default driver, so if one sets the output driver, then 
        the creation options should be reviewed too. 
        
        In more recent versions of RIOS, the addition of driver-specific
        default creation options ($RIOS_DFLT_CREOPT_<driver>) allows for
        multiple default creation options to be set up.
        
        """
        self.setOptionForImagename('drivername', imagename, drivername)
        
    def setWindowXsize(self, windowxsize):
        """
        Set the X size of the blocks used. Images are processed in 
        blocks (windows) of 'windowxsize' columns, and 'windowysize' rows. 
        """
        self.windowxsize = windowxsize
        
    def setWindowYsize(self, windowysize):
        """
        Set the Y size of the blocks used. Images are processed in 
        blocks (windows) of 'windowxsize' columns, and 'windowysize' rows. 
        """
        self.windowysize = windowysize
        
    def setWindowSize(self, windowxsize, windowysize):
        """
        Sets the X and Y size of the blocks used in one call.
        Images are processed in blocks (windows) of 'windowxsize' 
        columns, and 'windowysize' rows.

        New in version 1.4.17.

        """
        self.windowxsize = windowxsize
        self.windowysize = windowysize
        
    def setFootprintType(self, footprint):
        """
        Set type of footprint, one of INTERSECTION, UNION or 
        BOUNDS_FROM_REFERENCE from this module

        The footprint type controls the extent of the pixel grid
        used for calculation within the user function, and of the
        output files.

        Using INTERSECTION will result in the maximum extent which
        is wholly included in all of the input images. Using UNION results
        in the minimum extent which wholly includes all of the input
        images. If BOUNDS_FROM_REFERENCE is used, then the extent will
        be the same as that of the reference image or pixgrid, regardless
        of the extents of the various other inputs.

        For both UNION and BOUNDS_FROM_REFERENCE, it is possible to
        have pixels which are within the extent, but outside one or
        more of the input files. The input data for such pixels are filled
        with the null value for that file. If no null value is set for that
        file, then zero is used.

        """
        self.footprint = footprint
        
    def setReferenceImage(self, referenceImage):
        """
        Set the name of the image to use for the reference pixel grid and 
        projection. If neither referenceImage nor referencePixgrid are set, 
        then no resampling will be allowed. Only set one of referenceImage or
        referencePixgrid. 

        The reference image can be given as either the internal name, as given
        on infiles, or the external filename. The internal name is
        preferred, and consistent with other usage, but the filename is
        allowed for backward compatibility.

        """
        self.referenceImage = referenceImage
        
    def setReferencePixgrid(self, referencePixgrid):
        """
        Set the reference pixel grid. If neither referenceImage nor 
        referencePixgrid are set, then no resampling will be allowed. 
        Only set one of referenceImage or referencePixgrid. The referencePixgrid
        argument is of type :class:`rios.pixelgrid.PixelGridDefn`. 

        """
        self.referencePixgrid = referencePixgrid

    def setProgress(self, progress):
        """
        Set the progress display object. Default is no progress
        object.

        The progress object should be an instance of one of the classes
        from :class:`rios.cuiprogress`, and is used to generate a simple
        progress indicator showing the percentage completed.

        """
        self.progress = progress
        
    def setCreationOptions(self, creationoptions, imagename=None):
        """
        Set a list of GDAL creation options (should match with the driver). 
        Each list element is a string of the form "NAME=VALUE". 
        
        Defaults are suitable for the default driver, and need to be changed
        if that is changed. However, if an appropriate driver-specific default 
        environment variable ($RIOS_DFLT_CREOPT_<driver>) is given, this 
        will be used. 
        
        """
        self.setOptionForImagename('creationoptions', imagename, creationoptions)
        
    def setStatsIgnore(self, statsIgnore, imagename=None):
        """
        Set the 'no data' value for the output files (also known as the
        'null' value). This value will be written into the output files,
        and will thus be ignored when calculating statistics, histograms
        and overviews (pyramid layers) on those files.

        If this value is given as None, then no null value will be set on
        output files.

        If imagename is given, the setting will only apply to that image,
        otherwise it will apply to all output files.

        There is currently no mechanism to set different null values for
        different layers in an output file.

        The default value is 0. This was probably a bad idea, but to avoid
        breaking old scripts, we are not likely to change this.

        """
        self.setOptionForImagename('statsIgnore', imagename, statsIgnore)

    def setInputNoDataValue(self, nodataValue, imagename=None):
        """
        Set a 'no data' value for input file(s). This over-rides whatever
        null value may be defined within the file itself, and most importantly,
        will over-ride when the file does not have a null value set at all.

        The main reason this is important is when an input file does not
        have a null value, and is being reprojected on input. Since it has no
        null value, the resampling on the edge of any null value region in the
        image will risk blurring the nulls into the non-null area. Normally
        this is avoided if the file has a null value set. If the input file
        is not under the control of the user, then it cannot be set before
        reading, so this allows the user to over-ride it, and behave as though
        it had been set on the original file.

        If the supplied value is a single scalar, it will apply to all bands
        of the input, but if it is a list of values, they will apply
        per-band.

        If there is no reprojection on input, then this setting will have no
        effect on the data. However, it will be honoured by a call to
        info.getNoDataValueFor(), inside the user function (although that
        is itself discouraged).

        If the ``imagename`` parameter is used, then the setting will apply
        only to that input, otherwise it will be applied to all inputs.

        New in version 2.0.0

        """
        self.setOptionForImagename('inputnodata', imagename, nodataValue)
        
    def setCalcStats(self, calcStats, imagename=None):
        """
        From version 2.0.5, this is now obsolete.

        The default behaviour is to calculate pyramid layers, basic statistics,
        and histogram on all outputs. To omit any of these, call the
        associated controls method (setOmitPyramids, setOmitBasicStats,
        or setOmitHistogram).

        In earlier versions, these were all controlled with a call to this
        method. It is now preferred that these omit methods be called
        individually. The setCalcStats method now emulates the old behaviour,
        but will probably be deprecated in some future version, and
        eventually removed.

        """
        self.setOmitPyramids((not calcStats), imagename=imagename)
        self.setOmitBasicStats((not calcStats), imagename=imagename)
        self.setOmitHistogram((not calcStats), imagename=imagename)

    def setOmitPyramids(self, omitPyramids, imagename=None):
        """
        The default behaviour is to calculate pyramid layers (i.e. overviews)
        on all output images. To omit these, call setOmitPyramids(True). 

        If imagename is given, it should be a symbolic name as used on
        the outfiles object, and this setting will apply only to that
        image.

        New in version 1.1.2.

        """
        self.setOptionForImagename('omitPyramids', imagename, omitPyramids)
    
    def setOmitBasicStats(self, omitBasicStats, imagename=None):
        """
        The default behaviour is to calculate basic statistics
        on all output images. To omit these, call setOmitBasicStats(True).

        If imagename is given, it should be a symbolic name as used on
        the outfiles object, and this setting will apply only to that
        image.

        New in version 2.0.5.

        """
        self.setOptionForImagename('omitBasicStats', imagename, omitBasicStats)

    def setOmitHistogram(self, omitHistogram, imagename=None):
        """
        The default behaviour is to calculate image histograms
        on all output images. To omit these, call setOmitHistogram(True).

        If imagename is given, it should be a symbolic name as used on
        the outfiles object, and this setting will apply only to that
        image.

        New in version 2.0.5.

        """
        self.setOptionForImagename('omitHistogram', imagename, omitHistogram)
    
    def setOverviewLevels(self, overviewLevels, imagename=None):
        """
        Set the overview levels to be used on output images (i.e. pyramid layers). 
        Levels are specified as a list of integer factors, with the same meanings 
        as given to the gdaladdo command. 

        New in version 1.4.1

        """
        self.setOptionForImagename('overviewLevels', imagename, overviewLevels)

    def setOverviewMinDim(self, overviewMinDim, imagename=None):
        """
        Set minimum dimension allowed for output overview. Overview levels (i.e. pyramid
        layers) will be calculated as per the overviewLevels list of factors, but 
        only until the minimum dimension falls below the value of overviewMinDim

        New in version 1.4.1

        """
        self.setOptionForImagename('overviewMinDim', imagename, overviewMinDim)
    
    def setOverviewAggregationType(self, overviewAggType, imagename=None):
        """
        Set the type of aggregation used when computing overview images (i.e. pyramid 
        layers). Normally a thematic image should be aggregated using "NEAREST", while a 
        continuous image should be aggregated using "AVERAGE". When the setting is 
        given as None, then a default is used. If using an output format which 
        supports LAYER_TYPE, the default is based on this, but if not, it comes from 
        the value of the environment variable $RIOS_DEFAULT_OVERVIEWAGGREGATIONTYPE.
        
        This method should usually be used to set when writing an output to a format
        which does not support LAYER_TYPE, and which is not appropriate for the
        setting given by the environment default. 

        New in version 1.4.1

        """
        self.setOptionForImagename('overviewAggType', imagename, overviewAggType)

    def setSinglePassPyramids(self, singlePassPyramids, imagename=None):
        """
        The default behaviour is to attempt to compute pyramid layers (i.e.
        overviews) for output files as each block is computed. This avoids
        an extra pass through the data afterwards.

        The single-pass pyramids requires that incremental writing of
        pyramids is supported by the output format driver. This is checked
        for each driver used. The default will use it if supported, but fall
        back to GDAL if not.

        If singlePassPyramids is given here as False, then this will not be
        attempted, and instead GDAL's BuildOverviews() function will be called
        after the output is completed (i.e. a whole extra pass through the
        data). If True is given, and the driver does not support it, then
        an exception will be raised.

        New in version 2.0.5.

        """
        self.setOptionForImagename('singlePassPyramids', imagename,
            singlePassPyramids)

    def setSinglePassBasicStats(self, singlePassBasicStats, imagename=None):
        """
        The default behaviour is to attempt to compute basic statistics
        (i.e. min/max/mean/stddev) for all output files as each block is
        computed. This avoids an extra pass through the data afterwards.

        If singlePassBasicStats is given here as False, then this will not be
        attempted, and instead GDAL's ComputeStatistics() function will be
        called after the output is completed (i.e. a whole extra pass through
        the data).

        New in version 2.0.5.

        See also setApproxStats() for an alternative way of speeding up
        basic statistics.

        """
        self.setOptionForImagename('singlePassBasicStats', imagename,
            singlePassBasicStats)

    def setSinglePassHistogram(self, singlePassHistogram, imagename=None):
        """
        The default behaviour is to attempt to compute a histogram
        (on each band) for all output files. If possible, this will be done
        incrementally, as each block of output is written, but if that is
        not possible, it will be done at the end of processing, which will
        require an extra pass through each output file.

        The single-pass histogram is only supported for integer datatypes. The
        default behaviour is to do single-pass histograms if possible, and
        if not, to fall back computing histograms using GDAL's GetHistogram()
        function, after the output files have been written.

        If singlePassHistogram is given here as False, then GDAL's function
        will always be used. If singlePassHistogram is given here as True,
        and the required conditions are not satisfied, then an exception
        will be raised, explaining why this cannot be done.

        New in version 2.0.5.

        See also setApproxStats() for an alternative way of speeding up
        histogram calculation.

        """
        self.setOptionForImagename('singlePassHistogram', imagename,
            singlePassHistogram)

    def setThematic(self, thematicFlag, imagename=None):
        """
        Boolean flag to indicate whether the output file is thematic. A value
        of True means the output will be set as thematic, although this may
        not be supported by the output format driver.

        Default is False (i.e. not thematic).

        """
        self.setOptionForImagename('thematic', imagename, thematicFlag)

    def setLayerNames(self, layerNames, imagename=None):
        """
        Set list of layernames to be given to the output file(s). This is not
        really well supported by most format drivers, and should probably
        be avoided. It seemed like a good idea at the time.

        New in version 1.1.5

        """
        self.setOptionForImagename('layernames', imagename, layerNames)
        
    def setTempdir(self, tempdir):
        """
        Set directory to use for temporary files for resampling, etc.

        Default is '.' (i.e. current directory).
        """
        self.tempdir = tempdir
        
    def setResampleMethod(self, resampleMethod, imagename=None):
        """
        Set resample method to be used for resampling of input files. Possible
        options are those defined by gdalwarp, i.e. 'near', 'bilinear', 
        'cubic', 'cubicspline', 'lanczos'. 
        """
        self.setOptionForImagename('resampleMethod', imagename, resampleMethod)
    
    def setBurnValue(self, burnvalue, vectorname=None):
        """
        Set the burn value to be used when rasterizing the input vector(s).
        If vectorname given, set only for that vector. Default is 1. 
        """
        self.setOptionForImagename('burnvalue', vectorname, burnvalue)
    
    def setBurnAttribute(self, burnattribute, vectorname=None):
        """
        Set the vector attribute name from which to get the burn value
        for each vector feature. If vectorname is given, set only for that
        vector input. Default is to use burnvalue instead of burnattribute. 
        """
        self.setOptionForImagename('burnattribute', vectorname, burnattribute)
    
    def setVectorNull(self, vectornull, vectorname=None):
        """
        Set the vector null value. This is used to initialise the
        rasterised vector, before burning in the burn value. This is of most
        importance when burning values from a vector attribute column, as 
        this should be a distinct value from any of the values in the column. 
        If this is not so, then polygons can end up blending with the background,
        resulting in incorrect answers.

        Default is 0

        """
        self.setOptionForImagename('vectornull', vectorname, vectornull)
    
    def setFilterSQL(self, filtersql, vectorname=None):
        """
        Set an SQL WHERE clause which will be used to filter vector features.
        If vectorname is given, then set only for that vector
        """
        self.setOptionForImagename('filtersql', vectorname, filtersql)
    
    def setAlltouched(self, alltouched, vectorname=None):
        """
        Set boolean value of alltouched attribute. If alltouched is True, then
        pixels will count as "inside" a vector polygon if they touch the polygon,
        rather than only if their centre is inside. 
        If vectorname given, then set only for that vector.

        Default is False.

        """
        self.setOptionForImagename('alltouched', vectorname, alltouched)
    
    def setVectorDatatype(self, vectordatatype, vectorname=None):
        """
        Set numpy datatype to use for rasterized vectors. If vectorname
        given, set only for that vector.

        Default is numpy.uint8

        """
        self.setOptionForImagename('vectordatatype', vectorname, vectordatatype)
    
    def setVectorlayer(self, vectorlayer, vectorname=None):
        """
        Set number/name of vector layer, for vector formats which have 
        multiple layers. Not required for plain shapefiles. 
        Can be either a layer number (start at zero) or 
        a layer name. If vectorname given, set only for that vector.
        """
        self.setOptionForImagename('vectorlayer', vectorname, vectorlayer)

    def selectInputImageLayers(self, layerselection, imagename=None):
        """
        Set which layers are to be read from the input image(s). Default
        will read all layers. If imagename is given, selection will be for 
        that image only. The layerselection parameter should be a list
        of layer numbers. Layer numbers follow GDAL conventions, i.e. 
        a layer number of 1 refers to the first layer in the file. 
        Can  be much more efficient when only using a small subset of 
        layers from the inputs.

        New in version 1.4.0

        """
        self.setOptionForImagename('layerselection', imagename, layerselection)
    
    def setNumThreads(self, numThreads):
        """
        This is now deprecated (version 2.0.0).
        Please see setConcurrencyStyle instead.

        Set the number of 'threads' to be used when processing each block 
        of imagery. Note that these are not threads in the technical sense, 
        but are handled by the JobManager class, and are some form of 
        cooperating parallel processes, depending on the type of job 
        manager sub-class selected. See :mod:`rios.parallel.jobmanager` 
        for full details. Note that this is only worth using on very 
        computationally-intensive tasks. Default is 1, i.e. no parallel 
        processing. 
        
        """
        self.numThreads = numThreads
    
    def setJobManagerType(self, jobMgrType):
        """
        This is now deprecated (version 2.0.0).
        Please see setConcurrencyStyle instead.

        Set which type of JobManager is to be used for parallel processing.
        See :mod:`rios.parallel.jobmanager` for details. Default is taken from
        $RIOS_DFLT_JOBMGRTYPE. 
        
        """
        self.jobManagerType = jobMgrType

    def setConcurrencyStyle(self, concurrencyStyle):
        """
        Set the concurrency style. Argument is an instance of the
        :class:`rios.structures.ConcurrencyStyle` class. See there
        for full details of how to use this.

        New in version 2.0

        """
        self.concurrency = concurrencyStyle

    def setJobName(self, jobName):
        """
        Set a job name string. This is entirely optional, and has only cosmetic
        effect.

        A job name string is set on the controls object, and is made available
        to things like other compute workers. This can assist in identifying
        workers and relating them to the originating job, in situations where
        there are multiple main jobs running simultaneously.

        It defaults to None, and is then unused.

        New in version 2.0.5

        """
        self.jobName = jobName
    
    def setAutoColorTableType(self, autoColorTableType, imagename=None):
        """
        If this option is set, then thematic raster outputs will have a
        color table automatically generated and attached to them. The type is
        passed to :func:`rios.rat.genColorTable` to determine what type of automatic
        color table is generated. 
        
        The default type will be taken from $RIOS_DFLT_AUTOCOLORTABLETYPE if it
        is set. If that is not set, then the default is not to automatically attached
        any color table to thematic output rasters.
        
        In practise, it is probably simpler to explicitly set the color table using 
        the :func:`rios.rat.setColorTable` function, after creating the file, but this
        is an alternative. 
        
        Note that the imagename parameter can be given, in which case the autoColorTableType 
        will only be applied to that raster. 
        
        None of this has any impact on athematic outputs. 

        New in version 1.4.3

        """
        self.setOptionForImagename('autoColorTableType', imagename, autoColorTableType)
    
    def setAllowOverviewsGdalwarp(self, allowOverviewsGdalwarp):
        """
        This option is provided purely for testing purposes, and it is recommended 
        that this never be used operationally. 
        
        In GDAL >= 2.0, the default behaviour of gdalwarp was modified so that it
        will use overviews during a resample to a lower resolution. By default, 
        RIOS now switches this off again (by giving gdalwarp the '-ovr NONE' 
        switch), as this is very unreliable behaviour. Overviews can be 
        calculated by many different methods, and the user of the 
        file cannot tell how they were done. 
        
        In order to allow users to assess the damage done by this, we provide
        this option to allow resampling to use overviews. This also allows
        compatibility with versions of RIOS which did not switch it off, before 
        we discovered that it was happening. To allow this, set this parameter
        to True, otherwise it defaults to False. 
        
        We strongly recommend against allowing gdalwarp to use overviews. 

        New in version 1.4.8

        """
        self.allowOverviewsGdalwarp = allowOverviewsGdalwarp
    
    def setApproxStats(self, approxStats, imagename=None):
        """
        Set boolean value of approxStats attribute. This modifies the
        computation of both basic statistics and histograms on output
        files, allowing the use of lower resolution pyramid layers
        (i.e. overviews), instead of the full resolution data. This
        dramatically speeds up both calculations.

        This has no effect when using single-pass calculation for basic
        statistics and histograms (new in 2.0.5), and so setting this to
        be True will have the effect of disabling single-pass for both
        basic statistics and histograms. It is independent of single-pass
        pyramids layers.

        If imagename is given, then the setting will apply only to
        the given image.

        New in version 1.4.9

        """
        self.setOptionForImagename('approxStats', imagename, approxStats)

    def emulateOldJobManager(self):
        """
        Uses the new ConcurrencyStyle model (version 2.0.0) to emulate the
        old JobManager concurrency. The new stuff is much better, but this
        allows old programs to use it without modification. Prints a
        deprecation warning. This routine is called automatically if the
        old JobManager settings have been invoked, and should not be used
        otherwise.
        """
        if self.numThreads != 1 and self.jobManagerType is not None:
            msg = ("setNumThreads and setJobManagerType are now " +
                   "deprecated (v2.0.0). Please use setConcurrencyStyle " +
                   "instead. Emulating jobManagerType '{}'")
            msg = msg.format(self.jobManagerType)
            rioserrors.deprecationWarning(msg, stacklevel=3)

            numComputeWorkers = self.numThreads
            jobMgrToCwKind = {
                "pbs": CW_PBS, "multiprocessing": CW_THREADS,
                "subproc": CW_THREADS, "slurm": CW_SLURM,
                "mpi": CW_THREADS, "AWSBatch": CW_AWSBATCH
            }
            cwKind = jobMgrToCwKind[self.jobManagerType]
            concurrency = ConcurrencyStyle(
                numComputeWorkers=numComputeWorkers,
                computeWorkerKind=cwKind, numReadWorkers=1
            )
            self.setConcurrencyStyle(concurrency)


def apply(userFunction, infiles, outfiles, otherArgs=None, controls=None):
    """
    Apply the given 'userFunction' to the given
    input and output files. 

    infiles and outfiles are :class:`rios.structures.FilenameAssociations` objects to 
    define associations between internal variable names and
    external filenames, for the raster file inputs and outputs. 

    otherArgs is an object of extra arguments to be passed to the 
    userFunction, each with a sensible name on the object. These 
    can be either input or output arguments, entirely at the discretion
    of userFunction(). otherArgs should be in instance of :class:`rios.structures.OtherInputs`

    The userFunction has the following call sequence::

        userFunction(info, inputs, outputs)

    or::

        userFunction(info, inputs, outputs, otherArgs)

    if otherArgs is not None.

    inputs and outputs are objects in which there are named attributes 
    with the same names as those given in the infiles and outfiles 
    objects. In the inputs and outputs objects, available inside 
    userFunction, these attributes contain numpy arrays of data read 
    from/written to the corresponding image file. 

    If the attributes given in the infiles or outfiles objects are 
    lists of filenames, the the corresponding attributes of the 
    inputs and outputs objects inside the applied function will be 
    lists of image data blocks instead of single blocks. 

    The numpy arrays are always 3-d arrays, with shape::

        (numBands, numRows, numCols)

    The datatype of the output image(s) is determined directly
    from the datatype of the numpy arrays in the outputs object. 

    The info object contains many useful details about the processing, 
    and will always be passed to the userFunction. It can, of course, 
    be ignored. It is an instance of the :class:`rios.readerinfo.ReaderInfo` class. 

    The controls argument, if given, is an instance of the 
    :class:`rios.applier.ApplierControls` class, which allows control of various 
    aspects of the reading and writing of images. See the class 
    documentation for further details.

    The apply function returns a :class:`rios.structures.ApplierReturn` object
    (new in version 2.0).

    There is a page dedicated to :doc:`applierexamples`.

    """
    # We always want to be using exceptions, but don't wish to force this
    # on the calling program, so save what they were using
    usingGdalExceptions = gdal.GetUseExceptions()
    gdal.UseExceptions()

    if controls is None:
        controls = ApplierControls()
    controls.emulateOldJobManager()
    controls._checks(infiles, outfiles)

    # Includes ImageInfo and VectorFileInfo, keyed by (logicalname, seqNum)
    allInfo = readAllImgInfo(infiles)
    # Make the working grid
    workinggrid = makeWorkingGrid(infiles, allInfo, controls)
    # Divide the working grid into blocks for processing
    blockList = makeBlockList(workinggrid, controls)

    # A timer for the main thread, to estimate wallclock time of whole run
    timings = Timers()

    with timings.interval('walltime'):
        concurrency = controls.concurrency
        if (concurrency.computeWorkerKind == CW_NONE):
            rtn = apply_singleCompute(userFunction, infiles, outfiles,
                otherArgs, controls, allInfo, workinggrid, blockList,
                None, None, None, None)
        else:
            rtn = apply_multipleCompute(userFunction, infiles, outfiles,
                otherArgs, controls, allInfo, workinggrid, blockList)

    rtn.timings.merge(timings)
    rtn.workinggrid = workinggrid

    if not usingGdalExceptions:
        # Restore the calling program's preference
        gdal.DontUseExceptions()
    return rtn


def apply_singleCompute(userFunction, infiles, outfiles, otherArgs,
        controls, allInfo, workinggrid, blockList, outBlockBuffer,
        inBlockBuffer, workerID, forceExit):
    """
    Called internally from the apply() function. Not to be called directly.

    Apply function for simplest configuration, with no compute concurrency.
    Does have possible read concurrency.

    This function is also called for each compute worker in the
    batch-oriented compute worker styles, where each worker is an instance
    of a single-compute case.

    """
    timings = Timers()

    concurrency = controls.concurrency
    tmpfileMgr = TempfileManager(controls.tempdir)
    rasterizeMgr = RasterizationMgr()
    readWorkerMgr = None
    singlePassMgr = None
    prog = None
    exceptionQue = None
    numBlocks = len(blockList)
    if outBlockBuffer is None:
        # This must be the main thread, so do certain extra things
        gdalOutObjCache = {}
        singlePassMgr = SinglePassManager(outfiles, controls, workinggrid,
            tmpfileMgr)
        prog = ApplierProgress(controls, numBlocks)
        exceptionQue = queue.Queue()
    gdalObjCache = None
    if inBlockBuffer is None:
        if concurrency.numReadWorkers > 0:
            inBlockBuffer = BlockBuffer(infiles, concurrency.numReadWorkers,
                concurrency.readBufferInsertTimeout,
                concurrency.readBufferPopTimeout,
                'read')
            readWorkerMgr = ReadWorkerMgr()
            readWorkerMgr.startReadWorkers(blockList, infiles, allInfo,
                controls, tmpfileMgr, rasterizeMgr, workinggrid, inBlockBuffer,
                timings, exceptionQue)
        else:
            gdalObjCache = {}

    blockNdx = 0

    try:
        while (blockNdx < numBlocks and
                (forceExit is None or not forceExit.is_set())):

            if prog is not None:
                prog.update(blockNdx)

            if inBlockBuffer is None:
                blockDefn = blockList[blockNdx]
                with timings.interval('reading'):
                    inputs = readBlockAllFiles(infiles, workinggrid,
                        blockDefn, allInfo, gdalObjCache, controls,
                        tmpfileMgr, rasterizeMgr)
            else:
                try:
                    with timings.interval('pop_readbuffer'):
                        (blockDefn, inputs) = inBlockBuffer.popNextBlock()
                except Exception as e:
                    workerErr = WorkerErrorRecord(e, 'main')
                    exceptionQue.put(workerErr)
                    blockDefn = inputs = None

            if inputs is not None:
                readerInfo = makeReaderInfo(workinggrid, blockDefn, controls,
                    infiles, inputs, allInfo)

                outputs = BlockAssociations()
                userArgs = (readerInfo, inputs, outputs)
                if otherArgs is not None:
                    userArgs += (otherArgs,)

                with timings.interval('userfunction'):
                    userFunction(*userArgs)

                if outBlockBuffer is None:
                    writeBlock(gdalOutObjCache, blockDefn, outfiles, outputs,
                        controls, workinggrid, singlePassMgr, timings)
                else:
                    with timings.interval('insert_computebuffer'):
                        outBlockBuffer.insertCompleteBlock(blockDefn, outputs)

            blockNdx += 1

            # Check for exceptions from workers
            if exceptionQue is not None and exceptionQue.qsize() > 0:
                exceptionRecord = exceptionQue.get()
                reportWorkerException(exceptionRecord)
                msg = "The preceding exception was raised in a worker"
                raise rioserrors.WorkerExceptionError(msg)

        if prog is not None:
            prog.update(blockNdx)
        if outBlockBuffer is None:
            closeOutfiles(gdalOutObjCache, outfiles, controls,
                singlePassMgr, timings)
    finally:
        if readWorkerMgr is not None:
            readWorkerMgr.shutdown()
        gdalObjCache = None

    # Set up returns object
    rtn = ApplierReturn()
    rtn.timings = timings
    rtn.otherArgsList = [otherArgs]
    if singlePassMgr is not None:
        rtn.singlePassMgr = singlePassMgr

    return rtn


def apply_multipleCompute(userFunction, infiles, outfiles, otherArgs,
        controls, allInfo, workinggrid, blockList):
    """
    Called internally from the apply() function. Not to be called directly.

    Apply function for the multiple compute cases. Starts a number of
    compute workers, each of which calls the user function on inputs
    and creates outputs, which this function writes to the output files.

    """
    concurrency = controls.concurrency
    tmpfileMgr = TempfileManager(controls.tempdir)
    rasterizeMgr = RasterizationMgr()
    computeMgr = getComputeWorkerManager(concurrency.computeWorkerKind)
    computeMgr.setJobName(controls.jobName)
    timings = Timers()

    numComputeWorkers = concurrency.numComputeWorkers
    outBlockBuffer = BlockBuffer(outfiles, numComputeWorkers,
        concurrency.computeBufferInsertTimeout,
        concurrency.computeBufferPopTimeout, 'compute')
    gdalOutObjCache = {}
    singlePassMgr = SinglePassManager(outfiles, controls, workinggrid,
        tmpfileMgr)
    exceptionQue = queue.Queue()

    inBlockBuffer = None
    readWorkerMgr = None
    if not concurrency.computeWorkersRead:
        inBlockBuffer = BlockBuffer(infiles, concurrency.numReadWorkers,
            concurrency.readBufferInsertTimeout,
            concurrency.readBufferPopTimeout,
            'read')
        readWorkerMgr = ReadWorkerMgr()
        readWorkerMgr.startReadWorkers(blockList, infiles, allInfo,
            controls, tmpfileMgr, rasterizeMgr, workinggrid,
            inBlockBuffer, timings, exceptionQue)

    try:
        computeMgr.startWorkers(numWorkers=concurrency.numComputeWorkers,
            userFunction=userFunction, infiles=infiles, outfiles=outfiles,
            otherArgs=otherArgs, controls=controls, blockList=blockList,
            inBlockBuffer=inBlockBuffer, outBlockBuffer=outBlockBuffer,
            workinggrid=workinggrid, allInfo=allInfo,
            computeWorkersRead=concurrency.computeWorkersRead,
            singleBlockComputeWorkers=concurrency.singleBlockComputeWorkers,
            tmpfileMgr=tmpfileMgr, haveSharedTemp=concurrency.haveSharedTemp,
            exceptionQue=exceptionQue)
    except Exception as e:
        computeMgr.shutdown()
        if readWorkerMgr is not None:
            readWorkerMgr.shutdown()
        raise e

    try:
        numBlocks = len(blockList)
        blockNdx = 0
        prog = ApplierProgress(controls, numBlocks)
        while blockNdx < numBlocks:
            prog.update(blockNdx)

            try:
                with timings.interval('pop_computebuffer'):
                    (blockDefn, outputs) = outBlockBuffer.popNextBlock()

                writeBlock(gdalOutObjCache, blockDefn, outfiles, outputs,
                    controls, workinggrid, singlePassMgr, timings)
            except Exception as e:
                workerErr = WorkerErrorRecord(e, 'main')
                exceptionQue.put(workerErr)

            blockNdx += 1

            # Check for worker exceptions
            if exceptionQue.qsize() > 0:
                exceptionRecord = exceptionQue.get()
                reportWorkerException(exceptionRecord)
                msg = "The preceding exception was raised in a worker"
                raise rioserrors.WorkerExceptionError(msg)

        closeOutfiles(gdalOutObjCache, outfiles, controls, singlePassMgr,
            timings)
        prog.update(blockNdx)
    finally:
        # It is important that the computeMgr always be shut down, as it
        # could be running a NetworkDataChannel thread
        computeMgr.shutdown()
        if readWorkerMgr is not None:
            readWorkerMgr.shutdown()

    # Assemble the return object
    rtn = ApplierReturn()
    outObjList = computeMgr.outObjList
    timingsList = [obj for obj in outObjList if isinstance(obj, Timers)]
    rtn.timings = timings
    for t in timingsList:
        rtn.timings.merge(t)
    rtn.otherArgsList = [obj for obj in computeMgr.outObjList
        if isinstance(obj, OtherInputs)]
    rtn.singlePassMgr = singlePassMgr

    return rtn


def readAllImgInfo(infiles):
    """
    Open all input files and create an ImageInfo (or VectorFileInfo)
    object for each. Return a dictionary of them, keyed by their
    position within infiles, i.e. (symbolicName, SeqNum).

    """
    allInfo = {}
    for (symbolicName, seqNum, filename) in infiles:
        try:
            infoObj = ImageInfo(filename)
        except (RuntimeError, rioserrors.FileOpenError):
            infoObj = None

        # Try as a vector
        if infoObj is None:
            try:
                infoObj = VectorFileInfo(filename)
            except (RuntimeError, rioserrors.FileOpenError):
                infoObj = None

        if infoObj is None:
            msg = "Unable to open '{}'".format(filename)
            raise rioserrors.FileOpenError(msg)

        allInfo[symbolicName, seqNum] = infoObj

    return allInfo


def makeWorkingGrid(infiles, allInfo, controls):
    """
    Work out the projection and extent of the working grid.

    Return a PixelGridDefn object representing it.
    """
    # Make a list of all the pixel grids
    pixgridList = []
    for info in allInfo.values():
        if isinstance(info, ImageInfo):
            pixgrid = PixelGridDefn(
                projection=specialProjFixes(info.projection),
                geotransform=info.transform,
                nrows=info.nrows, ncols=info.ncols)
            pixgridList.append(pixgrid)

    # Work out the reference pixel grid
    refPixGrid = controls.referencePixgrid
    if refPixGrid is None and controls.referenceImage is not None:
        refImage = controls.referenceImage

        refNdx = None
        for (symbolicName, seqNum, filename) in infiles:
            # refImage can be either a symbolic name or a real filename,
            # so check both.
            if refImage in (symbolicName, filename):
                refNdx = (symbolicName, seqNum)

        if refNdx is not None:
            refInfo = allInfo[refNdx]
        else:
            refInfo = ImageInfo(refImage)

        refPixGrid = PixelGridDefn(projection=refInfo.projection,
                        geotransform=refInfo.transform,
                        nrows=refInfo.nrows, ncols=refInfo.ncols)

    if refPixGrid is None:
        # We have not been given a reference. This means that we should not
        # be doing any reprojecting, so check that all pixel grids match
        # the first one
        refPixGrid = pixgridList[0]
        match = checkAllMatch(pixgridList, refPixGrid)
        if not match:
            msg = ('Input grids do not match. Must supply a reference ' +
                'image or pixelgrid')
            raise rioserrors.ResampleNeededError(msg)

    workinggrid = findCommonRegion(pixgridList, refPixGrid,
        controls.footprint)
    return workinggrid


def checkAllMatch(pixgridList, refPixGrid):
    """
    Returns whether any resampling necessary to match
    reference dataset.

    Use as a check if no resampling is done that we
    can proceed ok.

    """

    match = True
    for pixGrid in pixgridList:
        if not refPixGrid.isComparable(pixGrid):
            match = False
            break
        elif not refPixGrid.alignedWith(pixGrid):
            match = False
            break

    return match


def makeBlockList(workinggrid, controls):
    """
    Divide the working grid area into blocks. Return a list of
    ApplierBlockDefn objects
    """
    blockList = []
    (nrows, ncols) = workinggrid.getDimensions()
    top = 0
    while top < nrows:
        ysize = min(controls.windowysize, (nrows - top))
        left = 0
        while left < ncols:
            xsize = min(controls.windowxsize, (ncols - left))

            blockDefn = ApplierBlockDefn(top, left, ysize, xsize)
            blockList.append(blockDefn)
            left += xsize
        top += ysize
    return blockList


class ApplierProgress:
    """
    Wrapper around the controls progress object, just to simplify the
    update call, and keeping track of whether the percentage has changed.
    """
    def __init__(self, controls, numBlocks):
        self.progress = controls.progress
        self.numBlocks = numBlocks
        self.lastpercent = None

    def update(self, blockNdx):
        if self.progress is not None:
            percent = int(round(100 * blockNdx / self.numBlocks))
            if percent != self.lastpercent:
                self.progress.setProgress(percent)
                self.lastpercent = percent


def reportWorkerException(exceptionRecord):
    """
    Report the given WorkerExceptionRecord object to stderr
    """
    print(exceptionRecord, file=sys.stderr)
