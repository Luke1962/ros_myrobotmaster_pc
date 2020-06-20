#!/usr/bin/env python3

'''
# mie annotazioni-------------------------------------------
# Questa versione usa l'App Android ROS Voice
per convertire la voce in testo


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



# Snowboy
sys.path.append('/home/luca/ros/src/myrobot/dialogflow_ros/scripts/snowboy')#per importare utils
#sys.path.append(os.path.join(os.path.dirname(__file__), '../snowboy'))
#sys.path.append("/usr/local/lib/python3.6/dist-packages/snowboy-1.3.0-py3.6.egg/snowboy")
import snowboydecoder

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
        self.PLAY_GOOGLE_AUDIO = rospy.get_param('/dialogflow_client/play_google_audio', False)      
        self.PLAY_LOCAL_AUDIO = rospy.get_param('/dialogflow_client/play_local_audio', True)

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
        self._create_audio_output()
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
        requests_topic = rospy.get_param('/dialogflow_client/requests_topic',
                                         '/dialogflow_client/requests')
        text_event_topic = requests_topic + '/string_event'
        msg_req_topic = requests_topic + '/df_msg'
        event_req_topic = requests_topic + '/df_event'
        text_req_topic = requests_topic + '/string_msg'
        self._results_pub = rospy.Publisher(results_topic, DialogflowResult, queue_size=10)
        rospy.Subscriber(text_req_topic, String, self._text_request_cb) # richiesta in formato testo
        rospy.Subscriber(text_event_topic, String, self._text_event_cb)
        rospy.Subscriber(msg_req_topic, DialogflowRequest, self._msg_request_cb)
        rospy.Subscriber(event_req_topic, DialogflowEvent, self._event_request_cb)

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
        if self.PLAY_LOCAL_AUDIO:
            self.msg_chatter = String()

        if self.USE_AUDIO_SERVER:
            print("==USO AUDIOSERVER==")
        else:
            print("==USO IL MICROFONO==")

        if self.use_snowboy:
            # Setup snowboy
            self.speech(" uso snowboy")
            self.detector = snowboydecoder.HotwordDetector(self.model_path,  sensitivity=self.snowboy_sensitivity)
            print("\n\n***Using SNOWBOY model {} \n Sensitivity:  {} \n***\n\n".format(self.model_path,self.snowboy_sensitivity )  )          
            
        else:
            print("\n\n***NON USO SNOWBOY ***")
            self.speech("non uso snowboy")


    # ========================================= #
    #           speech macro                    #
    # ========================================= #
    def speech(self, msg):
        self.pub_chatter.publish(msg)
        print("Chatter:",msg)

    def speech_df_msg(self, df_response):
        df_msg = utils.converters.result_struct_to_msg(df_response.query_result)        
        #print("Chatter:",msg)
        speech(df_msg)





    # ========================================= #
    #           Command parser                  #
    # ========================================= #
    #self.myCmdParser.command_parser = DialogflowCommandExecutor()

    # ================================== #
    #           Setters/Getters          #
    # ================================== #

    def get_language_code(self):
        return self._language_code

    def set_language_code(self, language_code):
        assert isinstance(language_code, str), "Language code must be a string!"
        self._language_code = language_code

    # ==================================== #
    #           Utility Functions          #
    # ==================================== #

    def _signal_handler(self, signal, frame):
        rospy.logwarn("\nDF_CLIENT: SIGINT caught!")
        rospy.loginfo("Totale Chiamate a Dialogflow:{} ".format(self.contaChiamateApi))
        self.exit()

    # ----------------- #
    #  Audio Utilities  #
    # ----------------- #

    def _create_audio_output(self):
        """Creates a PyAudio output stream."""
        rospy.logdebug("DF_CLIENT: Creating audio output...")
        self.stream_out = self.audio.open(format=pyaudio.paInt16,
                                          channels=1,
                                          rate=24000,
                                          output=True)

    def _play_stream(self, data):
        """Simple function to play a the output Dialogflow response.
        :param data: Audio in bytes.
        """
        self.stream_out.start_stream()
        self.stream_out.write(data)
        time.sleep(0.2)  # Wait for stream to finish
        self.stream_out.stop_stream()

    # ==================================== #
    #           Elaboro i comandi          #
    # ==================================== #
    def _elabora_comandi_robot(self,final_result):
        '''
        #Elaboro il comando se l'intent non è vuoto
        '''
        if (final_result.intent.display_name != ''):

            self.myCmdParser.command_parser(final_result.intent.display_name,final_result.parameters )


            # Pubblico la risposta di Dialogflow------------------
            #self._results_pub.publish(df_msg)
            #if return_result: return df_msg, final_result
            #return df_msg
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
        self.speech('Ho capito ' + txt)

        #Chiamo Dialogflow
        new_msg = DialogflowRequest(query_text=txt)
        response_query_result = self.detect_intent_text(new_msg)


        # stampo i risultati
        #========= BEGIN PRINTOUT =============
        rospy.loginfo(utils.output.print_result(response_query_result))
        #=========== END PRINTOUT =================

        #local TTS
        if self.PLAY_LOCAL_AUDIO:                 
            #self.speech(final_result.fulfillment_text)
            self.speech(response_query_result.fulfillment_text)

        self._elabora_comandi_robot(response_query_result)

        #converto l'intent in messaggio ROS
        df_msg = utils.converters.result_struct_to_msg(response_query_result)


    def _msg_request_cb(self, msg):
        """ROS Callback that sends text received from a topic to Dialogflow,
        :param msg: A DialogflowRequest message.
        :type msg: DialogflowRequest
        """
        df_msg = self.detect_intent_text(msg)
        rospy.logdebug("DF_CLIENT: Request received:\n{}".format(df_msg))

    def _event_request_cb(self, msg):
        """
        :param msg: DialogflowEvent Message
        :type msg: DialogflowEvent"""
        new_event = utils.converters.events_msg_to_struct(msg)
        self.event_intent(new_event)

    def _text_event_cb(self, msg):
        new_event = EventInput(name=msg.data, language_code=self._language_code)
        self.event_intent(new_event)


    def _text_request_cb(self, msg):
        """ROS Callback that sends text received from a topic to Dialogflow,
        :param msg: A String message.
        :type msg: String
        """
        
        rospy.logdebug("DF_CLIENT: Request received")
        new_msg = DialogflowRequest(query_text=msg.data)
        df_msg = self.detect_intent_text(new_msg)

    # 
    # 
    # 
    # chiamato da detect_intent_stream
    def _generator(self):
        """Generator function that continuously yields audio chunks from the
        buffer. Used to stream data to the Google Speech API Asynchronously.
        :return A streaming request with the audio data.
        First request carries config data per Dialogflow docs.
        :rtype: Iterator[:class:`StreamingDetectIntentRequest`]
        """
        # First message contains session, query_input, and params
        query_input = QueryInput(audio_config=self._audio_config)
        contexts = utils.converters.contexts_msg_to_struct(self.last_contexts)
        params = QueryParameters(contexts=contexts)
        req = StreamingDetectIntentRequest(
                session=self._session,
                query_input=query_input,
                query_params=params,
                single_utterance=True,
                output_audio_config=self._output_audio_config
        )
        yield req

        if self.USE_AUDIO_SERVER:
            #http://effbot.org/zone/python-with-statement.htm
            with AudioServerStream(self.RATE,self.CHUNK,self._server_name) as stream:
                audio_generator = stream.generator()
                for content in audio_generator:                    
                    yield StreamingDetectIntentRequest(input_audio=content)
        else:
            with MicrophoneStream() as stream:
                audio_generator = stream.generator()
                for content in audio_generator:
                    yield StreamingDetectIntentRequest(input_audio=content)

    #
    #
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
            response = self._session_cli.detect_intent(
                    session=self._session,
                    query_input=query_input,
                    query_params=params,
                    output_audio_config=self._output_audio_config
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
            


            # Play audio
            if self.PLAY_GOOGLE_AUDIO:
                self._play_stream(response.output_audio)

            # Ritorno la struttura dell'Intent riconosciuto
            return response.query_result




    #
    #
    #
    #------------------------------------------------------
    # chiamato da _snowboy_callback
    #------------------------------------------------------
    def detect_intent_stream(self, return_result=False):
        """Gets data from an audio generator (mic) and streams it to Dialogflow.
        We use a stream for VAD and single utterance detection."""

        self.contaChiamateApi +=1 #incremento il contatore chiamate Api
        # Generator yields audio chunks.
        requests = self._generator()

        responses = self._session_cli.streaming_detect_intent(requests)  #  <<<<-------Chiamo qui DF
        resp_list = []
        try:
            for response in responses:
                resp_list.append(response)
                rospy.logdebug(
                        'DF_CLIENT: Intermediate transcript: "{}".'.format(
                                response.recognition_result.transcript))
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
            # The response list returns responses in the following order:
            # 1. All intermediate recognition results
            # 2. The Final query recognition result (no audio!)
            # 3. The output audio with config
            final_result = resp_list[-2].query_result  
            final_audio = resp_list[-1]
            self.last_contexts = utils.converters.contexts_struct_to_msg(
                    final_result.output_contexts
            )
            df_msg = utils.converters.result_struct_to_msg(final_result)

            # stampo i risultati
            rospy.loginfo(utils.output.print_result(response.query_result))


            #----------------------------------------------
            #elaboro il comando se l'intent non è vuoto
            #----------------------------------------------
            elabora_comandi_robot(final_result)



    def event_intent(self, event):
        """Send an event message to Dialogflow
        :param event: The ROS event message
        :type event: DialogflowEvent
        :return: The result from dialogflow as a ROS msg
        :rtype: DialogflowResult
        """
        # Convert if needed
        if type(event) is DialogflowEvent:
            event_input = utils.converters.events_msg_to_struct(event)
        else:
            event_input = event

        query_input = QueryInput(event=event_input)
        params = utils.converters.create_query_parameters(
                contexts=self.last_contexts
        )
        response = self._session_cli.detect_intent(
                session=self._session,
                query_input=query_input,
                query_params=params,
                output_audio_config=self._output_audio_config
        )
        df_msg = utils.converters.result_struct_to_msg(response.query_result)
        if self.PLAY_GOOGLE_AUDIO:
            self._play_stream(response.output_audio)
        return df_msg



    # -------------- #
    #  SNOWBOY       #
    # -------------- #
    def play_ding(self):
        """Simple function to play a Ding sound."""
        self.stream_out.start_stream()
        self.stream_out.write(self.ding_data)
        time.sleep(0.2)
        self.stream_out.stop_stream()

    def _interrupt_callback(self):
        return self.interrupted

    def _snowboy_callback(self):
        self.play_ding()
        rospy.loginfo("Hotword detected!")
        # self.df_client = DialogflowClient(last_contexts=self.last_contexts)
        #df_msg, res = self.detect_intent_stream(return_result=True)
        self.detect_intent_stream(return_result=True)
        #self.last_contexts = res.output_contexts





    # -------------- #
    #  Main          #
    # -------------- #
    def start(self):

        """Start the dialogflow client"""
        msg=String("Okey conversiamo un po")
        self.speech(msg)

        if self.use_snowboy:
            rospy.loginfo("DF_CLIENT: Spinning... (waiting snowboy hotword)")
            while True:
                #Todo: verificare presenza audio prima di inviare la richiesta
                    try:
                        self.detector.start(detected_callback=self._snowboy_callback,
                                            interrupt_check=self._interrupt_callback,
                                            sleep_time=0.03)
                        print("\n...")
                    except KeyboardInterrupt:
                        self.exit()
            
        else:
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
    
