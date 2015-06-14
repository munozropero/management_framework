#!/usr/bin/env python

import sys
sys.path.append('../thrift_struct/gen-py')

import time
import logging
logging.basicConfig(level=logging.DEBUG, format= '%(levelname)s %(module)s %(funcName)s(): %(message)s')

import  Structures.ttypes as thrift 	# Import automatically-generated Thrift structures for Python
from thrift import TSerialization		# Import Thrift serialization module
import zmq
import threading


# Address where the EC is bound to wait for API calls and send Events
host = "192.168.1.36"
port = 1818
events_port = 1919			# EC's socket to PUSH events
context = zmq.Context()		# Create a context to spawn ZMQ sockets

event_buffer = []		# All events received are buffered here
new_event = threading.Event()	# Thread-safe flag to notify new_events

# This function will be invoked from a thread.
# It creates a socket connected to EC's event notifier.
# Then it enters an infinite loop waiting for event messages.
# When a message event arrives, the function associated with it is invoked
# The function will execute a series of orders.
# It also forwards buffers the events received so other functions can use them
# This mechanism is useful if we want to react immediatly to an event.
# Go to the end of the script for an example.
def react_to_event():
	# Socket to receive events from EC
	event_socket = context.socket(zmq.PULL)
	event_socket.connect("tcp://%s:%s" %(host, events_port))
	# We want another function to know too what events are being received.
	# It uses the global variables to store and notify new events.
	global event_buffer
	global new_event
	while True:	
		event_name = event_socket.recv()	# recv() blocks until it gets a message
		event_buffer.append(event_name)		# Add the event received to the buffer
		new_event.set()			# Set the flag to True. This will wake any thread waiting on it
		try:	# If there is a function in the ED with the same name as the event
				# this snippet calls such function (in a different Thread).
			function_to_call = globals()[event_name]
			call_function_t = threading.Thread(target=function_to_call)
			call_function_t.daemon = True
			call_function_t.start()
		except KeyError:
			logging.info("No action scheduled for received event '{0}'".format(event_name))
		



# The purpose of this functon is pause execution until a specific event occurs
def waitforEvent(event_name):
	# Use the global variables shared between threads
	global event_buffer
	global new_event
	while True: # It receives all incoming events and checks if it is the one we are awaiting.
		new_event.wait()	# It blocks until "react_to_event" notifies a new event.
		received_event = event_buffer.pop(0)	# Remove the event from the list once it is read.
		if not event_buffer: 	# If the list is empty, there are no more new events
			new_event.clear() 	# Hence, we set the flag to "False" to block in the next iteration.
		if event_name == received_event:
			logging.debug("Event '{0}'. Now ED can continue".format(event_name))
			return	# If event_name even is received, the function returns.


# Since we want to want to react immediately to events, there are going to be different threads
# sending API calls (messages through ZMQ) to EC. ZMQ sockets are not thread-safe.
# Hence, there are 2 options: Create a new socket in each thread or call a thread-safe function
# that forwards the message to another socket permanently connected to APIServer. Send is such thread-safe function.
# It creates a new socket every time it is called anyway, but it avoids creating it implicitly
# and makes the syntax clearer.
def send(*args):
	# 
	pipe_socket = context.socket(zmq.PUSH)
	pipe_socket.connect("inproc://api")
	# message = ["",]	# Use if the API is using a REP socket
	message = [] 		# Use if the API is using a ROUTER socket
	message.extend(args)
	pipe_socket.send_multipart(message)	


# This is invoked from a thread. It gets messages from sockets in different threads and 
# forwards it to APIServer.
def api():
	# Socket to listen for messages to forward
	pipe_socket = context.socket(zmq.PULL)
	pipe_socket.bind("inproc://api")	
	# Socket to send the API calls to.
	api_socket = context.socket(zmq.DEALER)
	api_socket.connect("tcp://%s:%s" %(host, port))
	while True:
		msg = pipe_socket.recv_multipart()	# Blocking call
		logging.debug("Message: {0}".format(msg))
		api_socket.send_multipart(msg)	# Send message to APIServer in the EC
		


# Start a thread listening for events
event_notifier_t = threading.Thread(target=react_to_event)
event_notifier_t.daemon = True
event_notifier_t.start()
# Start a thread that will forward API calls to the EC
api_t = threading.Thread(target=api)
api_t.daemon = True
api_t.start()

# ----- HERE STARTS EXPERIMENT DESCRIPTION ---- #	


# Create an application frame
scp = thrift.App(ap_name="scp", binary_path="/usr/bin/scp", description="SSH Copy")
scp.parameters =  ([thrift.Parameter(name="origin", cmd='', type= "String"), 
	thrift.Parameter(name="destination", cmd='', type= "String")] )
