#!/usr/bin/env python

import sys
sys.path.append('../thrift_struct/gen-py')

import time
import logging
logging.basicConfig(level=logging.DEBUG, format= '%(levelname)s %(module)s %(funcName)s(): %(message)s')

import  Structures.ttypes as thrift
from thrift import TSerialization
import zmq
import threading



host = "192.168.1.35"
port = 1818
events_port = 1919
context = zmq.Context()

event_buffer = []	
new_event = threading.Event()
new_event.daemon = True


def event_functions_actuator():
	event_socket = context.socket(zmq.PULL)
	event_socket.connect("tcp://%s:%s" %(host, events_port))
	# forward_event_socket = context.socket(zmq.PAIR)
	# forward_event_socket.bind("inproc://forward")
	global event_buffer
	global new_event
	while True:	
		event_name = event_socket.recv()
		# forward_event_socket.send(event_name)
		event_buffer.append(event_name)
		new_event.set()
		try:
			function_to_call = globals()[event_name]
			call_function_t = threading.Thread(target=function_to_call)
			call_function_t.daemon = True
			call_function_t.start()
		except KeyError:
			logging.info("No action scheduled for received event '{0}'".format(event_name))
		



# The purpose of this funciton is pause execution until event occurs
def waitforEvent(event_name):
	global event_buffer
	global new_event
	while True:
		new_event.wait()
		received_event = event_buffer.pop(0)
		if not event_buffer: 
			new_event.clear() 	# If the list is empty, the next iteration of the loop will have to wait.
		if event_name == received_event:
			logging.debug("Event '{0}'. Now ED can continue".format(event_name))
			return


# # The purpose of this funciton is pause execution until event occurs
# def waitforEvent(event_name):
# 	wait_socket = context.socket(zmq.PAIR)
# 	wait_socket.connect("inproc://forward")
# 	while True:
# 		if event_name == wait_socket.recv():
# 			logging.debug("Event '{0}'. Now ED can continue".format(event_name))
# 			return


def send(*args):
	pipe_socket = context.socket(zmq.PUSH)
	pipe_socket.connect("inproc://api")
	# message = ["",]	# Use if the API is using a REP socket
	message = [] 		# Use if the API is using a ROUTER socket
	message.extend(args)
	pipe_socket.send_multipart(message)	

def api():
	pipe_socket = context.socket(zmq.PULL)
	pipe_socket.bind("inproc://api")	
	api_socket = context.socket(zmq.DEALER)
	api_socket.connect("tcp://%s:%s" %(host, port))
	while True:
		msg = pipe_socket.recv_multipart()
		logging.debug("Message: {0}".format(msg))
		api_socket.send_multipart(msg)
		



event_notifier_t = threading.Thread(target=event_functions_actuator)
event_notifier_t.daemon = True
event_notifier_t.start()
api_t = threading.Thread(target=api)
api_t.daemon = True
api_t.start()

# ----- HERE STARTS EXPERIMENT DESCRIPTION ---- #	

def main():

	myapp = thrift.App(ap_name="iperf", binary_path="/usr/bin/iperf", description="Hello World Application")
	myapp.parameters =  ([thrift.Parameter(name="server", cmd='-s', type= "Flag", default_value="False"), 
		thrift.Parameter(name="client", cmd='-c', type= "String")] )


	send('def_application', TSerialization.serialize(myapp))
	send('def_group', "Servers", "kali")


	app_inst = thrift.AppInstance()
	app_inst.inst_name = "iperf_client"
	app_inst.app_name = "iperf"
	# app_inst.arguments = {"server": ""}
	app_inst.arguments = {"client": "192.168.1.37"}
	# app_inst.environment =
	# app_inst.clean_env =					
	# app_inst.map_err_to_out =

	# my_iface = thrift.Iface(if_name= "wlan0") 	# MOCKUP: This is obviously incomplete

	send('add_application', "kali", TSerialization.serialize(app_inst))
	# api_server.add_application("kali", app_inst)

	event_trigger = thrift.EventTrigger(name="kali_installed" ,enabled=True)
	event_trigger.conditions = {'kali.iperf_client': 'Installed'}

	send('def_event',TSerialization.serialize(event_trigger))


	send('start_experiment')

	# 
	time.sleep(60)
	# waitforEvent("experimentOver")
	# waitforEvent("kali_installed")

def kali_installed():
	send('startAllApps',"kali")

	time.sleep(4)
	send('stopApp',"kali", "iperf_client")
	send('change_parameter',"kali", "iperf_client", "client", "192.168.1.35")

	time.sleep(10)
	send ('startApp',"kali", "iperf_client")




main()




# def send (*args):
# 	api_socket = context.socket(zmq.PAIR)
# 	wait_socket.connect("inproc://api")
# 	global api_socket
# 	message = ["",]
# 	message.extend(args)
# 	api_socket.send_multipart(message)
