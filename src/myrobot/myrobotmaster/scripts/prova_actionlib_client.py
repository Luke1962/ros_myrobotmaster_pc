#!/usr/bin/env python2

import rospy
import actionlib
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal

waypoints = [
    [(0.2, 0.0, 0.0) , (0.0, 0.0, 0.0, 1.0)],
    [(0.2,-0.50, 0.0), (0.0, 0.0, 0.0, 1.0)]
]

def goal_pose(pose):
    goal_pose = MoveBaseGoal()
    goal_pose.target_pose.header.frame_id = 'map'
    goal_pose.target_pose.pose.position.x = pose[0][0]
    goal_pose.target_pose.pose.position.y = pose[0][1]
    goal_pose.target_pose.pose.position.z = pose[0][2]
    goal_pose.target_pose.pose.orientation.x =   pose[1][0]
    goal_pose.target_pose.pose.orientation.x =   pose[1][1]
    goal_pose.target_pose.pose.orientation.x =   pose[1][2]
    goal_pose.target_pose.pose.orientation.x =   pose[1][3]
    
    return goal_pose

def cleanup(self):
    rospy.loginfo("Shutting down talkback node...")

def main():
    rospy.init_node('patrol')
    rospy.on_shutdown(cleanup)
 
    client = actionlib.SimpleActionClient('move_base', MoveBaseAction)
    
    rospy.loginfo("Waiting for move_base action server...")
    wait = client.wait_for_server(rospy.Duration(5.0))
    if not wait:
        rospy.logerr("Action server not available!")
        rospy.signal_shutdown("Action server not available!")
        return
    rospy.loginfo("Connected to move base server")
    rospy.loginfo("Starting goals achievements ...")
        

    print("Start")
    while True:
        for pose in waypoints:
            print("goal: ", goal)
            goal = goal_pose
            client.send_goal(goal)
            client.wait_for_result()

if __name__ == '__main__':
    main()
