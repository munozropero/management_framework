#!/usr/bin/env python


import threading
import zmq
import time

import logging

from thrift import TSerialization
import  Structures.ttypes as thrift

class Group:		

	def __init__(self, name, members, ec_session):
		self.name = name
		self.members = {}
		for node_name in members:
			self.members[node_name] = ec_session.nodes[node_name]
		logging.debug("Group members:%s", self.members)
		# self.members = [ec_session.nodes[i] for i in members] 	# The user gives a list of name keys, what self.members must contain
													# the actual instances of Node
		# self.inst_names = []  						# CHECK: Was this necessary at the end?


class Node:

	# state = {Ready, Irresponsive}
	# child_resources = {applications: { 'iperf_client': <Apptracker object} , ifaces: {'wlan0': <Iface thrift structure> , }  }


	def __init__(self, rc_nodeinfo):
		# logging.debug("Creating Node: %s", rc_nodeinfo.node_name)		# DEBUG
		self.name = rc_nodeinfo.node_name
		self.os = rc_nodeinfo.os
		self.state = "Ready" 				# This object is being created because a Node registered to the EC
		self.last_report = time.time()		# so obviously it is "Ready" and being updated right now
		# All the events whose triggering events depend on the 'state' variable. This list contains Event objects.
		self.dependent_events = []		 
		self.child_resources = {"ifaces":  {}, "applications": {} }
		if rc_nodeinfo.ifaces:
			for iface in rc_nodeinfo.ifaces: # Map Iface structure to this object instance
				self.child_resources[ifaces][iface.if_name]=Iface(if_name=iface.if_name, phy=iface.phy, mode=iface.mode, channel=iface.channel)


	# Returns the Apptracker object from the application dictionary inside child_resources
	def app(self, inst_name):
		return self.child_resources['applications'][inst_name]
	
	# Returns the Iface thrift structure from the iface dictionary inside child_resources
	def iface(self, iface_name):
		return self.child_resources['ifaces'][iface_name]
	

class AppTracker:


	def __init__(self, inst_name):
		self.state = 'Created'
		self.inst_name = inst_name
		self.dependent_events = [] # Events depending on this app state to be triggered. The list contains Event objects
		#self.app_instance		# The AppInstance thrift structure that was passed with 'addApplication'.
								# DECISION: Is this going to be necessary?? So far it has no use.


