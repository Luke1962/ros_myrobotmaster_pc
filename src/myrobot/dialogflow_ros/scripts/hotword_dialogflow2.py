#!/usr/bin/env python3
import sys
import os
#sys.path.remove('/opt/ros/melodic/lib/python2.7/dist-packages')# in order to import cv2 under python3
sys.path.append('/home/luca/ros/src/dialogflow_ros/src/dialogflow_ros/utils')#per importare utils

# ROS
import rospy
import rospkg
from rospkg.rospack import RosPack
rpack = RosPack()
pkg_path = rpack.get_path('dialogflow_ros')

# Snowboy
snowboy_path = pkg_path + '/scripts/snowboy/resources/ding.wav'
#sys.path.append('/home/luca/ros/src/myrobot/dialogflow_ros/scripts/snowboy')#per importare utils
sys.path.append(snowboy_path)
from snowboy import snowboydecoder

# Dialogflow
src_path= pkg_path + '/src/dialogflow_ros'
sys.path.append(src_path)

#from dialogflow_ros import MyDialogflowClient
import importlib.util
spec = importlib.util.spec_from_file_location("dialogflow_client4.py",src_path + '/dialogflow_client4.py')

dfclient = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dfclient)
#dfclient.MyDialogflowClient()




# ROS
import rospy
from rospkg.rospack import RosPack
# Python
import pyaudio
import signal
import time
import wave

sys.path.append('/opt/ros/melodic/lib/python2.7/dist-packages') # append back in order to import rospy

class HotwordDialogflow(object):
    def __init__(self):
        self.interrupted = False
        self.detector = None
        rpack = RosPack()
        # UMDL or PMDL file paths along with audio files
        pkg_path = rpack.get_path('dialogflow_ros')

        #self.model_path = pkg_path + '/scripts/snowboy/resources/jarvis.umdl'
        self.model_path = pkg_path + '/scripts/snowboy/resources/OK_Robot.pmdl'
        print("Hotoword: {}".format(self.model_path))

        ding_path = pkg_path + '/scripts/snowboy/resources/ding.wav'
        # Setup df
        self.df_client = None
        # Setup audio output
        ding = wave.open(ding_path, 'rb')
        self.ding_data = ding.readframes(ding.getnframes())
        self.audio = pyaudio.PyAudio()
        self.stream_out = self.audio.open(
                format=self.audio.get_format_from_width(ding.getsampwidth()),
                channels=ding.getnchannels(), rate=ding.getframerate(),
                input=False, output=True)
        self.last_contexts = []
        rospy.loginfo("HOTWORD_CLIENT: Ready!")

    def _signal_handler(self, signal, frame):
        rospy.logwarn("SIGINT Caught!")
        self.exit()

    def _interrupt_callback(self):
        return self.interrupted

    def play_ding(self):
        """Simple function to play a Ding sound."""
        self.stream_out.start_stream()
        self.stream_out.write(self.ding_data)
        time.sleep(0.2)
        self.stream_out.stop_stream()

    def _snowboy_callback(self):
        rospy.loginfo("HOTWORD_CLIENT: Hotword detected!")
        # self.df_client = DialogflowClient(last_contexts=self.last_contexts)
        df_msg, res = self.df_client.detect_intent_stream(return_result=True)
        self.last_contexts = res.output_contexts
        self.play_ding()

    def start(self):
        # Register Ctrl-C sigint
        signal.signal(signal.SIGINT, self._signal_handler)
        # Setup snowboy
        self.detector = snowboydecoder.HotwordDetector(self.model_path,
                                                       sensitivity=[0.5])
        self.df_client = dfclient.MyDialogflowClient()
        rospy.loginfo("HOTWORD_CLIENT: Listening... Press Ctrl-C to stop.")
        while True:
            try:
                self.detector.start(detected_callback=self._snowboy_callback,
                                    interrupt_check=self._interrupt_callback,
                                    sleep_time=0.03)
            except KeyboardInterrupt:
                self.exit()

    def exit(self):
        self.interrupted = True
        self._interrupt_callback()  # IDK man...
        self.stream_out.close()
        self.audio.terminate()
        self.detector.terminate()
        exit()


if __name__ == '__main__':
    rospy.init_node('hotword_client', log_level=rospy.DEBUG)
    hd = HotwordDialogflow()
    hd.start()
