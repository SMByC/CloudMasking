# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CloudMasking
                                 A QGIS plugin
 Cloud masking for landsat products using different process suck as fmask
                              -------------------
        copyright            : (C) 2016-2018 by Xavier Corredor Llano, SMByC
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
"""

import os
from qgis.PyQt import QtGui, uic

# plugin path
plugin_folder = os.path.dirname(os.path.dirname(__file__))
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    plugin_folder, 'ui', 'about.ui'))


class AboutDialog(QtGui.QDialog, FORM_CLASS):
    def __init__(self):
        QtGui.QDialog.__init__(self)
        self.setupUi(self)
        about_file = os.path.join(plugin_folder, 'gui', 'about.html')
        html_text = open(about_file).read()
        self.about_html.setHtml(html_text)
        self.about_html.setOpenExternalLinks(True)
