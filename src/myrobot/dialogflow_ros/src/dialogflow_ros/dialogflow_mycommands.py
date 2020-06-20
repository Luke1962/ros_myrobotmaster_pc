#!/usr/bin/env python3


# mie annotazioni-------------------------------------------
# se vengono Warnings da ALSALIB commenta le seguenti linee in /usr/share/alsa/alsaconf
###pcm.rear cards.pcm.rear
###pcm.center_lfe cards.pcm.center_lfe
###pcm.side cards.pcm.side
###pcm.surround21 cards.pcm.surround21
###pcm.surround40 cards.pcm.surround40
###pcm.surround41 cards.pcm.surround41
###pcm.surround50 cards.pcm.surround50
###pcm.surround51 cards.pcm.surround51
###pcm.surround71 cards.pcm.surround71

#-----------------------------------------------------------


# Dialogflow
#https://dialogflow.cloud.google.com/#/agent/robot-15de1/intents

import sys
import signal #gestione ctrl-c

#sys.path.remove('/opt/ros/melodic/lib/python2.7/dist-packages')# in order to import cv2 under python3
sys.path.append('/home/luca/ros/src/dialogflow_ros/src/dialogflow_ros/utils')#per importare utils
import utils


#import dialogflow_v2beta1
import dialogflow_v2beta1
from dialogflow_v2beta1.types import Context, EventInput, InputAudioConfig, \
    OutputAudioConfig, QueryInput, QueryParameters, \
    StreamingDetectIntentRequest, TextInput
from dialogflow_v2beta1.gapic.enums import AudioEncoding, OutputAudioEncoding
import google.api_core.exceptions



import time
from uuid import uuid4
from yaml import load, YAMLError

# ROS
import rospy
import rospkg
from std_msgs.msg import String , Float64, Bool, Int32, Int16
from geometry_msgs.msg import Twist
from actionlib_msgs.msg import GoalID


sys.path.append('/opt/ros/melodic/share/')
from actionlib_msgs.msg import GoalID, GoalStatus, GoalStatusArray
from actionlib.exceptions import ActionException

# ROS-Dialogflow
from dialogflow_ros.msg import *
from dnn_detect.msg import DetectedObject, DetectedObjectArray

# Use to convert Struct messages to JSON
# from google.protobuf.json_format import MessageToJson
sys.path.append('/opt/ros/melodic/lib/python2.7/dist-packages')# in order to import cv2 under python3
# ========================================= #
#           ROS Utility Functions           #
# ========================================= #

def isNumber(s):
    try:
        float(s)
        return True
    except TypeError:
        print("Stai cercando di convertire questo in numero:", s)
        return False

    except ValueError:
        return False