class Event:		# MUST BE ABLE TO NOTIFY USER = SEND A MESSAGE TO USER OR MAKE SOMEONE SEND IT
	# event_name
	# conditions = {node:{<node_name>: <desired_state>}, {<another_node_name>: <desired_state> }, 
	# 	application: { <node_nameX>: { <inst_name>: <desired_state>}, ..} , { <node_nameY>: { <inst_name>: <desired_state>}, ..}  }
	# conditions_met = {node:{<node_name>: True/False}, {<another_node_name>: True/False }, 
	# 	application: { <node_nameX>: { <inst_name>: True/False }, ..} , { <node_nameY>: { <inst_name>: True/False }, ..}  }

	# bool ready_to_fire
	# bool enabled
	# timer
	# periodic

	# TODO!! 
	# Provide mechanism with keywords such as 'allapps' 'allnodes', etc. To target all of a node/group applications or all nodes
	# CHECK: Further testing of events is needed

	def __init__(self, eventtriger, ec_session): # ec_session must be provided so it can append itself to the monitored resources
		self.event_name = eventtriger.name
		self.ready_to_fire = False 				# False by default
		self.enabled = eventtriger.enabled
		self.timer = eventtriger.timer 			# Timer in seconds
		self.periodic = eventtriger.periodic 	# Does the timer fires once or every 'timer' seconds?

		self.ec_session = ec_session
		self.conditions = {'node': {}, 'application': { }}
		self.conditions_met = {'node': {}, 'application': {}}

		if eventtriger.conditions == []:
			self.ready_to_fire = True
		else:
			for condition_target in eventtriger.conditions:
				target_words = condition_target.split(".")	# Ex.: 'TPLINK.iperf_server.status' or 'tplink01.status' or 'servers.status'
				target_nodes = self.ec_session.target_names(target_words[0])
				# <node/group>.<target_app>  . In the future <attribute> could be appended at the end to bind to other attributes
				# different than 'state'
				if len(target_words) == 1:		
					for node in target_nodes:
						self.ec_session.nodes[node].dependent_events.append(self)
						self.conditions["node"][node] = eventtriger.conditions[condition_target]
						self.conditions_met["node"][node] = False	# Until checked, assume conditions aren't true yet
				elif len(target_words) == 2:
					# TODO: Add support for other child resources such as interfaces
					target_app = target_words[1]	# TODO: Should check target_app is among the apps. Or leave node.app() to throw exception
					for node in target_nodes:
						self.ec_session.nodes[node].app(target_app).dependent_events.append(self)
						if node not in self.conditions["application"]:
							self.conditions["application"][node] = {}
							self.conditions_met["application"][node] = {}
						self.conditions["application"][node][target_app] = eventtriger.conditions[condition_target]
						self.conditions_met["application"][node][target_app] = False # Until checked, assume conditions aren't true yet
				else:
					logging.error("Eventtriger condition {0}:{1} has too many words".format(condition_target, eventtriger.conditions[condition_target]))

		logging.debug ("Event '{0}'\nConditions: {1}\nConditions met: {2}".format(self.event_name, self.conditions, self.conditions_met))
		self.check_conditions()		# At the end, check which of the conditions are currently fulfilled



	# type = {"node", "application"}
	# Updates the state of self.conditions and self.conditions_met
	def update_conditions(self, r_type, state, node_name, inst_name): # String/Enum r_type, String/Enum state, String node_name, String inst_name
		logging.debug("r_type: {0} state: {1} node_name: {2} inst_name: {3}".format(r_type,state,node_name,inst_name))
		if r_type == "node":
			if self.conditions[r_type][node_name] == state:
				self.conditions_met [r_type][node_name] = True
		elif r_type == "application":
			if self.conditions[r_type][node_name][inst_name] == state:
				self.conditions_met [r_type][node_name][inst_name] = True
		else: 
			pass
			# ERROR! Wrong r_type!
		self.check_conditions()

	# TODO: Maybe you can re-write this better using **kwargs
	# Whether all arguments need to be given depends on 'type'
	# Check if the new state (given arguments) equals the condition in self.conditions
	# If it does, update 'conditions_met' 
	# call 'check_conditions()'


	def check_conditions(self):
		logging.debug("Conditions: {0}\n Conditions_met: {1}".format(self.conditions, self.conditions_met))
		if all(self.conditions_met): 
			self.ready_to_fire = True
			if self.timer is None:	
				if self.ec_session.experiment_started and self.enabled:
					self.enabled = False 	# An event based only on boolean conditions must only be fired once.
					self.notify_user()		
			else:
				pass 		# Conditions are met, but wait for timer to fire.
		else:
			self.ready_to_fire = False
	

	# CHECK: these 2 timer methods could be embedded in enable and disable methods, since
	# it does not make sense to have a starttimer and stoptimer api functions 
	# (they do the same than api functions enable and disable)
	# def start_timer(self):	# Timer must always be explicitly started
	# 	self.timer_handler = threading.Timer(self.timer, self.timer_fired)
	# 	self.timer_handler.start()

	# def stop_timer(self): 
	# 	self.timer_handler.stop()
	# 	#Throw exception if timer_handler doesn't exist


	# If ready_to_fire = True, call 'notify_user()'. If ready_to_fire = False, restart timer or disable depending on periodic=True/False
	def timer_fired(self):
		if self.ready_to_fire == True:
			self.notify_user()
		else:
			if self.periodic == True:
				self.timer_handler = threading.Timer(self.timer, self.timer_fired)
				self.timer_handler.start()

	
	# # Create an EventNotification and feed it to the event queue
	# def notify_user(self):
	# 	# context = zmq.Context()
	# 	# notify_socket = context.socket(zmq.PUSH)
	# 	# notify_socket.connect("inproc://newevent")
	# 	# notify_socket.send(self.event_name)
	# 	self.ec_session.send_event_socket.send(self.event_name) # TODO!! Thread safe!
	# 	logging.debug("Event: '{0}' sent to user".format(self.event_name))

	# Create an EventNotification and feed it to the event queue
	def notify_user(self):
		# context = zmq.Context()
		notify_socket = self.ec_session.context.socket(zmq.PUSH)
		# notify_socket = context.socket(zmq.socket(zmq.PUSH)PUSH)
		notify_socket.connect("inproc://newevent")
		notify_socket.send(self.event_name)
		# self.ec_session.send_event_socket.send(self.event_name) # TODO!! Thread safe!
		logging.debug("Event: '{0}' sent to user".format(self.event_name))

	

	def enable(self):
		self.enable = True
		if self.timer is not None:
			self.timer_handler = threading.Timer(self.timer, self.timer_fired)
			self.timer_handler.start()
		check_conditions()


	def disable(self):
		self.enable = False
		try:
			self.timer_handler.stop()
		except NameError:
			print "There was no timer to Stop" 