# cmd is what should preceed the argument value when starting the application
# For example, if you want to specify an option to connect to a specific port, 
# you usually write "iperf -P 3000 host_to_connect_to". Here the "port" parameter
# would have cmd="-P" and the argument passed would be "3000"

# Serialize the application frame and send it to the EC.
send('def_application', TSerialization.serialize(scp))
# 'tplink01', 'tplink02' and 'tplink03' will be now be members of the 'copiers' group
send('def_group', "copiers", 'tplink01', 'tplink02', 'tplink03')


# Create an Application instance. That is, give arguments to the parameters in
# the previously-created application frame.
scp_instance = thrift.AppInstance() # Create an empty Thrift structure
# Set the attributes
scp_instance.inst_name = "scp_tplink02" # This will be part of the resource's UID
scp_instance.app_name = "scp"	# Name of the app frame to which we are passing arguments.
scp_instance.arguments = {"origin": "/root/foo", "destination": "tplink02:/root/"}

scp_instance2 = thrift.AppInstance()
scp_instance2.inst_name = "scp_tplink03"
scp_instance2.app_name = "scp"
scp_instance2.arguments = {"origin": "/root/foo", "destination": "tplink03:/root/"}

# Now associate them with a node.
# scp_instance1 and scp_instance2 are instances of the same "scp" application frame
send('add_application', 'tplink01', TSerialization.serialize(scp_instance1))
send('add_application', 'tplink01', TSerialization.serialize(scp_instance2))
# Now applications are being deployed on the 'tplink01' node.
# They will be installed/downloaded now, if necessary. After that, they will be ready to start.


# Once an AppInstance is sent, we can change some of its attributes and reuse it for another node.
# It won't affect the instance created in 'tplink01'.
scp_instance2.inst_name = "scp_inst"
scp_instance2.arguments = {"origin": "/root/foo", "destination": "tplink04:/root/"}

# Associate and deploy the AppInstance on the 'copiers' group.
send('add_application', "copiers", TSerialization.serialize(scp_instance2))


# Create an EventTrigger structure that will be sent to define an event.
all_apps_installed = thrift.EventTrigger(name="allAppsInstalled" ,enabled=True)
# To stablish a condition, the key must be the UID of the resource and the value, the state of the resource
# that should trigger the event.
all_apps_installed.conditions = {'tplink01.scp_tplink02': 'Installed', 'tplink01.scp_tplink03': 'Installed' \
							'tplink02.scp_inst': 'Installed', 'tplink03.scp_inst': 'Installed'}

first_transfer_event = thrift.EventTrigger(name="firstTransferFinished" ,enabled=True)
first_transfer_event.conditions = {'tplink01.scp_tplink02': 'Finished'}

second_transfer_event = thrift.EventTrigger(name="secondTransferFinished" ,enabled=True)
second_transfer_event.conditions = {'tplink01.scp_tplink03': 'Finished'}

all_apps_finished = thrift.EventTrigger(name="allAppsFinished" ,enabled=True)
all_apps_finished.conditions = {'tplink01.scp_tplink02': 'Finished', 'tplink01.scp_tplink03': 'Finished' \
							'tplink02.scp_inst': 'Finished', 'tplink03.scp_inst': 'Finished'}							


send('def_event',TSerialization.serialize(all_apps_installed))
send('def_event',TSerialization.serialize(first_transfer_event))
send('def_event',TSerialization.serialize(second_transfer_event))
send('def_event',TSerialization.serialize(all_apps_finished))
# From now on, the events are defined 

# Block until the 'allAppsInstalled' event occurs.
# This way we make sure we don't try to start applications which are not ready.
waitforEvent ('allAppsInstalled')

# Remember that we associated the same AppInstance with both members of 'copiers' (tplink02 and tplink03)?
# We actually want tplink02 and tplink03 to copy the object to different nodes (tplink04 and tplink05)
send('change_parameter','tplink03', "scp_inst", "destination", 'tplink05:/root/')

send ('startAllApps', 'tplink01')

waitforEvent ('allAppsFinished')

# When we are finished doing or work, finish the experiment
send ('terminate_experiment')


# This function will be called when the 'firstTransferFinished' event occurs
def firstTransferFinished ():
	# firstTransferFinished is triggered when 'tplink01' finishes transfering the file to 'tplink02
	# We want 'tplink02' to subsequently copy such file to 'tplink04'
	send ('startApp',"tplink02", "scp_inst")


def secondTransferFinished ():
	# secondTransferFinished is triggered when 'tplink01' finishes transfering the file to 'tplink03
	# We want 'tplink03' to subsequently copy such file to 'tplink05'
	send ('startApp',"tplink03", "scp_inst")



