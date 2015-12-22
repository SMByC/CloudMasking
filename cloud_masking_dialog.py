# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CloudMaskingDialog
                                 A QGIS plugin
 Cloud masking using different process suck as fmask
                             -------------------
        begin                : 2015-12-17
        git sha              : $Format:%H$
        copyright            : (C) 2015 by Xavier Corredor Llano, SMBYC
        email                : xcorredorl@ideam.gov.co
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os

from PyQt4 import QtGui, uic, QtCore

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'cloud_masking_dialog_base.ui'))


class CloudMaskingDialog(QtGui.QDialog, FORM_CLASS):

    # Fmask parameters
    cloud_prob = 22.5

    def __init__(self, parent=None):
        """Constructor."""
        super(CloudMaskingDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        self.setup_gui()

    def setup_gui(self):
        self.update_cloud_prob_to_slider(self.cloud_prob)
        self.update_cloud_prob_to_spinbox(self.cloud_prob*10)
        self.horizontalSlider_CP.valueChanged.connect(self.update_cloud_prob_to_spinbox)
        self.doubleSpinBox_CP.valueChanged.connect(self.update_cloud_prob_to_slider)

    @QtCore.pyqtSlot(int)
    def update_cloud_prob_to_slider(self, value):
        self.cloud_prob = value
        self.horizontalSlider_CP.setValue(int(value*10))

    @QtCore.pyqtSlot(int)
    def update_cloud_prob_to_spinbox(self, value):
        self.cloud_prob = value / 10.0
        self.doubleSpinBox_CP.setValue(self.cloud_prob)

