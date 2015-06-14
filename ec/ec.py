#!/usr/bin/env python

import sys
import os
sys.path.append('../thrift_struct/gen-py')

import time
import logging
logging.basicConfig(level=logging.DEBUG, format= '%(levelname)s %(module)s %(funcName)s(): %(message)s')

import  Structures.ttypes as thrift
import apiserver
import ecsession
import publisher

from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer

child = None

def watcher():
	"""Forks a process, and the child process returns.

	The parent process waits for a KeyBoard interrupt, kills
	the child, and exits.

	This is a workaround for a problem with Python threads:
	when there is more than one thread, a KeyBoard interrupt
	might be delivered to any of them (or occasionally, it seems,
	none of them).
	"""
	global child
	child = os.fork()
	if child == 0:
		return
	try:
		os.wait()
	except KeyboardInterrupt:
		print '\nFinishing Resource Controller'
		try:
			os.kill(child, signal.SIGKILL)
		except OSError:
			pass
	sys.exit()



# watcher()

# print child

host = "192.168.1.35"	# Read from file, command line or set to *
ec_listen_port = 9000	# Read from file, command line or fix it
api_listen_port = 1818 	# Read from file, command line or fix it

publisher = publisher.Publisher(host, 10000)

ec_session = ecsession.ECSession (publisher, host, ec_listen_port)

api_server = apiserver.APIServer (ec_session, publisher, host, api_listen_port)



# ## Instead of the user, we do a mockup calling api_server methods ##

# time.sleep(5) 		# Give nodes time to register to EC


# myapp = thrift.App(ap_name="iperf", binary_path="/usr/bin/iperf", description="Hello World Application")
# myapp.parameters =  ([thrift.Parameter(name="server", cmd='-s', type= "Flag", default_value="False"), 
# 	thrift.Parameter(name="client", cmd='-c', type= "String")] )

# api_server.def_application(myapp)
# api_server.def_group ("Servers", ["kali",])

# app_inst = thrift.AppInstance()
# app_inst.inst_name = "iperf_server"
# app_inst.app_name = "iperf"
# app_inst.arguments = {"server": ""}
# # app_inst.arguments = {"client": "192.168.1.35"}

# # app_inst.environment =
# # app_inst.clean_env =					
# # app_inst.map_err_to_out =


# my_iface = thrift.Iface(if_name= "wlan0") 	# MOCKUP: This is obviously incomplete

# time.sleep(3)
# api_server.add_application("Servers", app_inst)
# # api_server.add_application("TPLINK", app_inst)



# event_trigger = thrift.EventTrigger (name="timerallready" ,enabled=True)
# event_trigger.conditions = {'TPLINK.iperf_server': 'Installed'}

# api_server.def_event(event_trigger)

# api_server.start_experiment()

# time.sleep(1)
# api_server.startAllApps ("Servers")

# time.sleep(4)
# api_server.pauseApp("Servers", "iperf_server")


# time.sleep(10)
# api_server.startApp("Servers", "iperf_server")


# # print api_server.get_resources()

# time.sleep(3600)


## ------------------------------------------------------------   ##


# event_manager = EventManager() 	

# ec_session = ECSession(event_manager)		# Should start a timer thread that triggers 'check_nodes_reported()'
# 											# Events inside must be able to call certain 'notify_user()' function

# messenger = PSMessaging(host,port, ec_session) 	# Must pass ec_session to PSMessaging can use EC records and methods 							

# api_server = APIServer(ec_session, messenger) 	# Must pass ec_session so the API server can use EC records and methods
# 												# Must be able to send messages to RC

