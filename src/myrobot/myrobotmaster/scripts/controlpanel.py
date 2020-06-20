#!/usr/bin/env python3

import sys
import os
#import utils
import signal #gestione ctrl-c

# ROS
import rospy
import rospkg
from rospkg.rospack import RosPack
from std_msgs.msg import String , Float64, Bool, Int32, Int16
from geometry_msgs.msg import Twist



import PyQt5.QtWidgets as QtWidgets 
from PyQt5.QtWidgets import *


from PyQt5.QtWidgets import QApplication, QMainWindow

class ControlPanel():
    def __init__(self):
        # Register Ctrl-C sigint
        signal.signal(signal.SIGINT, self._signal_handler)
        rpack = RosPack()
        pkg_path = rpack.get_path('dialogflow_ros')

        rospy.Subscriber('/bat_charge', Float64, self.cbk_bat_charge)

        # -------------------------------------------------- #
        #  COSTRUISCO IL PANNELLO          
        # ---------------------------------------------- #
        global app
        app = QApplication(sys.argv)
        #MainWindow = AppMainWindow()
        win = QMainWindow()
        win.resize(800, 600)

        BtnLayout = QtWidgets.QHBoxLayout()
        self.PlusButton = QtWidgets.QPushButton('+')
        self.MinusButton = QtWidgets.QPushButton('-')
        BtnLayout.addWidget(self.PlusButton)
        BtnLayout.addWidget(self.MinusButton)

        button = QPushButton('Click')

        button.clicked.connect(self.on_button_clicked)
        button.show()

        app.exec_()




        # grid = Qw.QGridLayout()
        # grid.setSpacing(10)

        # grid.addWidget(self.search_input, 1, 1)
        # grid.addWidget(self.fts_checkbox, 1, 3)
        # grid.addWidget(self.upd_button, 1, 4)
        # grid.addWidget(self.table, 2, 1, 4, 4)
        # self.setLayout(grid)


    def on_button_clicked(self):
        alert = QMessageBox()
        alert.setText('You clicked the button!')
        alert.exec_()


    def cbk_bat_charge(self, msg):
        bat_charge = msg.data









#!/usr/bin/env python

import os, sys
import rospy
from std_msgs.msg import String
from python_qt_binding import loadUi
from PyQt5 import QtGui

class pyGui(QtGui.QWidget):
    def __init__(self):
        super(pyGui, self).__init__()
        self_dir = os.path.dirname(os.path.realpath(__file__))
        print self_dir
        self.ui_dir = os.path.join(self_dir, '../ui')
        ui_file = os.path.join(self.ui_dir, 'pygui.ui')
        loadUi(ui_file, self)
        self.pub = rospy.Publisher("pygui_topic", String, queue_size=10)
        rospy.init_node('py_gui')
        self.is_pub = False
        self.current_value = self.horizontalSlider.value()
        print self.current_value
        self.label.setText("num: " + str(self.current_value))
        self.pushButton.pressed.connect(self.publish_topic)
        self.pushButton_2.pressed.connect(self.gui_close)
        self.horizontalSlider.valueChanged.connect(self.change_value)

    def publish_topic(self):
        self.pub.publish(str(self.current_value))
        self.pushButton.setEnabled(False)
        self.is_pub = True

    def change_value(self, value):
        self.current_value = value
        if True == self.is_pub:
            self.label.setText("num: " + str(value))
            self.pub.publish(str(self.current_value))

    def gui_close(self):
        self.close()


def main():
    app=QtGui.QApplication(sys.argv)
    pyShow = pyGui()
    pyShow.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()







    # -------------- #
    #  Main          #
    # -------------- #
    def start(self):

        """Start the control panel"""
        msg='Control panel attivato'
        self.speech(msg)
        
        rospy.spin()

    # ==================================== #
    #           Utility Functions          #
    # ==================================== #

    def _signal_handler(self, signal, frame):
        """Close as cleanly as possible"""
        rospy.loginfo("Control Panel: Shutting down")
        exit()

if __name__=="__main__":
  rospy.init_node("controlpanel")
  nodo= ControlPanel()
  nodo.start()

  rospy.spin()