class ECSession:

	# THREADS:
	#	-rc_events_listener
	#	-node_name_negotiator
	#	-topic_listener
	# 	-timer to check if nodes reported

	# Things EC must listen to:
	# Events : Node's periodic reports, Application's state changes
	# Negotiation: Request from ResourceController to get a node_name. Listen constantly to 'negotiate'
	# Response to requests and (maybe) successful creation: Decide what you want to be ACK'ed

	def __init__(self, publisher, host='*', port=9000, events_port=1919):
		self.events = {}					# Where all events are stored and can be addressed by name. <String event_name, Event event>
		self.groups = {}					# Same for groups. <String group_name, Group group>
		self.nodes = {}						# Same for all existing nodes. <String node_name, Node node>
		self.apps = {}						# <String application_name, Thrift application structures>

		self.experiment_started = False		# Is the preparation phase finished? In the beginning of the program must be False
		self.node_report_time = 60			# How often to check that nodes have reported their state
		self.report_time_margin = 1			# How much margin time it leaves them 

		self.publisher = publisher 			# The publisher provides the capability to send messages
		self.topics	= []					# Topics the EC will be listening to

		# Set periodic timer to check nodes reported their state
		self.check_nodes_timer = threading.Timer (self.node_report_time, self.check_nodes_reported)
		self.check_nodes_timer.daemon = True
		self.check_nodes_timer.start()

		self.host = host
		self.topics_port = port
		self.events_port = events_port

		self.context = zmq.Context()

		# Create PAIR socket to update topic_listener's subscription
		self.pair_socket = self.context.socket(zmq.PAIR)
  		self.pair_socket.bind("inproc://addtopic")

		# # Socket to send events to user: # MOVED TO "event_notifier"
		# self.send_event_socket = self.context.socket(zmq.PUSH)
		# self.send_event_socket.bind("tcp://%s:%s" %(self.host, events_port))	


		# Start topic_listener as a daemon thread
		topic_listener_thread = threading.Thread(target=self.topic_listener)
		topic_listener_thread.daemon = True
		topic_listener_thread.start()

		# Start a thread to listen to even notifications from EC:Events and to push events to the user.
		topic_listener_thread = threading.Thread(target=self.event_notifier)
		topic_listener_thread.daemon = True
		topic_listener_thread.start()		

		# Add default topics:
		self.addtopic('events')
		self.addtopic('negotiate')


		# # Start rc_events_listener as a daemon thread
		# rc_events_listener_thread = threading.Thread(target=self.rc_events_listener)
		# rc_events_listener_thread.daemon = True
		# rc_events_listener_thread.start()
		# # Start node_name_negotiator as a daemonthread
		# name_negotiator_thread = threading.Thread(target=self.node_name_negotiator)
		# name_negotiator_thread.daemon = True
		# name_negotiator_thread.start()




	# Check all nodes's last_report property to see if they have reported. If not: mark them as irresponsive
	def check_nodes_reported(self):	# FORMERNAME: is_node_reporting
		# global nodes
		for node in self.nodes.itervalues():	# We iterate over the Node objects
			# logging.info("Time since last report: {0}".format(time.time()-node.last_report)+" Report time + Margin:{0}".format(self.node_report_time+self.report_time_margin))
			if time.time()-node.last_report < self.node_report_time+self.report_time_margin:
				# OK
				self.update_node("Ready", node.name, refresh_timestamp=False)
			else:
				self.update_node("Irresponsive", node.name, refresh_timestamp=False) 
	#	 	else
	#	 		Poll node. 
	#	 		if node responds
	#				OK # ADDITIONAL_FEATURE: Count how many times you needed to poll the node. If it keeps happening, notify/warn
	#	 		if irresponsive
	#				update_node(node.node_name, "Irresponsive")		
	# 	Could add a feature to remove a Node from the list after some time being irresponsive			
		# Restart timer so this happens periodically
		self.check_nodes_timer = threading.Timer (self.node_report_time, self.check_nodes_reported)
		self.check_nodes_timer.start()




	def node_name_negotiator (self, topic, bodymsg):
		response_topic = topic 				# CHECK: Do some checking here?
		prefered_name = bodymsg.field
		# logging.debug("Response topic:%s", response_topic)
		# logging.info("Prefered name:%s", prefered_name)
		# **1 TODO!!: Right now, if several resourcecontrollers request the same name before one of them can register the node,
		# both will be granted the same name, and the second one to register will fail to do so because there will
		# be already another node with the same name. 
		if prefered_name!= "" and prefered_name not in self.nodes: # **1
			assigned_name = prefered_name
		else: 								# Make up a different name. Ideal would be to base it on node hostname within the network
			assigned_name = "ForcedName"	# MOCKUP
		self.addtopic (assigned_name)	
		# logging.info("Assigned name:%s", assigned_name)
		self.publisher.assign_name(response_topic, assigned_name)		#topic, assigned_name		



	def update_distributor(self, topic, msg_header, bodymsg):
		# logging.debug("Entered function") # DEBUGGING
		topic_words = topic.split('.')	# Split a topic name like this: 'events.application.<parent_name>.<inst_name>'
										# or 'events.node.<node_name>' into a word list.
		resource_type = topic_words[1]
		state = bodymsg.field
		node_name = topic_words[2]
		logging.info("Update message: Resource type: {0} State: {1} Node name: {2}".format(resource_type,state,node_name))
		if resource_type == "node":
			self.update_node(state, node_name)
		elif resource_type == "application":
			inst_name = topic_words[3]
			# logging.info("inst_name = topic_words[3]: {0}".format(topic_words[3]) )
			self.update_application(state, node_name, inst_name)
		else: 
			print "update_distributor() failed to parse a message"


	def update_node(self, state, node_name, refresh_timestamp=True):			## TO CLASS?
		node = self.nodes[node_name]
		if refresh_timestamp:		#  If the EC is updating the state, 'last_report' must not be refreshed
			node.last_report = time.time()
		# logging.info("Updating node%s", state)	# DEBUGGING
		if node.state != state:
			node.state = state
			map (lambda x: x.update_conditions("node", state, node_name) , node.dependent_events)  


	def update_application (self, state, node_name, inst_name): 	## TO CLASS? No. This one needs to access the nodes!
	#  To move to class, make update_distributor look for the app inside the nodes and do
	# x.update(state) == update_application(state,node_name,inst_name)
	# Problem is update_conditions needs to know to which node the app belongs
	# Solution?: Make each apptracker know to which node belongs? NOOO. 
	# Same apptracker (from the same 'add_application') are shared by several nodes.
	# Solution: make update_distributtor call <one_app>.update(state, node_name) so it has all data to call update_conditions
		apptracker = self.nodes[node_name].app(inst_name)
		if apptracker.state != state: 		# Remember app() returns the node AppTracker object with name inst_name
			apptracker.state = state
			map (lambda x: x.update_conditions("application", state, node_name, inst_name) , apptracker.dependent_events) 

	def register_node (self, nodeinfo): # nodeinfo is instance of NodeInfo
		if nodeinfo.node_name not in self.nodes:
			self.nodes[nodeinfo.node_name]= Node(nodeinfo)
			logging.info("Node registered \nName: {0}\nOS: {1}\nApplications: {2}\nNetwork Interfaces:{3}\n{4}".format(
			nodeinfo.node_name, nodeinfo.os, nodeinfo.apps, nodeinfo.ifaces, 20*'-')) 	# DEBUGGING
		else:
			print "Node registration failed: Node name already exists!" # CHECK: /"...: Node is already"
			#TODO: Proper error/exception handling


	## Auxiliar functions ## 

	def addApptoNode (self, node_name, inst_name, appinstance):  ## TO CLASS?	
			# Must assure inst_name is not already present in any of the nodes members of the group. 
		# logging.debug("Node name: %s Inst name: %s AppInstance object: %s", node_name, inst_name, appinstance)
		if inst_name not in self.nodes[node_name].child_resources["applications"]:
			self.nodes[node_name].child_resources["applications"][inst_name]= AppTracker(appinstance)
		else: 
			logging.error ("inst_name already exists in node {0}".format (node_name) )
			#TODO: Proper error/exception handling. THIS ERROR SHOULD BE FUNNELED BACK TO THE USER!!

	def target_names (self, target):
		target_nodes = []
		if target in self.nodes:
			target_nodes.append(target)
		elif target in self.groups:
			target_nodes = self.groups[target].members.keys()
		else: 
			logging.error ("Specified node or group doesn't exist")
			return
		return target_nodes

	def target_instances (self, target):
		target_nodes = []
		if target in self.nodes:
			target_nodes.append(self.nodes[target])
		elif target in self.groups:
			target_nodes = self.groups[target].members.values()
		else: 
			logging.error ("Specified node or group doesn't exist")	
			return	
		return target_nodes	

	## ------------ ##


	## Listening methods ##

	def addtopic(self, topic):	 # Or maybe call it add_topic_to_listen better?
		self.pair_socket.send(topic)		

	def message_handler(self, topic, msg_header, bodymsg):
		topic_prefix = topic.split(".",1)[0]
		# logging.debug("Topic:%s", topic)
		# logging.debug("Topic prefix:%s", topic_prefix)
		if topic_prefix == 'events':
			self.update_distributor(topic, msg_header, bodymsg) # CHECK: So far, msg_header is not needed, remove it if finally not used.
		elif topic_prefix == 'negotiate':
			self.node_name_negotiator(topic, bodymsg)
		else:
		# MOCKUP: Right now I only care about handling node registrations:
			if bodymsg.itype == thrift.InformType.REGISTER:
				self.register_node(bodymsg.nodeinfo)

		# Classifies messages and acts calling other functions according to its content

		# To classify:
		# 	- Node registration  --> register_node(NodeInfo nodeinfo)
		# 	- Creation_ok			## Await for ok? or just log it?
		# 	- Creation_failed 		## Errors should be notified to user? Or just logged?
		# 	- Released				## Log it
		#  	- Error/Warning			## Errors should be notified to user? Or just logged?



	def add_pending_response(self, mid, timelimit, functiontocall): 		## NECESSARY???
		pending_response.append(mid)
		# Start timer with 'timelimit' which will call 'functiontocall'

	def delete_pending_response (self, mid):								## NECESSARY???
		pass
		# Stop pending_response[mid] timer
		# Delete pending_response[mid]


	## LISTENING THREAD ##


	def event_notifier (self):
		# Socket to receive new events from Events instances
		get_event = self.context.socket(zmq.PULL)
		get_event.bind("inproc://newevent")
		# Socket to send events to user:
		self.send_event_socket = self.context.socket(zmq.PUSH)
		self.send_event_socket.bind("tcp://%s:%s" %(self.host, self.events_port))	

		while True:
			event = get_event.recv()
			self.send_event_socket.send(event)




	def topic_listener (self):
		# Create socket to receive topic subscriptions commands
		get_socket = self.context.socket(zmq.PAIR)
		get_socket.connect("inproc://addtopic")
		# Create socket to listen to topics of its interest
		topics_socket = self.context.socket(zmq.SUB)
		topics_socket.bind("tcp://%s:%s" %(self.host, self.topics_port))

		# poller.poll() will return when any of the registered sockets got a message
		poller = zmq.Poller()
		poller.register(get_socket, zmq.POLLIN)
		poller.register(topics_socket, zmq.POLLIN)		

		while True:		
			# logging.info("Ready to listen")	
			socks = dict(poller.poll())		# Waiting for a message on ANY of the registered sockets
			if get_socket in socks and socks[get_socket] == zmq.POLLIN:
				topic = get_socket.recv()
				topics_socket.setsockopt(zmq.SUBSCRIBE, topic)
				# logging.info("topic_listener subscribed to {0}".format(topic))
				self.topics.append(topic)					# Keep track of the topics we are listening to.
				logging.info("EC is now subscribed to {0}".format(self.topics))				# DEBUGGING
			if topics_socket in socks and socks[topics_socket] == zmq.POLLIN:
				msg = topics_socket.recv_multipart()
				# logging.info("topic_listener got a message")
				if False: # MOCKUP: Some proper checking on msg here. Like that it is a InformMsg and so on..
					# BAD!
					print "Something wrong happened at 'topic_listener'"
				else:
					# TODO: Proper message checking
					topic = msg[0]
					msg_header = TSerialization.deserialize(thrift.MsgHeader(), msg[1])
					bodymsg = TSerialization.deserialize(thrift.InformMsg(), msg[2])	# CHECK: We assume we get an inform message. What else could it be?
					# CHECK AGAIN: What arguments do you really want to pass to 'message_handler' ?
					message_handler_thread = threading.Thread(target=self.message_handler, args=[topic, msg_header, bodymsg])
					message_handler_thread.daemon = True
					message_handler_thread.start()		## MOCKUP Temporary!
					# logging.debug("Got a message from topic {0}. Message type: {1} Bodymsg {2}".format(topic,msg_header,bodymsg))


		# Check if InformMessage.cid is in 'awaiting_response' and delete it
		# Spawn message_handler as a daemon thread.

	## --------------- ##

