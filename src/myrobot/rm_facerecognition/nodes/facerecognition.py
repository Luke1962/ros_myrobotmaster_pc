#!/usr/bin/env python3
# -------------------------------------------------------------------------------------------
# versione integrata in ROS tratta da https://github.com/ageitgey/face_recognition
# se non trova face_recognition, prova sudo python -m pip install face_recognition
# VA ESEGUITO CON PYTHON2 
# -------------------------------------------------------------------------------------------
'''
ho compilato per Python3 anche ros_bridge 
catkin_make -DCATKIN_WHITELIST_PACKAGES="rm_facerecognition;cv_bridge" -DCMAKE_BUILD_TYPE=Release -DPYTHON_EXECUTABLE=/usr/bin/python3  -DPYTHON_INCLUDE_DIR=/usr/include/python3.6m  -DPYTHON_LIBRARY=/usr/lib/x86_64-linux-gnu/libpython3.6m.so

All'uscita del nodo $PYTHONPATH era
/home/luca/ros/install/lib/python3/dist-packages:/home/luca/ros/devel/lib/python3/dist-packages:/opt/ros/melodic/lib/python2.7/dist-packages


'''
import sys
import time
print(sys.path)
#sys.path.remove('/opt/ros/melodic/lib/python2.7/dist-packages')# in order to import cv2 under python3
import numpy as np 


#from ros_face_recognition.srv import Face, Name, NameResponse, FaceResponse, Detect, DetectResponse
#from ros_face_recognition.msg import Box

#sys.path.append('/opt/ros/melodic/lib/python2.7/dist-packages') # serve per importare cvbridge
sys.path.append('/home/luca/ros/install/lib/python3/dist-packages') # serve per importare cvbridge
from cv_bridge import CvBridge, CvBridgeError
from sensor_msgs.msg import Image, CompressedImage
from std_msgs.msg import String
import cv2
import face_recognition  #usa le librerie dlib
import roslib
import rospy
import sys
from rm_facerecognition.msg import DetectedFace, DetectedFaceArray




