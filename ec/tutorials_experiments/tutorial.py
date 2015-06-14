#!/usr/bin/env python

import sys
sys.path.append('../../thrift_struct/gen-py')

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


def event_functions_actuator():
	event_socket = context.socket(zmq.PULL)
	event_socket.connect("tcp://%s:%s" %(host, events_port))
	forward_event_socket = context.socket(zmq.PAIR)
	forward_event_socket.bind("inproc://forward")
	while True:	
		event_name = event_socket.recv()
		forward_event_socket.send(event_name)
		try:
			function_to_call = globals()[event_name]
			call_function_t = threading.Thread(target=function_to_call)
			call_function_t.daemon = True
			call_function_t.start()
		except KeyError:
			logging.info("No action scheduled for received event '{0}'".format(event_name))
		



# The purpose of this funciton is pause execution until event occurs
def waitforEvent(event_name):
	wait_socket = context.socket(zmq.PAIR)
	wait_socket.connect("inproc://forward")
	while True:
		if event_name == wait_socket.recv():
			logging.debug("Event '{0}'. Now ED can continue".format(event_name))
			return


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


scp = thrift.App(ap_name="scp", binary_path="/usr/bin/scp", description="SSH Copy")
scp.parameters =  ([thrift.Parameter(name="origin", cmd='', type= "String"), 
	thrift.Parameter(name="destiny", cmd='', type= "String")] )


# scp -P 3000 plopenwrt.pdf pi@81.33.172.75:/home/pi/

# ping = thrift.App(ap_name="scp", binary_path="/bin/ping" )
# ping.parameters =  ([thrift.Parameter(name="host", cmd='', type= "String"))
# defApplication(ping)

send('def_application', TSerialization.serialize(scp) )

send('def_group', "copiers", 'tplink02', 'tplink03')


scp_instance = thrift.AppInstance()
scp_instance.inst_name = "scp_tplink02"
scp_instance.app_name = "scp"
# app_inst.arguments = {"server": ""}
scp_instance.arguments = {"origin": "~/experiment/foo", "destiny": "tplink02:~/experiment/tplink02"}

scp_instance2 = thrift.AppInstance()
scp_instance2.inst_name = "scp_tplink03"
scp_instance2.app_name = "scp"
# app_inst.arguments = {"server": ""}
scp_instance2.arguments = {"origin": "~/experiment/foo", "destiny": "tplink03:~/experiment/tplink03"}

send('add_application', 'tplink01', TSerialization.serialize(scp_instance))
send('add_application', 'tplink01', TSerialization.serialize(scp_instance2))


scp_instance2.inst_name = "scp_inst"
scp_instance2.arguments = {"origin": "~/experiment/tplink02/foo", "destiny": "tplink04:~/experiment/tplink04"}

send('add_application', 'copiers', TSerialization.serialize(scp_instance2))


all_apps_installed = thrift.EventTrigger(name="allAppsInstalled" ,enabled=True)
all_apps_installed.conditions = {'tplink01.scp_tplink02': 'Installed', 'tplink01.scp_tplink03': 'Installed', \
							'tplink02.scp_inst': 'Installed', 'tplink03.scp_inst': 'Installed'}

first_transfer_event = thrift.EventTrigger(name="firstTransferFinished" ,enabled=True)
first_transfer_event.conditions = {'tplink01.scp_tplink02': 'Finished'}

second_transfer_event = thrift.EventTrigger(name="secondTransferFinished" ,enabled=True)
second_transfer_event.conditions = {'tplink01.scp_tplink03': 'Finished'}

all_apps_finished = thrift.EventTrigger(name="allAppsFinished" ,enabled=True)
all_apps_finished.conditions = {'tplink01.scp_tplink02': 'Finished', 'tplink01.scp_tplink03': 'Finished', \
							'tplink02.scp_inst': 'Finished', 'tplink03.scp_inst': 'Finished'}							


send('def_event',TSerialization.serialize(all_apps_installed))
send('def_event',TSerialization.serialize(first_transfer_event))
send('def_event',TSerialization.serialize(second_transfer_event))
send('def_event',TSerialization.serialize(all_apps_finished))


waitforEvent ('allAppsInstalled')

send('change_parameter', "tplink03", "scp_inst", "origin", "~/experiment/tplink03/foo")
send('change_parameter', "tplink03", "scp_inst", "destiny", 'tplink05:~/experiment/tplink05')

send('startApp', 'tplink01', 'scp_tplink02')
send('startApp', 'tplink01', 'scp_tplink03')


waitforEvent ('allAppsFinished')

send ('terminateExperiment')


def onTP02finished ():
	send('startApp', 'tplink02', 'scp_inst')


def onTP03finished ():
	send('startApp', 'tplink03', 'scp_inst')




