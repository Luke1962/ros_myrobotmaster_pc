#!/usr/bin/python3

'''
install:
 sudo apt install ros-melodic-python-qt-binding python-pyqt5
 sudo -H pip3 install PyQt5
git clone https://github.com/ros-visualization/python_qt_binding.git
sudo -H apt-get install python3-pyside
pip install PySide2
'''
import sys,os
# sys.path.remove('/opt/ros/melodic/lib/python2.7/dist-packages')# in order to import cv2 under python3
# sys.path.append('/usr/local/lib/python3.6/dist-packages') 
# sys.path.append('/opt/ros/melodic/share') 


#ROS
import rospy
from std_msgs.msg import String , Float64, Bool, Int32, Int16
from geometry_msgs.msg import Twist
from actionlib_msgs.msg import GoalID

#Qt5
from PyQt5 import QtGui
from PyQt5.QtGui import * #QLabel, QVBoxLayout, QHBoxLayout, QSlider, QPushButton
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5 import QtCore, QtGui, QtWidgets
from python_qt_binding import loadUi
from PyQt5.QtWidgets import QDial



class Dashboard(QWidget):
    def __init__(self):
        super(Dashboard, self).__init__()
        self.setObjectName('Dashboard')

        #carico il file di GUI sotto ../ui/pygui.ui
        self_dir = os.path.dirname(os.path.realpath(__file__))
        self.ui_dir = os.path.join(self_dir, '../ui')
        ui_file = os.path.join(self.ui_dir, 'Dashboard.ui')
        loadUi(ui_file, self)


        #ROS pub 
        self.pub_chatter = rospy.Publisher("/chatter", String, queue_size=1)
        self.pub_servo_camera = rospy.Publisher("/servo_raspicam", Int16, queue_size=1)
        self.pub_startFollowme = rospy.Publisher("/start_follwome", Bool, queue_size=1)
        self.pub_cancelGoal = rospy.Publisher("/move_base/cancel", GoalID, queue_size=1)

        # ROS subscribes
        self.bat_charge = 0
        rospy.Subscriber('/bat_charge', Float64, self.cbk_bat_chargeLevel)
        rospy.Subscriber('/bat_ampere', Float64, self.cbk_bat_chargingCurrent)

        rospy.init_node('pyqt_gui')

   
        #Azioni dei pulsanti e comandi
        self.sliderServo.valueChanged.connect(self.sliderServo_changeValue)
        self.btnQuit.pressed.connect(self.quit)
        self.btnCancelGoal.pressed.connect(self.cancelGoal)
        self.btnStartFollowme.pressed.connect(self.startFollowme)

 

    def buttonClick(self, button):
        print(button.text()) 

    def change_color(self, color):
        template_css = """QProgressBar::chunk { background: %s; }"""
        css = template_css % color
        self.setStyleSheet(css)

    # ========================================= #
    #           Battery                         #
    # ========================================= #
    def cbk_bat_chargeLevel(self, msg):
        self.bat_charge = msg.data
        self.LCDbatCharge.display(self.bat_charge) 
        self.barBatCharge.setValue(msg.data)
        '''
        if self.bat_charge > 60:
            self.barBatCharge.setStyleSheet("selection-background-color: rgb(0, 250, 0);")
        elif self.bat_charge > 40:
            self.barBatCharge.setStyleSheet("selection-background-color: rgb(245, 121, 0);")
        else:
            self.barBatCharge.setStyleSheet("selection-background-color: rgb(255, 0, 0);")

 
        '''
    def cbk_bat_chargingCurrent(self,msg):
        ma = -int(msg.data*1000)
        self.barChargingCurrent.setValue(-msg.data*1000) 
        #self.label_milliampere.text=str(ma)
        self.radioButton.toggle() # = not self.radioButton.checked
        print("mA charge: ",ma)

    def startFollowme(self):
        print("startFollowme")        
        self.pub_startFollowme.publish()


    def cancelGoal(self):
        print("Cancel Goal")
        msg_canceGoal = GoalID()
        self.pub_cancelGoal.publish(msg_canceGoal)
        

    def publish_topic(self):
        self.pub_chatter.publish(str(self.current_value))

    def sliderServo_changeValue(self, value):
        self.label_servo.setText("ricevuto  " + str(value))
        self.current_value = value
        print(self.current_value)


        msg_servo_raspicam = Int16()
        msg_servo_raspicam.data = int(value)
        self.pub_servo_camera.publish(msg_servo_raspicam)
        
    def quit(self):
        self.pub_chatter.unregister()
        rospy.loginfo("Shutting down talkback node...")
        sys.exit(app.exec_())

if __name__ == "__main__":
    app=QtWidgets.QApplication(sys.argv)
    pyShow = Dashboard()
    pyShow.show()
    sys.exit(app.exec_())
