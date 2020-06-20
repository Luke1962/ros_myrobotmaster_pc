#!/usr/bin/env python3

'''
# mie annotazioni-------------------------------------------
# Questa versione usa l'App Android ROS Voice
per convertire la voce in testo
e usa solo il testo
#-----------------------------------------------------------
'''


import sys
import os

'''debug'''
sys.path.append('/home/luca/ros/devel/lib/python2.7/dist-packages:/opt/ros/melodic/lib/python2.7/dist-packages:/usr/bin:/usr/local/lib/python3.6/dist-packages')
sys.path.append('/home/luca/ros/src/myrobot/dialogflow_ros/src/')
sys.path.append('/home/luca/ros/src/myrobot/dialogflow_ros/src/dialogflow_ros')#per importare utils
sys.path.append('/home/luca/ros/src/myrobot/dialogflow_ros/src/dialogflow_ros/utils')#per importare utils
print(sys.path)
import utils




#installare jsk_common_msgs
from speech_recognition_msgs.msg import SpeechRecognitionCandidates

# dialogflow
import dialogflow_v2 
from dialogflow_v2.types \
    import Context, EventInput, InputAudioConfig, \
    OutputAudioConfig, QueryInput, QueryParameters, \
    StreamingDetectIntentRequest, TextInput
from dialogflow_v2.gapic.enums import AudioEncoding, OutputAudioEncoding
import google.api_core.exceptions
from uuid import uuid4

#import utils
from AudioServerStream import AudioServerStream
from MicrophoneStream import MicrophoneStream

# Python
import pyaudio
import signal #gestione ctrl-c

import time
from yaml import load, YAMLError

# ROS
import rospy
import rospkg
from rospkg.rospack import RosPack

from std_msgs.msg import String , Float64, Bool
from geometry_msgs.msg import Twist

# ROS-Dialogflow
from dialogflow_ros.msg import *


#esegue i comandi riconosciuti da DialogFlow
from  dialogflow_mycommands import DialogflowCommandExecutor

# Use to convert Struct messages to JSON
# from google.protobuf.json_format import MessageToJson
sys.path.append('/opt/ros/melodic/lib/python2.7/dist-packages')#  to import cv2 under python3



rpack = RosPack()
# UMDL or PMDL file paths along with audio files
import wave
pkg_path = rpack.get_path('dialogflow_ros')
ding_path = pkg_path + '/scripts/snowboy/resources/ding.wav'
ding = wave.open(ding_path, 'rb')

