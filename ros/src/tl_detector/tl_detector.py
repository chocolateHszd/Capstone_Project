#!/usr/bin/env python
import rospy
from std_msgs.msg import Int32
from geometry_msgs.msg import PoseStamped, Pose
from styx_msgs.msg import TrafficLightArray, TrafficLight
from styx_msgs.msg import Lane
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
from light_classification.tl_classifier import TLClassifier
import tf
import cv2
import yaml
import math


STATE_COUNT_THRESHOLD = 3

class TLDetector(object):
    def __init__(self):
        rospy.init_node('tl_detector', log_level=rospy.DEBUG)

        self.pose = None
        self.waypoints = None
        self.camera_image = None
        self.light_classifier = None
        self.lights = []
        self.skip_next = False
        self.skip_count = 0
        self.closest_stop_line_index = -1
        self.detected_not_red = 0
        self.traffic_light_current_color = TrafficLight.UNKNOWN

        self.listener = tf.TransformListener()

        self.state = TrafficLight.UNKNOWN
        self.last_state = TrafficLight.UNKNOWN
        self.last_wp = -1
        self.state_count = 0

        sub1 = rospy.Subscriber('/current_pose', PoseStamped, self.pose_cb)
        sub2 = rospy.Subscriber('/base_waypoints', Lane, self.waypoints_cb)

        '''
        /vehicle/traffic_lights provides you with the location of the traffic light in 3D map space and
        helps you acquire an accurate ground truth data source for the traffic light
        classifier by sending the current color state of all traffic lights in the
        simulator. When testing on the vehicle, the color state will not be available. You'll need to
        rely on the position of the light and the camera image to predict it.
        '''
        sub3 = rospy.Subscriber('/vehicle/traffic_lights', TrafficLightArray, self.traffic_cb)
        sub6 = rospy.Subscriber('/image_color', Image, self.image_cb)

        config_string = rospy.get_param("/traffic_light_config")

        ssd_model_path = rospy.get_param("/ssd_model_path")
        traffic_light_model_path = rospy.get_param("/traffic_light_model_path")

        save_path = rospy.get_param("/save_path")
        self.config = yaml.load(config_string)

        self.upcoming_traffic_light_pub = rospy.Publisher('/traffic_waypoint', Int32, queue_size=1)
        self.upcoming_traffic_light_state_pub = rospy.Publisher('/traffic_light_state', Int32, queue_size=1)

        self.bridge = CvBridge()

        self.light_classifier = TLClassifier(traffic_light_model_path = traffic_light_model_path, ssd_model_path=ssd_model_path, save_path=save_path)
        rospy.loginfo("Classifier Loaded!")

        rospy.spin()

    def pose_cb(self, msg):
        self.pose = msg

    def waypoints_cb(self, waypoints):
        self.waypoints = waypoints.waypoints

    def traffic_cb(self, msg):
        self.lights = msg.lights


    def image_cb(self, msg):
        """Identifies red lights in the incoming camera image and publishes the index
            of the waypoint closest to the red light's stop line to /traffic_waypoint

        Args:
            msg (Image): image from car-mounted camera

        """
        self.has_image = True
        self.camera_image = msg
        light_wp, state = self.process_traffic_lights()

        '''
        Publish upcoming red lights at camera frequency.
        Each predicted state has to occur `STATE_COUNT_THRESHOLD` number
        of times till we start using it. Otherwise the previous stable state is
        used.
        # '''
        # only publish when light is red
        
        # if state == TrafficLight.RED :
        #     self.detected_not_red = 0
        #     if self.state != state:
        #         self.state_count = 0
        #         self.state = state
        #     elif self.state_count >= STATE_COUNT_THRESHOLD:
        #         self.last_state = self.state
        #         light_wp = light_wp if state == TrafficLight.RED else -1
        #         self.last_wp = light_wp
        #         if light_wp > -1:
        #             # rospy.loginfo ("* index:{} color:{}".format(light_wp,self.state))
        #             self.upcoming_red_light_pub.publish(Int32(light_wp))
        #     else:
        #         if light_wp > -1:
        #             # rospy.loginfo("* index:{} color:{}".format(self.last_wp,self.state))
        #             self.upcoming_red_light_pub.publish(Int32(self.last_wp))
                    
        #     self.state_count += 1
        # else:
        #     if self.detected_not_red <3:
        #         self.upcoming_red_light_pub.publish(Int32(-1))
        #         self.detected_not_red +=1
        # rospy.loginfo('v_error img recieved')

        # if light_wp > -1:
        if self.last_state != state:
            self.last_state = state
            self.state_count = 0
        else:
            if self.state_count >= 3:
                self.upcoming_traffic_light_pub.publish(Int32(light_wp))
                self.upcoming_traffic_light_state_pub.publish(Int32(state))
            self.state_count+=1
        


    def get_closest_waypoint(self, pose):
        """Identifies the closest path waypoint to the given position
            https://en.wikipedia.org/wiki/Closest_pair_of_points_problem
        Args:
            pose (Pose): position to match a waypoint to

        Returns:
            int: index of the closest waypoint in self.waypoints

        """
        #TODO implemented***
        min_index = 0
        if len(self.waypoints) >0:
            min_distance = float('inf')
            iterator = 0
            for waypoint in self.waypoints:
                waypoint_position = waypoint.pose.pose.position
                target_postion = pose.position
                distance = waypoint_position.x - target_postion.x
                if distance < min_distance  and distance>0 :
                    min_distance = distance
                    min_index = iterator
                iterator+=1
        return min_index

    def get_closest_light(self, pose):
        """Identifies the closest light to the given position
            https://en.wikipedia.org/wiki/Closest_pair_of_points_problem
        Args:
            pose (Pose): position to match a light to

        Returns:
            int: index of the closest light in self.lights

        """
        #TODO implemented***
        close_light_position = None
        if len(self.lights) >0:
            min_distance = float('inf')
            iterator = 0
            for light in self.lights:
                light_position = light.pose.pose.position
                target_postion = pose.position
                # dont need y & z for considering distance between trffic light
                distance = light_position.x - target_postion.x
                if distance < min_distance  and distance >0:
                    min_distance = distance
                    close_light_position = light_position
                iterator+=1
        return close_light_position


    def get_closest_stopline_wp(self, stop_line_coords):
        """Identifies the closest light to the given position
            https://en.wikipedia.org/wiki/Closest_pair_of_points_problem
        Args:
            pose (Pose): position to match a light to

        Returns:
            int: index of the closest light in self.lights

        """
        #TODO implemented***
        min_index = 0
        min_distance = float('-inf')
        iterator = 0
        for waypoint in self.waypoints:
            waypoint_position = waypoint.pose.pose.position
            distance = waypoint_position.x - stop_line_coords[0]
            if distance > min_distance and distance<=0: # and waypoint_position.x <= stop_line_coords[0]:
                min_distance = distance
                min_index = iterator
            iterator+=1
        return min_index


    def get_light_state(self, light, light_to_car_distance):
        """Determines the current color of the traffic light

        Args:
            light (TrafficLight): light to classify

        Returns:
            int: ID of traffic light color (specified in styx_msgs/TrafficLight)

        """
        if(not self.has_image):
            self.prev_light_loc = None
            return False

        cv_image = self.bridge.imgmsg_to_cv2(self.camera_image, "rgb8")

        #Get classification
        return self.light_classifier.get_classification(cv_image, light_to_car_distance)


    def process_traffic_lights(self):
        """Finds closest visible traffic light, if one exists, and determines its
            location and color

        Returns:
            int: index of waypoint closes to the upcoming stop line for a traffic light (-1 if none exists)
            int: ID of traffic light color (specified in styx_msgs/TrafficLight)

        """
        light = None
        # List of positions that correspond to the line to stop in front of for a given intersection
        stop_line_positions = self.config['stop_line_positions']

        if self.waypoints is not None and self.lights is not None and self.light_classifier is not None:
            if self.pose != None:
                car_position_index = self.get_closest_waypoint(self.pose.pose)
                light_position = self.get_closest_light(self.pose.pose)
                car_position = self.waypoints[car_position_index].pose.pose.position

                if light_position != None and car_position !=None:
                    light_to_car_distance = (light_position.x - car_position.x)
                    
                    # Note: Uncomment if simulator is runnning slow:
                    # limit distance ssd starts detecting from 40 to 20 starts cutting traffic light from top
                    if light_to_car_distance > 0 : # and light_to_car_distance >= 20 and light_to_car_distance <= 40: 
                        closest_stop_line = float('-inf')
                        
                        # find the closest stopline to the traffic light
                        count = 0
                        stop_line_index = -1
                        for stop_line in stop_line_positions:
                            distance = stop_line[0] - light_position.x
                            if distance <=0 and distance > closest_stop_line:
                                closest_stop_line = distance
                                stop_line_index = count
                            count +=1 

                        if stop_line_index > -1:
                            self.closest_stop_line_index = self.get_closest_stopline_wp(stop_line_positions[stop_line_index])
                            light = True

        if light:
            traffic_light_current_color = self.get_light_state(light,light_to_car_distance)
            if traffic_light_current_color == 0:
                rospy.loginfo('class RED')
            elif traffic_light_current_color == 1:
                rospy.loginfo('class YELLOW')
            elif traffic_light_current_color == 2:
                rospy.loginfo('class GREEN')
            elif traffic_light_current_color == 4:
                rospy.loginfo('class UNKNOWN')
            return self.closest_stop_line_index , traffic_light_current_color
        
        return -1, TrafficLight.UNKNOWN

if __name__ == '__main__':
    try:
        TLDetector()
    except rospy.ROSInterruptException:
        rospy.logerr('Could not start traffic node.')