class myFaceRecognition():
    #def __init__(self, node_name):
    def __init__(self, node_name):
        #super(myFaceRecognition, self).__init__(node_name)
        rospy.init_node(node_name)
 
        self.node_name = node_name
        self.keystroke = None
        rospy.loginfo("Starting node " + str(node_name))
        print("OpenCV version " + cv2.__version__)


        print("\nLoading reference images, please wait...")
        imgpath = "/home/luca/ros/src/myrobot/rm_facerecognition/data/"
        # Load a sample picture and learn how to recognize it.
        luca_image = face_recognition.load_image_file(imgpath + "luca.jpg")
        luca_face_encoding = face_recognition.face_encodings(luca_image)[0]

        # Load a second sample picture and learn how to recognize it.
        vinicia_image = face_recognition.load_image_file(
            imgpath + "vinicia.jpg")
        vinicia_face_encoding = face_recognition.face_encodings(vinicia_image)[
            0]
        # Create arrays of known face encodings and their names
        self.known_face_encodings = [
            luca_face_encoding,
            vinicia_face_encoding
        ]
        self.known_face_names = [
            "luca",
            "vinicia"
        ]
        print("Loaded reference images:",self.known_face_names)

        # Initialize some variables
        self.face_locations = []
        self.face_encodings = []
        self.face_names = []

        self.face_detections = DetectedFaceArray()
        self.face = DetectedFace()

        self.marker_image = None
        self.keep_marker_history = None
        self.night_mode = None
        self.show_boxes = True
        self.show_text = True
        self.track_box = None
        self.bridge = CvBridge()

        self.frame_cv2 = None
        self.frame_width = None
        self.frame_height = None
        self.frame_size = (0, 0)

        self.detect_box = None
        self.cvdepth_to_numpy_depth = {cv2.CV_8U: 'uint8', cv2.CV_8S: 'int8', cv2.CV_16U: 'uint16',
                                       cv2.CV_16S: 'int16', cv2.CV_32S: 'int32', cv2.CV_32F: 'float32',
                                       cv2.CV_64F: 'float64'}

        self.cps = 0
        self.cps_values = None

        # Subscribe to the image and depth topics and set the appropriate callbacks
        # The image topic names can be remapped in the appropriate launch file
        self.topic_sub_image= "/camera/image_raw"
        self.image_sub = rospy.Subscriber( self.topic_sub_image, Image, self.image_callback, queue_size=1)
        print("Subscribe to image Topic:",  self.topic_sub_image)

        self.topic_pub_image = "/recognition"
        self.pub_image = rospy.Publisher(self.topic_pub_image, Image, queue_size=1)
        print("Publishing Image with recognition to  topic:", self.topic_pub_image)
        #self.pub_imgcompressed = rospy.Publisher("/recognition_image_compressed", CompressedImage, queue_size=1)

        self.detections_pub = rospy.Publisher("/face_detections", DetectedFaceArray, queue_size=1)
        self.detection_pub = rospy.Publisher( "/face_detection", DetectedFace, queue_size=1)

        self.msg_chatter =String()
        self.pub_speech_coded = rospy.Publisher("/speech_coded", String, queue_size=1)

        #self.recognition_interval_duration = rospy.Duration.from_sec(1 / rospy.get_param("~rate", 1))
        #self.prevTime =  rospy.get_rostime()
        #self.now  = rospy.get_rostime()
        self.recognition_interval_duration = 1.0 / 3.0 # rospy.get_param("~rate", 1)
        self.start = time.time()
        print("Recognition rate Hz:", 1/self.recognition_interval_duration)

        self.lastCodedSpeech = ""

        print("Started...")

    def speech_coded_norepeat(self,data):
        #if self.lastCodedSpeech != data:
        self.msg_chatter.data = data
        self.pub_speech_coded.publish(self.msg_chatter)
        self.lastCodedSpeech = data

    ###########################################################
    #def image_callback
    ###########################################################
    def image_callback(self, data):

        #print("image_callback")

        
        #ritorna subito se non e' trascorso l'intervallo prestabilito
        #if rospy.get_rostime() - self.prevTime <  self.recognition_interval_duration
        if ( ( time.time() - self.start ) <  self.recognition_interval_duration):
            return

        # Time this loop to get cycles per second
        self.start = time.time()

        # Convert the ROS image to OpenCV
        # vedi http://wiki.ros.org/cv_bridge/Tutorials/ConvertingBetweenROSImagesAndOpenCVImagesPython
        try:
            frame_cv2 = self.bridge.imgmsg_to_cv2(data, "bgr8")
        except CvBridgeError as e:
             print(e)

        # Store the frame width and height in a pair of global variables
        if self.frame_width is None:
            self.frame_size = (frame_cv2.shape[1], frame_cv2.shape[0])
            self.frame_width, self.frame_height = self.frame_size

        # Copy the current frame to the global image in case we need it elsewhere
        self.frame_cv2 = frame_cv2.copy()

        # Process the image to detect and track objects or features
        processed_image = self.process_image(self.frame_cv2)

        # Make a global copy
        self.processed_image = processed_image.copy()

        try:
            ros_img = self.bridge.cv2_to_imgmsg(self.processed_image, "bgr8")
            self.pub_image.publish(ros_img)

            #cmprsmsg = self.bridge.cv2_to_compressed_imgmsg(self.processed_image)  # Convert the image to a compress message
            #self.pub_imgcompressed.publish(cmprsmsg)
			
        except CvBridgeError as e:
            print(e)

        # Publish faces names and positions
        self.detections_pub.publish(self.face_detections)

        # Compute the time for this loop and estimate CPS as a running average
        end = time.time()
        duration = end - self.start
        fps = int(1.0 / duration)
        rospy.loginfo_throttle(3, "Max fps processing capability:" + str(fps))  ## 6 o7 fps con immagine di 320x240
        

        # Update the image display
        #cv2.imshow(self.node_name, self.processed_image)

    ###########################################################
    #def process_image
    ###########################################################
    def process_image(self, cv_frame):
        try:

            # Resize frame of video to 1/5 size for faster face recognition processing
            small_frame = cv2.resize(cv_frame, (0, 0), fx=0.5, fy=0.5)

            # Convert the image from BGR color (which OpenCV uses) to RGB color (which face_recognition uses)
            rgb_small_frame = small_frame[:, :, ::-1]

            # Find all the faces and face encodings in the current frame of video
            self.face_locations = face_recognition.face_locations(
                rgb_small_frame)
            self.face_encodings = face_recognition.face_encodings(
                rgb_small_frame, self.face_locations)

            self.face_names = []
            for self.face_encoding in self.face_encodings:
                # See if the face is a match for the known face(s)
                matches = face_recognition.compare_faces(
                    self.known_face_encodings, self.face_encoding)
                name = "Unknown"

                # # If a match was found in known_face_encodings, just use the first one.
                # if True in matches:
                #     first_match_index = matches.index(True)
                #     name = self.known_face_names[first_match_index]

                # Or instead, use the known face with the smallest distance to the new face
                face_distances = face_recognition.face_distance(
                    self.known_face_encodings, self.face_encoding)
                best_match_index = np.argmin(face_distances)
                #print("best_match_index:" + str(best_match_index))
                if matches[best_match_index]:
                    name = self.known_face_names[best_match_index]

                self.face_names.append(name)
                print("Riconosco : " + name)

            # Display the results
            for (top, right, bottom, left), name in zip(self.face_locations, self.face_names):
                # Scale back up face locations since the frame we detected in was scaled to 1/2 size
                top *= 2
                right *= 2
                bottom *= 2
                left *= 2

                # Store center position x,y and size for estimating distance
                pos_x = (right + left)/2
                pos_y = (top + bottom)/2
                pos_z = (right - left)/float(self.frame_width)
				
                print("at x"+str(pos_x) + ", y " +
                      str(pos_y) + ", z "+str(pos_z) + ",  width " + str(self.frame_width))

                # Draw a box around the face
                cv2.rectangle(cv_frame, (left, top),  (right, bottom), (0,  255, 0), 2)
                # person Name
                font = cv2.FONT_HERSHEY_DUPLEX
                cv2.putText(cv_frame, name, (left + 6, bottom - 6), font, 0.5, (255, 0, 0), 1)

                # create message----------------------
                self.face.name = name
                self.face.x = pos_x
                self.face.y = pos_y
                self.face.size = pos_z
                self.detection_pub.publish(self.face)
                #self.face_detections.append(self.face)

                msg_chatter = "speech_ciao_"+name  # il nome deve essere minuscolo
                
                self.speech_coded_norepeat(msg_chatter)
        except AttributeError:
            pass

        #return cv_image
        return cv_frame


if __name__ == '__main__':
    try:
        node_name = "facerecognition"
        myFaceRecognition(node_name)
        try:
            rospy.init_node(node_name)
        except:
            pass
        rospy.spin()
    except KeyboardInterrupt:
        print("Shutting down facerecognition node.")
        # cv.DestroyAllWindows()

        # Release handle to the webcam
        video_capture.release()
        cv2.destroyAllWindows()
