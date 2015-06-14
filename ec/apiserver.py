#!/usr/bin/env python

from ecsession import Group
from ecsession import Event
import  Structures.ttypes as thrift
from thrift import TSerialization
import logging
import zmq


class APIServer:
	
	# THREADS: So far, none

	def __init__(self, ec_session, publisher, host='*', api_port=1818, events_port=1919):
	
		self.ec = ec_session
		self.publisher = publisher

		context = zmq.Context()
		# self.socket = context.socket(zmq.REP)
		self.socket = context.socket(zmq.ROUTER)
		self.socket.bind("tcp://%s:%s" %(host, api_port))

		# get_event_socket = context.socket(zmq.PULL)
		# get_event_socket.bind("inproc://newevent")


		# serialized_data_f = ('def_application', 'add_application', 'def_event', 'updateIf')
		self.serialized_data_f = { 'def_application' : [thrift.App], 'add_application': [None, thrift.AppInstance],
					'def_event': [thrift.EventTrigger], 'updateIf': [thrift.Iface] }

		while True:
			command = self.socket.recv_multipart()
			# logging.debug ("Message as it its: {0}".format(command))
			i = 1 			# 0 if socket == zmq.REP, 1 if socket == zmq.ROUTER CHECK
			function_to_call = command[i] 
			#TSerialization.deserialize(thrift.MsgHeader(), msg[1])
			args = command[i+1:]
			if function_to_call in self.serialized_data_f:
				args = self.__deserialize(function_to_call, args)

			logging.debug("Calling function '{0}()' with args {1}".format(function_to_call, args))
			return_value = getattr(self, function_to_call)(*args)   # Use here a try-catch structure to send errors back to user?
			# logging.debug("End of while loop")



		# poller = zmq.Poller()
		# poller.register(get_event_socket, zmq.POLLIN)
		# poller.register(self.socket, zmq.POLLIN)

		# while True: #CHECK if you want to do this this way or rather using threads
		# 	socks = dict(poller.poll())		# Waiting for a message on ANY of the registered sockets
		# 	if self.socket in socks and socks[self.socket] == zmq.POLLIN:
		# 		command = self.socket.recv_multipart()
		# 		logging.debug ("Message as it is: {0}".format(command))
		# 		i = 1 			# 0 if socket == zmq.REP, 1 if socket == zmq.ROUTER CHECK
		# 		function_to_call = command[i] 
		# 		#TSerialization.deserialize(thrift.MsgHeader(), msg[1])
		# 		args = command[i+1:]
		# 		if function_to_call in self.serialized_data_f:
		# 			args = self.__deserialize(function_to_call, args)

		# 		logging.debug("Calling function '{0}()' with args {1}".format(function_to_call, args))
		# 		return_value = getattr(self, function_to_call)(*args)   # Use here a try-catch structure to send errors back to user?
		# 		# self.socket.send("MOCKUP")	# MOCKUP
		# 	elif get_event_socket in socks and socks[get_event_socket] == zmq.POLLIN:
		# 		event_name = get_event_socket.recv()
		# 		send_event_socket.send (event_name)
		# 		logging.debug("Event: '{0}' received and passed to user".format(event_name))
		# 	logging.debug("End of while loop")





	
	def __deserialize (self, func_name, args):
		for i,vessel in enumerate(self.serialized_data_f[func_name]):
			# logging.debug ("i: {0} vessel: {1}".format(i,vessel))
			if vessel is not None:
				args[i] = TSerialization.deserialize(vessel(), args[i])
		return args


	def get_resources(self):
		resources = []
		for node in self.ec.nodes.itervalues():
			nodeinfo = thrift.NodeInfo()
			nodeinfo.node_name = node.name
			nodeinfo.os = node.os
			logging.info("child_resources", "Applications:%s",node.child_resources["applications"])
			for app in node.child_resources["applications"].itervalues():
				appinfo = thrift.AppInfo()
				#appinfo.app_name =  		# DECISION: Include this? If you do, you must include app_name in AppTracker:
											# Either implicitly by saving AppInstance or by including it as a separated attribute
				appinfo.inst_name = app.inst_name
				appinfo.state = app.state
				logging.debug ("Adding thrift.AppInfo to nodeinfo: {0} to ".format(appinfo))
				nodeinfo.apps = []
				nodeinfo.apps.append(appinfo)
				logging.debug ("Nodeinfo apps: {0} to ".format(nodeinfo.apps))
			# for iface in node.child_resources["ifaces"].itervalues():
			# 	iface = thrift.Iface()
			# 	iface.if_name = 
			# 	iface.phy = 
			# 	iface.mode = 
			# 	iface.channel = 
			# 	iface.mac_address = 
			resources.append(nodeinfo)
		return resources 	# 







	def def_application (self, app):
		logging.debug("struct App added:\nap_name = {0}\nbinary_path = {1}\npkg_opkg = {2}\npkg_tarball = {3}\ntarball_installdir = {4}\
			\nforce_tarball_install = {5}\ndescription = {6}\n{7}".format(app.ap_name, \
				app.binary_path, app.pkg_opkg, app.pkg_tarball, app.tarball_installdir, app.force_tarball_install,
				app.description, 20*'-'))
		self.ec.apps[app.ap_name] = app # Save the 'application' structure in a map<String app_name, Application app>
		# TODO: Validate app structure. See comments below:
		# At least one of the following combinations must be provided:
		# [binary_path] (if the user expects the app to be already installed), [binary_path, pkg_tarball] (if tarball_installdir is given 
		# , it must be a prefix of binary_path, if not Makefile should be provided inside the tarball)
		# [pkg_opkg]
		# Otherwise throw exception
		

	def def_group(self, group_name, *members): # members is a variable number of strings with the node names
											   # String group_name, String member1, String member2, ...
		#TODO: Argument validation:
		# Check members is a list
		members_list = members
		logging.debug("Adding group {0} with members {1}".format(group_name, members_list))
		group = Group (group_name, members_list, self.ec)	# Should validation be done here or in Group constructor?
		self.ec.groups[group_name] = group		
		# Instruct all members to subscribe to the group's topic
		for member in members_list:
			self.publisher.config_subscription(topic=member, subscribe_to=group_name) # Remember that the * is added by the 'Publisher'
		


	def add_application (self, container_name, appinstance): # String container_name, Appinstance appinstance
		# TODO: 
		# Check arguments in appinstance comply with the parameter requirements in the corresponding application structure 
		# If not, return error
		inst_name = appinstance.inst_name
		app = self.ec.apps[appinstance.app_name]	
		targets = self.ec.target_names(container_name)	# Returns a list with the names of nodes addressed
		for target in targets:
			self.ec.addApptoNode(target, inst_name, appinstance)
			logging.debug("Appinstance for App '{0}'\ninst_name = {1}\nclean_env = {2}\nmapp_err_to_out = {3}\
				\narguments = {4}\nenvironment = {5}\n{6}".format(appinstance.app_name, appinstance.inst_name, \
					appinstance.clean_env, appinstance.map_err_to_out, appinstance.arguments, appinstance.environment, 20*'-'))
		# Send create message either to a <node_topic> or <group_topic>  (so all member nodes create it anyway)	
		self.publisher.create(container_name, "application", app, appinstance)

		# if container_name in self.ec.nodes:	# Is the target a Node?
		# 	self.ec.addApptoNode(container_name, inst_name, appinstance)
		# 	self.publisher.create (container_name, "application", app, appinstance)
		# elif container_name in self.ec.groups: # Is the target a group?
		# 	for node_key in self.ec.groups[container_name].members: # This iterator contains node_name keys of a dictionary
		# 		self.ec.addApptoNode(node_key, inst_name, appinstance)	# It creates a different AppTracker for each member node
		# 		# Still use container_name==group_name, since the order is going to be sent to the group topic
		# 		self.publisher.create (container_name, "application", app, appinstance)

		# DECISION: Create a new RC_application structure here to eliminate redundant information
		# or just forward both structures?
		# MUST DO SOME CHECKING ON THE PARAMTERS!! Have 2 of them the same order or name? That kind of stuff
	# Note that in the RC, when creation is addressed to a group, the child resource must
	# subscribe to <group_topic>.<own_topic> ; <group_topic>.<childresource_type> ; <parent_topic>.<own_topic>
	#  & <parent_topic>.<childresource_type> . When creation is addressed to a single node. Only the last two ones.


	def def_event (self, eventtrigger): # EventTrigger eventtrigger
		# TODO: Checking on eventtriger before passing it
		self.ec.events [eventtrigger.name] = Event(eventtrigger, self.ec)
	# Translate EventTrigger into a newly created EC:Event and add to a Dictionary<String Event_name,Event event>
	# 
	# Will throw exception (generated in EC:Event when any of the targets for the condition is undefined (e.g. app not yet defined))

	def start_experiment (self):
		self.ec.experiment_started = True # Set experiment_started = True


	## Auxiliar functions ##


	## ---------- ------  ##


	## FUNCTIONS THAT MUST BE CALLABLE IN BOTH PHASES ##

	# Update Iface (Thrift structure) attribute of all Node objects belonging to 'group' (or just node's Iface)
	# Send message to group topic to create 
	def updateIf (self, target_name, iface): # String group_name/node_name, Iface iface
		logging.info("Updating interface {0} for nodes: {1}".format(iface.if_name, self.ec.target_names(target_name)))
		for node in self.ec.target_instances(target_name):  # Returns a list with the object instances of the nodes addressed
			node.child_resources["ifaces"][iface.if_name] = iface
		# Send create message either to a <node_topic> or <group_topic>  (so all member nodes create it anyway)	
		self.publisher.create(target_name, "iface", iface)	



	## FUNCTIONS TO STEER THE EXPERIMENT ##

	def change_parameter (self, target_name, inst_name, parameter, new_argument):
		topic = target_name+'.'+inst_name 		#CHECK: This means that if you defined the application within group1=[A,B,C,D]
		# and now you want to start that app refering to group2=[A,B] it will send it to group2.inst_name, which does not exist
		self.publisher.change_parameter(topic, parameter, new_argument)


	def startAllApps (self, target_name): # String group_name/node_name
		if not self.ec.experiment_started:
			logging.error ("The experiment has not been started")
		else:
			# < Make sure that ALL application(s) is/are installed >
			for node in self.ec.target_instances(target_name):
				for app in node.child_resources['applications'].values():
					if app.state.lower() not in ("installed", "running" "stopped", "finished", "paused"):
						logging.error ("One or more of the applications is not installed yet")
						return
			#  < / >			
			topic = target_name+'.application'
			self.publisher.set_state(topic , "Running")

	# Check that all applications are installed and then:
	# 	Send config (group_name.apps/node_name.apps , startinstruction )
	# If any of them can't run yet, return error.

	def stopAllApps (self, target_name): # String group_name/node_name
		if not self.ec.experiment_started:
			logging.error ("The experiment has not been started")
		else:
			# < Make sure that ALL application(s) is/are installed >
			for node in self.ec.target_instances(target_name):
				for app in node.child_resources['applications']:
					if app.state.lower() not in ("installed", "running" "stopped", "finished", "paused"):
						logging.error ("One or more of the applications is not installed yet")
						return
			#  < / >			
			topic = target_name+'.application'
			self.publisher.set_state(topic , "Stopped")


	def pauseAllApps (self, target_name): # String group_name/node_name
		if not self.ec.experiment_started:
			logging.error ("The experiment has not been started")
		else:
			# < Make sure that ALL application(s) is/are installed >
			for node in self.ec.target_instances(target_name):
				for app in node.child_resources['applications']:
					if app.state.lower() not in ("installed", "running" "stopped", "finished", "paused"):
						logging.error ("One or more of the applications is not installed yet")
						return
			#  < / >			
			topic = target_name+'.application'
			self.publisher.set_state(topic , "Paused")	

	# 
	# Send config (group_name.apps/node_name.apps , stopinstruction )

	def startApp (self, target_name, inst_name): # String group_name/node_name , String inst_name
		if not self.ec.experiment_started:
			logging.error ("The experiment has not been started")
		else:
			# < Make sure that target application(s) is/are installed >
			for node in self.ec.target_instances(target_name):
				if node.app(inst_name).state.lower() not in ("installed", "running", "stopped", "finished", "paused"):
					logging.error ("One or more of the applications is not installed yet")
					return
			#  < / >
			topic = target_name+'.'+inst_name
			self.publisher.set_state(topic , "Running")



	# Check that application is installed and then:
	# 	Send config (group_name.inst_name/node_name.inst_name , startinstruction )
	# 

	def stopApp (self, target_name, inst_name): # String group_name/node_name, String inst_name
		if not self.ec.experiment_started:
			logging.error ("The experiment has not been started")
		else:
			# < Make sure that target application(s) is/are installed >
			for node in self.ec.target_instances(target_name):
				if node.app(inst_name).state.lower() not in ("installed", "running", "stopped", "finished", "paused"):
					logging.error ("One or more of the applications is not installed yet")
					return
			#  < / >
			topic = target_name+'.'+inst_name
			self.publisher.set_state(topic , "Stopped")


	def pauseApp (self, target_name, inst_name): # String group_name/node_name, String inst_name
		if not self.ec.experiment_started:
			logging.error ("The experiment has not been started")
		else:
			# < Make sure that target application(s) is/are installed >
			for node in self.ec.target_instances(target_name):
				if node.app(inst_name).state.lower() not in ("installed", "running", "stopped", "finished", "paused"):
					logging.error ("One or more of the applications is not installed yet")
					return
			#  < / >
			topic = target_name+'.'+inst_name
			self.publisher.set_state(topic , "Paused")


	def timerOn (name): # String name
		pass
	# if experiment_started:
	# 	events[name].start_timer()	
	# else:
	# 	throw exception ("Can't start timer until experiment has started")

	def timerOff (name): # String name
		pass
	# events[name].stop_timer()		
	# throws exception if there was no previously started timer

	def enableEvent (name): # String name
		pass
	# events[name].enable()

	def disableEvent (name): # String name
		pass
	# events[name].disable()

	def terminateExperiment():
		pass
	# Send release messages to all nodes with child resources for each child resource
	# Give link to OML database file