def isNumber(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

class MyDialogflowClient(object):
    def __init__(self, language_code='it-IT', last_contexts=None):
        """Initialize all params and load data"""
        """ Constants and params """

        self.CHUNK = 4096
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE =44100 #was 16000
        self.DEBUG = rospy.get_param('/dialogflow_client/debug', False)

        #----------------------------------------------------------------------------------
        #
        # ROS Parametrers
        #
        #-----------------------------------------------------------------------------------
        self.USE_AUDIO_SERVER = rospy.get_param('/dialogflow_client/use_audio_server', False)


        # se il flag PLAY_GOOGLE_AUDIO è attivo creo l'output audio
        self.stream_out =None

 
 
        #Snowboy parameters
        self.model_path = rospy.get_param('/dialogflow_client/model_path','')
        self.interrupted = False
        self.detector = None
        self.use_snowboy = rospy.get_param('/dialogflow_client/use_snowboy', False)
        self.snowboy_sensitivity = rospy.get_param('/dialogflow_client/snowboy_sensitivity', 0.5)        
        
        # Dialogflow params
        project_id = rospy.get_param('/dialogflow_client/project_id', 'robot-15de1')

        # Setup audio output        
        self.ding_data = ding.readframes(ding.getnframes())
        self.audio = pyaudio.PyAudio()
        #self._create_audio_output()
        '''        
                self.stream_out = self.audio.open(
                format=self.audio.get_format_from_width(ding.getsampwidth()),
                channels=ding.getnchannels(), rate=ding.getframerate(),
                input=False, output=True)
        '''





        # Register Ctrl-C sigint
        signal.signal(signal.SIGINT, self._signal_handler)


        """  
        ###############################################################################
        ###############################################################################
         Dialogflow setup
        ###############################################################################
        ###############################################################################
        """
        self.contaChiamateApi = 0
        # Get hints/clues
        rp = rospkg.RosPack()
        file_dir = rp.get_path('dialogflow_ros') + '/config/context.yaml'
        with open(file_dir, 'r') as f:
            try:
                self.phrase_hints = load(f)
            except YAMLError:
                rospy.logwarn("DF_CLIENT: Unable to open phrase hints yaml file!")
                self.phrase_hints = []

        self._language_code = language_code
        self.last_contexts = last_contexts if last_contexts else []
       
        audio_encoding = AudioEncoding.AUDIO_ENCODING_LINEAR_16

        # Possibel models: video, phone_call, command_and_search, default
        # https://cloud.google.com/dialogflow/docs/reference/rpc/google.cloud.dialogflow.v2#google.cloud.dialogflow.v2.InputAudioConfig
        self._audio_config = InputAudioConfig(audio_encoding=audio_encoding,
                                              language_code=self._language_code,
                                              sample_rate_hertz=self.RATE,
                                              phrase_hints=self.phrase_hints, #parametro deprecato
                                              #model='command_and_search',
                                              single_utterance=True)
        self._output_audio_config = OutputAudioConfig(
                audio_encoding=OutputAudioEncoding.OUTPUT_AUDIO_ENCODING_LINEAR_16
        )


       
        #----------------------------------------------------------------------------------
        # Create a DIALOGFLOW session
        #----------------------------------------------------------------------------------
        session_id = str(uuid4())  # Random
        
        self._session_cli = dialogflow_v2.SessionsClient()
        self._session = self._session_cli.session_path(project_id, session_id)
        rospy.logdebug("DF_CLIENT: Session Path: {}".format(self._session))
        '''
        ###############################################################################
        ###############################################################################
         '''


        # dialogflow ros  -----------------------------------------------------------------
        results_topic = rospy.get_param('/dialogflow_client/results_topic',
                                        '/dialogflow_client/results')
        self._results_pub = rospy.Publisher(results_topic, DialogflowResult, queue_size=10)


        rospy.Subscriber("/voice", SpeechRecognitionCandidates, self._AndroidVoice2text_cb)
        
        #----------------------------------------------------------------------------------


 
        '''
        I subscribe ai tutti i topics per i quali devo poter rispondere a voce
        sono in dialogflow_mycommands.py
        '''

        #  advertise di tutti i comandi eseguibili a voce-------------------------
        self.pub_chatter = rospy.Publisher('/chatter',String,queue_size=10)
        self.pub_faretto = rospy.Publisher("/faretto", Bool, queue_size=1)
        self.pub_laser = rospy.Publisher("/laser", Bool, queue_size=1)
        self.pub_start_followme = rospy.Publisher("/start_followme", Bool, queue_size=1)
        self.pub_cmd_vel = rospy.Publisher("/cmd_vel",Twist, queue_size=1)
        self.pub_targetPose = rospy.Publisher("/target_pose",Twist, queue_size=1)
        #-------------------------------------------------------------------------

        # Esecutore comandi --------------------------
        self.myCmdParser = DialogflowCommandExecutor()



        #----------------------------------------------------------------------------------
        #
        # inizializzazione
        #
        #-----------------------------------------------------------------------------------
        self.msg_chatter = String()

        print("==USA L'APP ROS VOICE RECOGNITION SU ANDROID PER CONVERTIRE LA VOCE IN TESTO ==\n")



    # ========================================= #
    #           speech macro                    #
    # ========================================= #
    def speech(self, msg):
        self.pub_chatter.publish(msg)
        print("Chatter:",msg)


    # ========================================= #
    #           Command parser                  #
    # ========================================= #
    #self.myCmdParser.command_parser = DialogflowCommandExecutor()




    # ==================================== #
    #           Utility Functions          #
    # ==================================== #

    def _signal_handler(self, signal, frame):
        rospy.logwarn("\nDF_CLIENT: SIGINT caught!")
        rospy.loginfo("Totale Chiamate a Dialogflow:{} ".format(self.contaChiamateApi))
        self.exit()




    # ==================================== #
    #           Elaboro i comandi          #
    # ==================================== #
    def _elabora_comandi_robot(self,final_result):
        '''
        #Elaboro il comando se l'intent non è vuoto
        '''
        if (final_result.intent.display_name != ''):

            self.myCmdParser.command_parser(final_result.intent.display_name,final_result.parameters )
        else:
            print("\n\n### Nulla da elaborare ###\n\n")


    #
    #
    # ========================================= #
    #           ROS C A L L B A C K             #
    # ========================================= #
    def _AndroidVoice2text_cb(self, voice):
        # Prendo la prima trascrizione (la più probabile)
        txt = voice.transcript[0]
        print(txt)
        #self.speech('Ho capito ' + txt)

        #Chiamo Dialogflow
        new_msg = DialogflowRequest(query_text=txt)
        response_query_result = self.detect_intent_text(new_msg)

        self.speech(response_query_result.fulfillment_text )
        # stampo i risultati
        #========= BEGIN PRINTOUT =============
        rospy.loginfo(utils.output.print_result(response_query_result))
        #=========== END PRINTOUT =================


        self._elabora_comandi_robot(response_query_result)

        #converto l'intent in messaggio ROS
        df_msg = utils.converters.result_struct_to_msg(response_query_result)





    # ================================================================================ #
    # ================================================================================ #
    #
    #           Dialogflow Functions           #
    #
    # ================================================================================ #
    # ================================================================================ #
    #
    #
    # ======================================== #
    #  Chiama Dialogflow passando un testo     #
    # ======================================== #
    def detect_intent_text(self, msg):
        """Use the Dialogflow API to detect a user's intent. Goto the Dialogflow
        console to define intents and params.
        :param msg: DialogflowRequest msg
        :return query_result: Dialogflow's query_result with action parameters
        :rtype: DialogflowResult
        """
        # Create the Query Input
        text_input = TextInput(text=msg.query_text, language_code=self._language_code)
        query_input = QueryInput(text=text_input)
        # Create QueryParameters
        user_contexts = utils.converters.contexts_msg_to_struct(msg.contexts)
        self.last_contexts = utils.converters.contexts_msg_to_struct(self.last_contexts)
        contexts = self.last_contexts + user_contexts
        params = QueryParameters(contexts=contexts)
        try:
            self.contaChiamateApi +=1 #incremento il contatore chiamate Api
            '''            
                    response = self._session_cli.detect_intent(
                    session=self._session,
                    query_input=query_input,
                    query_params=params,
                    output_audio_config=self._output_audio_config)
            '''
            response = self._session_cli.detect_intent(
                    session=self._session,
                    query_input=query_input,
                    query_params=params
                    
            )

        except google.api_core.exceptions.Cancelled as c:
            rospy.logwarn("DF_CLIENT: Caught a Google API Client cancelled "
                          "exception. Check request format!:\n{}".format(c))
        except google.api_core.exceptions.Unknown as u:
            rospy.logwarn("DF_CLIENT: Unknown Exception Caught:\n{}".format(u))
        except google.api_core.exceptions.ServiceUnavailable:
            rospy.logwarn("DF_CLIENT: Deadline exceeded exception caught. The response "
                          "took too long or you aren't connected to the internet!")
        except google.api_core.exceptions.DeadlineExceeded as u:
            rospy.logwarn("DF_CLIENT: DeadlineExceeded Exception Caught:\n{}".format(u))
        else:
            if response is None:
                rospy.logwarn("DF_CLIENT: No response received!")
                return None

            # Salvo il contesto
            self.last_contexts = utils.converters.contexts_struct_to_msg(response.query_result.output_contexts)
            



            # Ritorno la struttura dell'Intent riconosciuto
            return response.query_result



    # -------------- #
    #  Main          #
    # -------------- #
    def start(self):

        """Start the dialogflow client"""
        msg=String("Okey conversiamo un po")
        self.speech(msg)


            

        rospy.loginfo("DF_CLIENT: Spinning... (no snowboy)")
        #while True:            
        #    self.detect_intent_stream(return_result=False)
            
        rospy.spin()




    def exit(self):
        """Close as cleanly as possible"""
        rospy.loginfo("DF_CLIENT: Shutting down")
        self.audio.terminate()
        
        exit()


if __name__ == '__main__':
    rospy.init_node('dialogflow_client5')
    df = MyDialogflowClient()
    df.start()
    
