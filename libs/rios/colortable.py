"""
This module contains routines for dealing with large color 
tables. This module uses the Raster Attribute Table functions 
which are the fastest method to access the color table that
GDAL provides. 

The more general :mod:`rios.rat` and :mod:`rios.ratapplier`  
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
    ramp['Accent'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Qualitative'}
    ramp['Accent']['description'] = {}
    ramp['Accent']['description']['red'] = '127 190 253 255 56 240 191 102'
    ramp['Accent']['description']['green'] = '201 174 192 255 108 2 91 102'
    ramp['Accent']['description']['blue'] = '127 212 134 153 176 127 23 102'
    ramp['Blues'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Sequential'}
    ramp['Blues']['description'] = {}
    ramp['Blues']['description']['red'] = '247 222 198 158 107 66 33 8 8'
    ramp['Blues']['description']['green'] = '251 235 219 202 174 146 113 81 48'
    ramp['Blues']['description']['blue'] = '255 247 239 225 214 198 181 156 107'
    ramp['BrBG'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Diverging'}
    ramp['BrBG']['description'] = {}
    ramp['BrBG']['description']['red'] = '84 140 191 223 246 245 199 128 53 1 0'
    ramp['BrBG']['description']['green'] = '48 81 129 194 232 245 234 205 151 102 60'
    ramp['BrBG']['description']['blue'] = '5 10 45 125 195 245 229 193 143 94 48'
    ramp['BuGn'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Sequential'}
    ramp['BuGn']['description'] = {}
    ramp['BuGn']['description']['red'] = '247 229 204 153 102 65 35 0 0'
    ramp['BuGn']['description']['green'] = '252 245 236 216 194 174 139 109 68'
    ramp['BuGn']['description']['blue'] = '253 249 230 201 164 118 69 44 27'
    ramp['BuPu'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Sequential'}
    ramp['BuPu']['description'] = {}
    ramp['BuPu']['description']['red'] = '247 224 191 158 140 140 136 129 77'
    ramp['BuPu']['description']['green'] = '252 236 211 188 150 107 65 15 0'
    ramp['BuPu']['description']['blue'] = '253 244 230 218 198 177 157 124 75'
    ramp['Dark2'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Qualitative'}
    ramp['Dark2']['description'] = {}
    ramp['Dark2']['description']['red'] = '27 217 117 231 102 230 166 102'
    ramp['Dark2']['description']['green'] = '158 95 112 41 166 171 118 102'
    ramp['Dark2']['description']['blue'] = '119 2 179 138 30 2 29 102'
    ramp['GnBu'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Sequential'}
    ramp['GnBu']['description'] = {}
    ramp['GnBu']['description']['red'] = '247 224 204 168 123 78 43 8 8'
    ramp['GnBu']['description']['green'] = '252 243 235 221 204 179 140 104 64'
    ramp['GnBu']['description']['blue'] = '240 219 197 181 196 211 190 172 129'
    ramp['Greens'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Sequential'}
    ramp['Greens']['description'] = {}
    ramp['Greens']['description']['red'] = '247 229 199 161 116 65 35 0 0'
    ramp['Greens']['description']['green'] = '252 245 233 217 196 171 139 109 68'
    ramp['Greens']['description']['blue'] = '245 224 192 155 118 93 69 44 27'
    ramp['Greys'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Sequential'}
    ramp['Greys']['description'] = {}
    ramp['Greys']['description']['red'] = '255 240 217 189 150 115 82 37 0'
    ramp['Greys']['description']['green'] = '255 240 217 189 150 115 82 37 0'
    ramp['Greys']['description']['blue'] = '255 240 217 189 150 115 82 37 0'
    ramp['OrRd'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Sequential'}
    ramp['OrRd']['description'] = {}
    ramp['OrRd']['description']['red'] = '255 254 253 253 252 239 215 179 127'
    ramp['OrRd']['description']['green'] = '247 232 212 187 141 101 48 0 0'
    ramp['OrRd']['description']['blue'] = '236 200 158 132 89 72 31 0 0'
    ramp['Oranges'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Sequential'}
    ramp['Oranges']['description'] = {}
    ramp['Oranges']['description']['red'] = '255 254 253 253 253 241 217 166 127'
    ramp['Oranges']['description']['green'] = '245 230 208 174 141 105 72 54 39'
    ramp['Oranges']['description']['blue'] = '235 206 162 107 60 19 1 3 4'
    ramp['PRGn'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Diverging'}
    ramp['PRGn']['description'] = {}
    ramp['PRGn']['description']['red'] = '64 118 153 194 231 247 217 166 90 27 0'
    ramp['PRGn']['description']['green'] = '0 42 112 165 212 247 240 219 174 120 68'
    ramp['PRGn']['description']['blue'] = '75 131 171 207 232 247 211 160 97 55 27'
    ramp['Paired'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Qualitative'}
    ramp['Paired']['description'] = {}
    ramp['Paired']['description']['red'] = '166 31 178 51 251 227 253 255 202 106 255 177'
    ramp['Paired']['description']['green'] = '206 120 223 160 154 26 191 127 178 61 255 89'
    ramp['Paired']['description']['blue'] = '227 180 138 44 153 28 111 0 214 154 153 40'
    ramp['Pastel1'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Qualitative'}
    ramp['Pastel1']['description'] = {}
    ramp['Pastel1']['description']['red'] = '251 179 204 222 254 255 229 253 242'
    ramp['Pastel1']['description']['green'] = '180 205 235 203 217 255 216 218 242'
    ramp['Pastel1']['description']['blue'] = '174 227 197 228 166 204 189 236 242'
    ramp['Pastel2'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Qualitative'}
    ramp['Pastel2']['description'] = {}
    ramp['Pastel2']['description']['red'] = '179 253 203 244 230 255 241 204'
    ramp['Pastel2']['description']['green'] = '226 205 213 202 245 242 226 204'
    ramp['Pastel2']['description']['blue'] = '205 172 232 228 201 174 204 204'
    ramp['PiYG'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Diverging'}
    ramp['PiYG']['description'] = {}
    ramp['PiYG']['description']['red'] = '142 197 222 241 253 247 230 184 127 77 39'
    ramp['PiYG']['description']['green'] = '1 27 119 182 224 247 245 225 188 146 100'
    ramp['PiYG']['description']['blue'] = '82 125 174 218 239 247 208 134 65 33 25'
    ramp['PuBuGn'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Sequential'}
    ramp['PuBuGn']['description'] = {}
    ramp['PuBuGn']['description']['red'] = '255 236 208 166 103 54 2 1 1'
    ramp['PuBuGn']['description']['green'] = '247 226 209 189 169 144 129 108 70'
    ramp['PuBuGn']['description']['blue'] = '251 240 230 219 207 192 138 89 54'
    ramp['PuBu'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Sequential'}
    ramp['PuBu']['description'] = {}
    ramp['PuBu']['description']['red'] = '255 236 208 166 116 54 5 4 2'
    ramp['PuBu']['description']['green'] = '247 231 209 189 169 144 112 90 56'
    ramp['PuBu']['description']['blue'] = '251 242 230 219 207 192 176 141 88'
    ramp['PuOr'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Diverging'}
    ramp['PuOr']['description'] = {}
    ramp['PuOr']['description']['red'] = '127 179 224 253 254 247 216 178 128 84 45'
    ramp['PuOr']['description']['green'] = '59 88 130 184 224 247 218 171 115 39 0'
    ramp['PuOr']['description']['blue'] = '8 6 20 99 182 247 235 210 172 136 75'
    ramp['PuRd'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Sequential'}
    ramp['PuRd']['description'] = {}
    ramp['PuRd']['description']['red'] = '247 231 212 201 223 231 206 152 103'
    ramp['PuRd']['description']['green'] = '244 225 185 148 101 41 18 0 0'
    ramp['PuRd']['description']['blue'] = '249 239 218 199 176 138 86 67 31'
    ramp['Purples'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Sequential'}
    ramp['Purples']['description'] = {}
    ramp['Purples']['description']['red'] = '252 239 218 188 158 128 106 84 63'
    ramp['Purples']['description']['green'] = '251 237 218 189 154 125 81 39 0'
    ramp['Purples']['description']['blue'] = '253 245 235 220 200 186 163 143 125'
    ramp['RdBu'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Diverging'}
    ramp['RdBu']['description'] = {}
    ramp['RdBu']['description']['red'] = '103 178 214 244 253 247 209 146 67 33 5'
    ramp['RdBu']['description']['green'] = '0 24 96 165 219 247 229 197 147 102 48'
    ramp['RdBu']['description']['blue'] = '31 43 77 130 199 247 240 222 195 172 97'
    ramp['RdGy'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Diverging'}
    ramp['RdGy']['description'] = {}
    ramp['RdGy']['description']['red'] = '103 178 214 244 253 255 224 186 135 77 26'
    ramp['RdGy']['description']['green'] = '0 24 96 165 219 255 224 186 135 77 26'
    ramp['RdGy']['description']['blue'] = '31 43 77 130 199 255 224 186 135 77 26'
    ramp['RdPu'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Sequential'}
    ramp['RdPu']['description'] = {}
    ramp['RdPu']['description']['red'] = '255 253 252 250 247 221 174 122 73'
    ramp['RdPu']['description']['green'] = '247 224 197 159 104 52 1 1 0'
    ramp['RdPu']['description']['blue'] = '243 221 192 181 161 151 126 119 106'
    ramp['RdYlBu'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Diverging'}
    ramp['RdYlBu']['description'] = {}
    ramp['RdYlBu']['description']['red'] = '165 215 244 253 254 255 224 171 116 69 49'
    ramp['RdYlBu']['description']['green'] = '0 48 109 174 224 255 243 217 173 117 54'
    ramp['RdYlBu']['description']['blue'] = '38 39 67 97 144 191 248 233 209 180 149'
    ramp['RdYlGn'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Diverging'}
    ramp['RdYlGn']['description'] = {}
    ramp['RdYlGn']['description']['red'] = '165 215 244 253 254 255 217 166 102 26 0'
    ramp['RdYlGn']['description']['green'] = '0 48 109 174 224 255 239 217 189 152 104'
    ramp['RdYlGn']['description']['blue'] = '38 39 67 97 139 191 139 106 99 80 55'
    ramp['Reds'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Sequential'}
    ramp['Reds']['description'] = {}
    ramp['Reds']['description']['red'] = '255 254 252 252 251 239 203 165 103'
    ramp['Reds']['description']['green'] = '245 224 187 146 106 59 24 15 0'
    ramp['Reds']['description']['blue'] = '240 210 161 114 74 44 29 21 13'
    ramp['Set1'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Qualitative'}
    ramp['Set1']['description'] = {}
    ramp['Set1']['description']['red'] = '228 55 77 152 255 255 166 247 153'
    ramp['Set1']['description']['green'] = '26 126 175 78 127 255 86 129 153'
    ramp['Set1']['description']['blue'] = '28 184 74 163 0 51 40 191 153'
    ramp['Set2'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Qualitative'}
    ramp['Set2']['description'] = {}
    ramp['Set2']['description']['red'] = '102 252 141 231 166 255 229 179'
    ramp['Set2']['description']['green'] = '194 141 160 138 216 217 196 179'
    ramp['Set2']['description']['blue'] = '165 98 203 195 84 47 148 179'
    ramp['Set3'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Qualitative'}
    ramp['Set3']['description'] = {}
    ramp['Set3']['description']['red'] = '141 255 190 251 128 253 179 252 217 188 204 255'
    ramp['Set3']['description']['green'] = '211 255 186 128 177 180 222 205 217 128 235 237'
    ramp['Set3']['description']['blue'] = '199 179 218 114 211 98 105 229 217 189 197 111'
    ramp['Spectral'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Diverging'}
    ramp['Spectral']['description'] = {}
    ramp['Spectral']['description']['red'] = '158 213 244 253 254 255 230 171 102 50 94'
    ramp['Spectral']['description']['green'] = '1 62 109 174 224 255 245 221 194 136 79'
    ramp['Spectral']['description']['blue'] = '66 79 67 97 139 191 152 164 165 189 162'
    ramp['YlGnBu'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Sequential'}
    ramp['YlGnBu']['description'] = {}
    ramp['YlGnBu']['description']['red'] = '255 237 199 127 65 29 34 37 8'
    ramp['YlGnBu']['description']['green'] = '255 248 233 205 182 145 94 52 29'
    ramp['YlGnBu']['description']['blue'] = '217 177 180 187 196 192 168 148 88'
    ramp['YlGn'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Sequential'}
    ramp['YlGn']['description'] = {}
    ramp['YlGn']['description']['red'] = '255 247 217 173 120 65 35 0 0'
    ramp['YlGn']['description']['green'] = '255 252 240 221 198 171 132 104 69'
    ramp['YlGn']['description']['blue'] = '229 185 163 142 121 93 67 55 41'
    ramp['YlOrBr'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Sequential'}
    ramp['YlOrBr']['description'] = {}
    ramp['YlOrBr']['description']['red'] = '255 255 254 254 254 236 204 153 102'
    ramp['YlOrBr']['description']['green'] = '255 247 227 196 153 112 76 52 37'
    ramp['YlOrBr']['description']['blue'] = '229 188 145 79 41 20 2 4 6'
    ramp['YlOrRd'] = {'author': 'Cynthia Brewer', 'comments': 'Colours from www.colorbrewer.org by Cynthia A. Brewer, Geography, Pennsylvania State University.', 'type': 'Sequential'}
    ramp['YlOrRd']['description'] = {}
    ramp['YlOrRd']['description']['red'] = '255 255 254 254 253 252 227 189 128'
    ramp['YlOrRd']['description']['green'] = '255 237 217 178 141 78 26 0 0'
    ramp['YlOrRd']['description']['blue'] = '204 160 118 76 60 42 28 38 38'    
    # Viridis palettes
    ramp['viridis'] = {'author': ' Stefan van der Walt and Nathaniel Smith', 'comments': '', 
        'type': 'Diverging'}
    ramp['viridis']['description'] = {}
    ramp['viridis']['description']['red'] = '68 72 67 56 45 37 30 43 81 133 194 253'
    ramp['viridis']['description']['green'] = '1 33 62 89 112 133 155 176 197 213 223 231'
    ramp['viridis']['description']['blue'] = '84 115 133 140 142 142 138 127 106 74 35 37'
    ramp['magma'] = {'author': ' Stefan van der Walt and Nathaniel Smith', 'comments': '', 
        'type': 'Diverging'}
    ramp['magma']['description'] = {}
    ramp['magma']['description']['red'] = '0 18 51 90 125 163 200 233 249 254 254 252'
    ramp['magma']['description']['green'] = '0 13 16 22 36 48 62 85 124 168 211 253'
    ramp['magma']['description']['blue'] = '4 50 104 126 130 126 115 98 93 115 149 191'
    ramp['plasma'] = {'author': ' Stefan van der Walt and Nathaniel Smith', 'comments': '',
        'type': 'Diverging'}
    ramp['plasma']['description'] = {}
    ramp['plasma']['description']['red'] = '13 62 99 135 166 192 213 231 245 253 252 240'
    ramp['plasma']['description']['green'] = '8 4 0 7 32 58 84 111 140 173 210 249'
    ramp['plasma']['description']['blue'] = '135 156 167 166 152 131 110 90 70 50 37 33'
    ramp['inferno'] = {'author': ' Stefan van der Walt and Nathaniel Smith', 'comments': '', 
        'type': 'Diverging'}
    ramp['inferno']['description'] = {}
    ramp['inferno']['description']['red'] = '0 20 58 96 133 169 203 230 247 252 245 252'
    ramp['inferno']['description']['green'] = '0 11 9 19 33 46 65 93 131 173 219 255'
    ramp['inferno']['description']['blue'] = '4 53 99 110 107 94 73 47 17 18 75 164'
    ramp['cividis'] = {'author': ' Stefan van der Walt and Nathaniel Smith', 'comments': '', 
        'type': 'Diverging'}
    ramp['cividis']['description'] = {}
    ramp['cividis']['description']['red'] = '0 0 42 72 94 114 135 158 182 208 234 255'
    ramp['cividis']['description']['green'] = '32 48 64 82 98 115 132 150 169 190 211 234'
    ramp['cividis']['description']['blue'] = '77 111 108 107 110 116 121 119 113 103 87 70'
    # Other tables 
    ramp['gray'] = {'type': 'Sequential', 'description': {}}
    ramp['gray']['description']['red'] = '0 255'
    ramp['gray']['description']['green'] = '0 255'
    ramp['gray']['description']['blue'] = '0 255'
    ramp['rainbow'] = {'type': 'Sequential', 'description': {}}
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


class ColorTableMissingException(ColorTableException):
    "Exception for errors related to errors reading color table"


def addRamp(name, red, green, blue):
    """
    Add a new ramp to the internal list of color ramps so that it can 
    be used with genTable() etc. 
    
    red, green and blue must be strings with the values, space separated.
    These values should be 0-255 and have the same number of values for 
    each color.
    
    """
    if name in RAMP:
        msg = 'Ramp {} already exists'.format(name)
        raise ColorTableException(msg)
        
    if (not isinstance(red, basestring) or not isinstance(green, basestring) or 
            not isinstance(blue, basestring)):
        msg = "Colour values must be a space separated string"
        raise ColorTableException(msg)
        
    RAMP[name] = {'description': {'red': red, 'green': green, 'blue': blue}}


def getRampNames():
    """
    Get a list of names of the available color ramps
    """
    names = list(RAMP.keys())
    names.append(RANDOM_NAME)
    return names


def genTable(numEntries, colorType, ignoreVal=None, colorPoints=None):
    """
    Generate the named color table for use with setTable().
    
    colorType should be one of the names returned from 
    getRampNames(). 
    
    numEntries is the size of the table that is generated
    and should correspond to the range of data you have 
    in the output file.
    
    If ignoreVal is specified then the opacity for this
    row is set to 0 - ie totally transparent. Use this for
    preparing images for display so images underneath in a 
    viewer show through where the ignoreVal is set.
    
    If colorPoints is set it should be a sequence of entry numbers
    to use for the points on the color ramp. If not given the points
    on the color ramp are evenly spread 0-numEntries. Actual colors
    for points between are interpolated.

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
            if colorPoints is not None:
                # use what they've given us
                if len(colorPoints) != len(colList):
                    msg = 'colorPoints needs to have same number as selected ramp'
                    raise ColorTableException(msg)
                xobs = colorPoints
            else:
                # the x-values of the observations
                # evenly spaced 0-numEntries with len(colList) obs
                xobs = numpy.linspace(0, numEntries, len(colList))
            # create an array from our list
            yobs = numpy.array(colList)
            # values to interpolate at 0-numEntries
            # same size as the lut
            xinterp = numpy.linspace(0, numEntries, numEntries)
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
    
    If there is no color table, returns None.
    
    """
    if isinstance(imgFile, basestring):
        ds = gdal.Open(str(imgFile))
    elif isinstance(imgFile, gdal.Dataset):
        ds = imgFile

    gdalBand = ds.GetRasterBand(bandNumber)
    attrTbl = gdalBand.GetDefaultRAT()
    if attrTbl is None:
        msg = 'Color table has zero rows'
        raise ColorTableMissingException(msg)
    
    numEntries = attrTbl.GetRowCount()
    if numEntries == 0:
        msg = 'Color table has zero rows'
        raise ColorTableMissingException(msg)
    
    ct = numpy.empty((4, numEntries), dtype=numpy.uint8)
    
    colorUsages = [gdal.GFU_Red, gdal.GFU_Green, gdal.GFU_Blue, gdal.GFU_Alpha]
    for idx, usage in enumerate(colorUsages):
        colNum = attrTbl.GetColOfUsage(usage)
        if colNum == -1:
            msg = 'Cannot find color table columns in file'
            raise ColorTableMissingException(msg)
            
        ct[idx] = attrTbl.ReadAsArray(colNum)
        
    return ct


def setTable(imgFile, colorTable, bandNumber=1, colorTableAPI=False):
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
    
    This table is usually generated by getTable() or genTable().
    
    If colorTableAPI is True, then GDAL's ColorTable API is used rather than
    the default RasterAttributeTable API. This can be slower, but is supported
    better by some formats (eg GTiff). 
    
    """    
    if isinstance(imgFile, basestring):
        ds = gdal.Open(str(imgFile), gdal.GA_Update)
    elif isinstance(imgFile, gdal.Dataset):
        ds = imgFile

    gdalBand = ds.GetRasterBand(bandNumber)
    
    if colorTableAPI:
        clrTbl = gdal.ColorTable()

        _, nrows = colorTable.shape
        for n in range(nrows):
            clrTbl.SetColorEntry(n, tuple(colorTable[..., n]))

        gdalBand.SetRasterColorTable(clrTbl)
    else:
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
        colorUsages = {gdal.GFU_Red: 'Red', gdal.GFU_Green: 'Green', 
            gdal.GFU_Blue: 'Blue', gdal.GFU_Alpha: 'Alpha'}
        for idx, usage in enumerate(colorUsages):
            colNum = attrTbl.GetColOfUsage(usage)
            if colNum == -1:
                name = colorUsages[usage]
                attrTbl.CreateColumn(name, gdal.GFT_Integer, usage)
                colNum = attrTbl.GetColumnCount() - 1

            attrTbl.WriteArray(colorTable[idx], colNum)

        if not isFileRAT:
            gdalBand.SetDefaultRAT(attrTbl)
