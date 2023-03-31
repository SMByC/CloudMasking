"""
Raster Input Output Simplification

A Python package to simplify raster input/output
using GDAL, allowing a programmer to focus on the
processing of the data rather than the mechanics of
raster I/O. 

Rios is built on top of GDAL, and handles, among other things: 
    - Opening raster files and reading/writing raster data
    - Determining the area of intersection (or union) of 
      input rasters
    - Reprojecting inputs to be on the same projection and
      pixel alignment
    - Stepping through the rasters in small blocks, to avoid 
      large memory usage

Most common entry point is the apply function in the applier 
module. For more subtle and complex work the imagereader and 
imagewriter modules provide the ImageReader and ImageWriter 
classes, respectively. 

"""
# Used to fill in the rest of the comparison methods
from functools import total_ordering

RIOS_VERSION = '1.4.15'
__version__ = RIOS_VERSION


@total_ordering
class VersionObj(object):
    """
    Our own replacement for the old LooseVersion class,
    since they deprecated that.

    An instance of this class is initialized with a SemVer-style
    version string, and instances can be compared for ordering in
    a sensible way.

    Yes, I know we could use setuptools.pkg_resources, or similar,
    but I am sick of relying on other people's packages, when they
    go and change them so easily. This will be constant. Sigh.....
    """
    def __init__(self, vstring):
        """
        vstring is a version string, something like "a.b.c"
        where a, b & c are integers
        """
        self.vstring = vstring
        self.components = None
        if vstring is not None:
            self.components = self.parse(vstring)

    @staticmethod
    def parse(vstring):
        """
        Return a tuple of version components.

        Currently wants everything to be an int. Any trailing non-digits
        will be ignored. This means that things like '2beta1' will be
        treated the same as '2'.
        """
        fields = vstring.split('.')
        components = []
        for f in fields:
            i = VersionObj.leadingDigits(f)
            if len(i) > 0:
                components.append(int(i))
        return tuple(components)

    @staticmethod
    def leadingDigits(s):
        """
        Return the leading numeric digits of the given string,
        up to anything non-digit.

        Clever people would use a regular expression for this, but
        I am not clever.
        """
        digits = []
        i = 0
        while i < len(s) and s[i].isdigit():
            digits.append(s[i])
            i += 1
        return ''.join(digits)

    def __repr__(self):
        return "VersionObj('{}')".format(self.vstring)

    # Methods to allow ordered comparisons
    def __eq__(self, other):
        return (self.components == other.components)

    def __lt__(self, other):
        return (self.components < other.components)