class DialogflowCommandExecutor(object):
    def __init__(self, language_code='it-IT', last_contexts=None):
        """Initialize all params and load data"""
        """ Constants and params """

        self.DEBUG = rospy.get_param('/dialogflow_client/debug', False)

        # Register Ctrl-C sigint
        #signal.signal(signal.SIGINT, self._signal_handler)

        """ Dialogflow setup """
        # Get hints/clues
        rp = rospkg.RosPack()
        file_dir = rp.get_path('dialogflow_ros') + '/config/context.yaml'
        with open(file_dir, 'r') as f:
            try:
                self.phrase_hints = load(f)
            except YAMLError:
                rospy.logwarn("DF_CLIENT: Unable to open phrase hints yaml file!")
                self.phrase_hints = []

        # Dialogflow params
        #project_id = rospy.get_param('/dialogflow_client/project_id', 'robot-15de1')
        #session_id = str(uuid4())  # Random
        #self._language_code = language_code
        #self.last_contexts = last_contexts if last_contexts else []



        """ ROS Setup """

        #rospy.logdebug("DF_CLIENT: Last Contexts: {}".format(self.last_contexts))
 
 
        # subscribe tutti i messaggi di cui devo poter dare info a voce 
        self.bat_charge = 0
        rospy.Subscriber('/bat_charge', Float64, self.cbk_bat_charge)
        self.bat_volt = 0
        rospy.Subscriber('/bat_volt', Float64, self.cbk_bat_volt)
        self.bat_ampere = 0
        rospy.Subscriber('/bat_ampere', Float64, self.cbk_bat_ampere)
        self.bat_ischarging = False
        rospy.Subscriber('/bat_ischarging', Bool, self.cbk_bat_ischarging)


        self.load_watt = 0
        rospy.Subscriber('/load_watt', Float64, self.cbk_load_watt)
        self.load_ampere = 0
        rospy.Subscriber('/load_ampere', Float64, self.cbk_load_ampere)


        rospy.Subscriber("/dnn_objects",DetectedObjectArray ,self.cbk_detections)


        # qui tutti i comandi eseguibili a voce
        self.pub_chatter = rospy.Publisher('/chatter',String,queue_size=10)
        self.pub_speech_coded = rospy.Publisher('/speech_coded',String,queue_size=10)
        self.pub_speech_once = rospy.Publisher('/speech_once',String,queue_size=10)
        self.pub_faretto = rospy.Publisher("/faretto", Bool, queue_size=1)
        self.pub_laser = rospy.Publisher("/laser", Bool, queue_size=1)
        self.pub_lidar = rospy.Publisher("/lidar_enable", Bool, queue_size=1)
        self.pub_start_followme = rospy.Publisher("/start_followme", Bool, queue_size=1)
        self.pub_cmd_vel = rospy.Publisher("/cmd_vel",Twist, queue_size=1)
        self.pub_targetPose = rospy.Publisher("/target_pose",Twist, queue_size=1)
        self.pub_servo_camera = rospy.Publisher("/servo_raspicam", Int16, queue_size=1)
        self.pub_cancelGoal = rospy.Publisher("/move_base/cancel", GoalID, queue_size=1)
        self.pub_startFollowme = rospy.Publisher("/start_followme", Bool, queue_size=1)


        self.current_detection =""
        self.current_detection_confidence =0.0

    # ========================================= #
    #           speech macro                    #
    # ========================================= #
    def speech(self, msg):
        self.pub_chatter.publish(msg)
    def speech_coded(self, msg):
        self.pub_speech_coded.publish(msg)

    # ========================================= #
    #           Battery                         #
    # ========================================= #
    def cbk_bat_charge(self, msg):
        self.bat_charge = msg.data

    def cbk_bat_volt(self, msg):
        self.bat_volt = msg.data
    def cbk_bat_ampere(self, msg):
        self.bat_ampere = msg.data
    def cbk_bat_ischarging(self, msg):
        self.bat_ischarging = msg.data

    def cbk_load_watt(self, msg):
        self.load_watt = msg.data
    def cbk_load_ampere(self, msg):
        self.load_ampere = msg.data

    # ==================================== #
    #           Detections from edgetpu    #
    # ==================================== #
    def cbk_detections(self, msg):
       #detections = Detection2DArray()
       #detections = msg
       d = DetectedObject()
       d = msg.objects[0]
       self.current_detection = d.class_name
       self.current_detection_confidence = d.confidence
       #print(self.current_detection)
    # ==================================== #
    #           Utility Functions          #
    # ==================================== #



    # ========================================= #
    #           Command parser                  #
    # ========================================= #
    
    def command_parser(self, intent, parameters):
        # fai riferimento alle voci dell'entity @command in DialogFlow
        # https://cloud.google.com/dialogflow/docs/reference/rpc/google.cloud.dialogflow.v2beta1#queryparameters
        pName =""
        pVal = ""
        devName=""
        devVal= False
        str_speech_coded =""

        if intent=='':
            return
        #--------------------------------------------------------------------------        
        elif intent=='cmd_help':
            print('Comando: {}'.format(intent))
            
            argomento =""
            #leggo il parametro
            for p in parameters:
                pName = p
                pVal = parameters[p]
                #print( "p={}: parameters[p]={}\n\t".format(pName,pVal ))
                
                if (pName=="argument"):
                        argomento = pVal #  
                        
            if argomento=='batteria':
                str_speech_coded = "speech_help"
            elif argomento=='movimento':
                str_speech_coded = "speech_help"
            elif argomento=='periferiche':
                str_speech_coded = "speech_help"
            else:
                str_speech_coded = "speech_help"

            self.speech_coded(str_speech_coded)
        #--------------------------------------------------------------------------        
        # cmd_set   Accensione o spegnimento device
        #--------------------------------------------------------------------------        
        elif intent=='cmd_set':
            #parametri associati all'intent
            devName=""
            devVal =False

            print('####  Comando: {}'.format(intent))
            for p in parameters:

                pName = p #estraggo il nome del parametro
                pVal = parameters[p] #estraggo il valore del parametro
                
                
                if (pName=="device"):
                    devName = pVal
                if (pName=="status_on_off"):
                    if parameters[p]=="on":
                        devVal = True

                    else:
                        devVal = False


            # a questo punto ho le info per generare il comando
            if devName=="faretto":
                self.pub_faretto.publish(devVal)

                if devVal:
                    str_speech_coded= "speech_faretto_on"
                else:
                    str_speech_coded= "speech_faretto_off"
                self.speech_coded(str_speech_coded)

            elif devName=="laser":
                self.pub_laser.publish(devVal)

                if devVal:
                    str_speech_coded= "speech_laser_on"
                else:
                    str_speech_coded= "speech_laser_off"
                self.speech_coded(str_speech_coded)                


            elif devName=="lidar":
                self.pub_lidar.publish(devVal)


            print("_______Device:{} set:{}___________".format(devName,devVal))

        #--------------------------------------------------------------------------        
        elif intent=='cmd_move':
            #parametri associati all'intent
            direction= 1
            angle=0.0
            unitFactor = 0.01
            displacement =0.0

            print('Comando: {}'.format(intent))
            for p in parameters:
                pName = p
                pVal = parameters[p]
                print( "pName:{}, pVal:{}\n\t".format(pName,pVal ))
                
                if (pName=="direction"):    # avanti , indietro, destra , sinistra
                    if pVal =="avanti":
                        direction = 1
                    else:
                        direction = -1
                if (pName=="displacement"):
                    if isNumber(pVal):
                        displacement = float(pVal)
                    else:
                        displacement = 0.0
                if (pName=="unit_length"):
                    if pVal =="m":
                        unitFactor = 1
                    elif pVal == "dm":
                         unitFactor = 0.1
                    elif pVal == "cm":
                         unitFactor = 0.01
                    elif pVal == "mm":
                         unitFactor = 0.001                        
            msg_targetPose = Twist()
            msg_targetPose.linear.x = direction * displacement * unitFactor
            msg_targetPose.linear.y = 0.0
            msg_targetPose.linear.z = 0.0
            msg_targetPose.angular.x = 0.0
            msg_targetPose.angular.y = 0.0
            msg_targetPose.angular.z = 0.0
            #ruota di x gradi. Richiede nodo rm_cmd_move su rockpi4
            self.pub_targetPose.publish(msg_targetPose)

        #--------------------------------------------------------------------------        
        elif intent=='cmd_rotate':
            #parametri associati all'intent
            direction= 1
            angle=0.0

            print('Comando: {}'.format(intent))
            for p in parameters:
                pName = p
                pVal = parameters[p]
                #print( "p={}: parameters[p]={}\n\t".format(pName,pVal ))
                
                if (pName=="direction"):
                    if pVal =="destra":
                        direction = -1
                    else:
                        direction = 1
                if (pName=="angle"):
                    if isNumber(pVal):
                        print("\n =====> pVal:", pVal)
                        angle = float(pVal)
                        if abs(angle) > 360:
                            self.speech("sono troppi")
                            
                    else:
                        angle = 0.0

            msg_targetPose = Twist()
            msg_targetPose.linear.x = 0.0
            msg_targetPose.linear.y = 0.0
            msg_targetPose.linear.z = 0.0
            msg_targetPose.angular.x = 0.0
            msg_targetPose.angular.y = 0.0
            msg_targetPose.angular.z = direction * angle
            #ruota di x gradi. Richiede nodo rm_cmd_move su rockpi4
            #msg_targetPose.angular.z  espresso in gradi
            self.pub_targetPose.publish(msg_targetPose)

        #--------------------------------------------------------------------------        
        elif intent=='cmd_stop':
            print('Comando: {}'.format(intent))
            # cancello eventuali goal di movebase
            msg_canceGoal = GoalID()
            self.pub_cancelGoal.publish(msg_canceGoal)

            # mi fermo
            msg_targetPose = Twist()
            msg_targetPose.linear.x = 0.0
            msg_targetPose.linear.y = 0.0
            msg_targetPose.linear.z = 0.0
            msg_targetPose.angular.x = 0.0
            msg_targetPose.angular.y = 0.0
            msg_targetPose.angular.z = 0.0
            #stopi. Richiede nodo rm_cmd_move su rockpi4  (alias enc2odom)
            self.pub_targetPose.publish(msg_targetPose)        
        #--------------------------------------------------------------------------        
        elif intent=='cmd_follower':
            print('Comando: {}'.format(intent))
            pub_start_follower = Bool()
            pub_start_follower.data = True
            self.pub_start_followme.publish(pub_start_follower)

        elif intent=='cmd_follower_stop':
            print('Comando: {}'.format(intent))
            pub_start_follower = Bool()
            pub_start_follower.data = False
            self.pub_start_followme.publish(pub_start_follower)


        #--------------------------------------------------------------------------        
        elif intent=='get_info_battery':
            print('Comando : {}'.format(intent))
            s=""

            #leggo il parametro
            for p in parameters:
                pName = p
                pVal = parameters[p]
                #print( "p={}: parameters[p]={}\n\t".format(pName,pVal ))
                
                if (pName=="dev_property_bat"):
                    propertyName = pVal # tensione , corrente, consumo,carica
            
            # rispondo a seconda del parametro
            if propertyName=="tensione":
                s = "La tensione è {:.1f} volt".format( self.bat_volt)
            elif propertyName=="corrente":
                s = "La corrente è {:.2f} ampere".format( self.bat_ampere)
            elif propertyName=="consumo":
                s = "Il consumo è {:.2f} watt".format( self.load_watt)
            elif propertyName=="carica":
                s = "La batteria è al {:.1f} percento".format( self.bat_charge)
                

            print(s)
            self.speech(s)



        #--------------------------------------------------------------------------        
        elif intent=='cmd_explore':
            print('Comando: {}'.format(intent))
            self.speech("spiacente ma non sono ancora in grado di esplorare")


        #--------------------------------------------------------------------------        
        elif intent=='cmd_surveil':
            print('Comando: {}'.format(intent))
            self.speech("spiacente ma non sono ancora in grado di sorvegliare la casa")

        #--------------------------------------------------------------------------        
        elif intent=='cmd_sayhello':
            print('Comando: {}'.format(intent))
            
            person =""
            #leggo il parametro
            for p in parameters:
                pName = p
                pVal = parameters[p]
                #print( "p={}: parameters[p]={}\n\t".format(pName,pVal ))
                
                if (pName=="person"):
                    person = pVal # luca | vinicia | angelica
            if person=='luca':
                str_speech_coded = "speech_ciao_luca"
            elif person=='vinicia':
                str_speech_coded = "speech_ciao_vinicia"
            elif person=='angelica':
                str_speech_coded = "speech_ciao_angelica"
            else:
                str_speech_coded = "speech_ciao"

            self.speech_coded(str_speech_coded)

        #--------------------------------------------------------------------------        
        elif intent=='cmd_servo_camera':
            print('Comando: {}'.format(intent))
            servo_angle =0

            #leggo il parametro
            for p in parameters:
                pName = p
                pVal = parameters[p]                
                if (pName=="servo_angle"):
                    servo_angle = pVal # luca | vinicia | angelica

            msg_servo_raspicam = Int16()
            msg_servo_raspicam.data = int(servo_angle)
            self.pub_servo_camera.publish(msg_servo_raspicam)
        #--------------------------------------------------------------------------        
        elif intent=='get_detection':
            print('Comando: {}'.format(intent))
            if self.current_detection !="":
                str_speech = "vedo qualcosa che assomiglia a una " + self.current_detection
            else:
                str_speech = "non vedo nulla che posso riconoscere"
            self.speech(str_speech)
       #--------------------------------------------------------------------------        
        elif intent=='cmd_sayhello':
            print('Comando: {}'.format(intent))
            

            str_speech_coded = "speech_help"
            self.speech_coded(str_speech)
       #--------------------------------------------------------------------------        
        elif intent=='get_name':
            print('Comando: {}'.format(intent))
            

            str_speech_coded = "speech_help"
            self.speech_coded(str_speech)
       #--------------------------------------------------------------------------        
        elif intent=='cmd_rot180':
            print('Comando: {}'.format(intent))
            
            msg_targetPose = Twist()
            msg_targetPose.linear.x = 0.0
            msg_targetPose.linear.y = 0.0
            msg_targetPose.linear.z = 0.0
            msg_targetPose.angular.x = 0.0
            msg_targetPose.angular.y = 0.0
            msg_targetPose.angular.z = 180
            #ruota di x gradi. Richiede nodo rm_cmd_move su rockpi4
            #msg_targetPose.angular.z  espresso in gradi
            self.pub_targetPose.publish(msg_targetPose)
 
        elif intent=='cmd_goal_cancel':
            # cancello eventuali goal di movebase
            msg_canceGoal = GoalID()
            self.pub_cancelGoal.publish(msg_canceGoal)

 
        #--------------------------------------------------------------------------        
        else:
            print('Comando non gestito: {}'.format(intent))
            str_speech_coded = "speech_cmd_unknown"
            self.speech_coded(str_speech_coded)


 






    
