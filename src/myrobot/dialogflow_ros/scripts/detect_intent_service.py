#!/usr/bin/env python3
import sys


from dialogflow_ros.srv import DialogflowService
from dialogflow_ros import DialogflowClient

sys.path.remove('/opt/ros/melodic/lib/python2.7/dist-packages')# in order to import cv2 under python3
sys.path.append('/home/luca/ros/src/dialogflow_ros/src/dialogflow_ros/scripts')#per importare utils
sys.path.append('/home/luca/ros/src/dialogflow_ros/src/dialogflow_ros/srv')#per importare utils

sys.path.append('/opt/ros/melodic/lib/python2.7/dist-packages')# in order to import cv2 under python3
import rospy

class DialogflowService:
    def __init__(self):
        self._dc = DialogflowClient()
        self._service = rospy.Service('/dialogflow_client/intent_service', DialogflowService, self._service_cb)

    def _service_cb(self, req):
        if req.voice:
            df_msg = self._dc.detect_intent_stream()
        else:
            df_msg = self._dc.detect_intent_text(req.text)
        return DialogflowServiceResponse(success=True, result=df_msg)


if __name__ == '__main__':
    rospy.init_node('dialogflow_service')
    ds = DialogflowService()
    rospy.loginfo("DF_CLIENT: Dialogflow Service is running...")
    rospy.spin()
