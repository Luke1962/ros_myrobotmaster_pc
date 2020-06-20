#!/usr/bin/env python
# C



PKG='actionlib'
import roslib; roslib.load_manifest(PKG)
import rospy

import sys

from actionlib.simple_action_server import SimpleActionServer
from actionlib.msg import TestAction,TestFeedback


class RefSimpleServer (SimpleActionServer):

    def __init__(self,name):
        action_spec=TestAction
        SimpleActionServer.__init__(self,name,action_spec,self.goal_callback, False);
        self.start()
        rospy.loginfo("Creating SimpleActionServer [%s]\n", name);


    def goal_callback(self,goal):

        rospy.loginfo("Got goal %d", int(goal.goal))
        if goal.goal == 1:
            self.set_succeeded(None, "The ref server has succeeded");
        elif goal.goal == 2:
            self.set_aborted(None, "The ref server has aborted");

        elif goal.goal == 3:
            self.set_aborted(None, "The simple action server can't reject goals");


        elif goal.goal == 4:
            self.set_aborted(None, "Simple server can't save goals");


        elif goal.goal == 5:
            self.set_aborted(None, "Simple server can't save goals");

        elif goal.goal == 6:
            self.set_aborted(None, "Simple server can't save goals");



        elif goal.goal == 7:
            self.set_aborted(None, "Simple server can't save goals");

        elif goal.goal == 8:
            self.set_aborted(None, "Simple server can't save goals");

        elif goal.goal == 9:
            rospy.sleep(1);
            rospy.loginfo("Sending feedback")
            self.publish_feedback(TestFeedback(9)); #by the goal ID
            rospy.sleep(1);
            self.set_succeeded(None, "The ref server has succeeded");


        else:
            pass

if __name__=="__main__":
  rospy.init_node("ref_simple_server");
  ref_server = RefSimpleServer("actionlib_server");

  rospy.spin();


