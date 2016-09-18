# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CloudMaskingDockWidget
                                 A QGIS plugin
 Cloud masking using different process suck as fmask
                             -------------------
        copyright            : (C) 2016 by Xavier Corredor Llano, SMBYC
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
from PyQt4.QtCore import pyqtSignal

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'cloud_masking_dockwidget_base.ui'))


class CloudMaskingDockWidget(QtGui.QDockWidget, FORM_CLASS):

    # Fmask parameters by default
    cloud_prob = 22.5
    bb_threshold = 10

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(CloudMaskingDockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.setup_gui()

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def setup_gui(self):
        # FMask Cloud probability #########
        # start hidden
        self.frame_FMask.setHidden(True)
        # Synchronize the slider with the spin box
        self.update_cloud_prob(self.cloud_prob)
        self.horizontalSlider_CP.valueChanged.connect(self.update_cloud_prob)
        self.doubleSpinBox_CP.valueChanged.connect(self.update_cloud_prob)

        # Blue band threshold #########
        # start hidden
        self.frame_BlueBand.setHidden(True)
        # Synchronize the slider with the spin box
        self.update_bb_threshold(self.bb_threshold)
        self.horizontalSlider_BB.valueChanged.connect(self.update_bb_threshold)
        self.doubleSpinBox_BB.valueChanged.connect(self.update_bb_threshold)

        # Quality control flags #########
        # start hidden
        self.frame_QCflags.setHidden(True)

    @QtCore.pyqtSlot(int)
    def update_cloud_prob(self, value):
        """Save value and connect the slider and spinbox
        """
        self.cloud_prob = value
        self.horizontalSlider_CP.setValue(value)
        self.doubleSpinBox_CP.setValue(value)


    @QtCore.pyqtSlot(int)
    def update_bb_threshold(self, value):
        """Save value and connect the slider and spinbox
        """
        self.bb_threshold = value
        self.horizontalSlider_BB.setValue(value)
        self.doubleSpinBox_BB.setValue(value)
