#!/usr/bin/env python

import time
import os
import sys
import random
import threading
import signal
import zmq
import logging
logging.basicConfig(level=logging.DEBUG, format= '%(levelname)s %(module)s %(funcName)s(): %(message)s')

import common
import rpnode

from thrift import TSerialization
import  Structures.ttypes as thrift



ec_address = "192.168.1.35"
pub_port = 9000
sub_port = 10000
common.Common.ec_address = ec_address

    
def watcher():
	"""Forks a process, and the child process returns.

	The parent process waits for a KeyBoard interrupt, kills
	the child, and exits.

	This is a workaround for a problem with Python threads:
	when there is more than one thread, a KeyBoard interrupt
	might be delivered to any of them (or occasionally, it seems,
	none of them).
	"""
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




# def listener():
# 	# Subscribe socket
# 	sub_socket = context.socket(zmq.SUB)
# 	listen_topic = 'negotiate.{0}'.format(provisional_uid)
# 	# listen_topic = ''
# 	sub_socket.setsockopt(zmq.SUBSCRIBE, listen_topic)
# 	# logging.info("Waiting for message on topic:%s", listen_topic )
# 	sub_socket.connect("tcp://%s:%s" %(ec_address, sub_port))
# 	global name_assigned
# 	while True:
# 		msg = sub_socket.recv_multipart()
# 		# TODO: Proper message checking
# 		topic = msg[0]									# We don't need it
# 		# logging.info("Received topic%s", topic)
# 		msg_header = TSerialization.deserialize(thrift.MsgHeader(), msg[1])
# 		bodymsg = TSerialization.deserialize(thrift.ConfigMsg(), msg[2])	
# 		if msg_header.mtype == thrift.MessageType.CONFIGURE and bodymsg.ctype == thrift.ConfigType.ASSIGN_NAME:
# 			name_assigned = bodymsg.field
# 			# logging.info("Assigned node_name:%s", name_assigned )
# 			return

# def request_node_name (prefered_name=""):
# 	# Publish socket
# 	pub_socket = context.socket(zmq.PUB)
# 	pub_socket.connect("tcp://%s:%s" %(ec_address, pub_port))

# 	topic = "negotiate.{0}".format(provisional_uid)
# 	# logging.info("I am sending a message to topic:%s", topic)
# 	msg_id = random.randint(0, 2147483647)
# 	timestamp = time.time()
# 	# CHECK: Using uid as source
# 	msg_header = thrift.MsgHeader(version=1, mtype=thrift.MessageType.INFORM, msg_id=msg_id, source="RC Startup script", ts=timestamp) 
# 	# Create message body:
# 	body_msg = thrift.InformMsg(itype=thrift.InformType.NEGOTIATE, field=know_my_name()) 
# 	coded_body_msg = TSerialization.serialize(body_msg)
# 	# print "\n\n\n"
# 	logging.info("Name negotiation msg:%s %s %s", topic, msg_header, body_msg)
# 	pub_socket.send(topic, zmq.SNDMORE)
# 	pub_socket.send(TSerialization.serialize(msg_header), zmq.SNDMORE)
# 	pub_socket.send(TSerialization.serialize(body_msg))	





def request_node_name (prefered_name=""):

	context = zmq.Context()
	# Publish socket
	pub_socket = context.socket(zmq.PUB)
	pub_socket.connect("tcp://%s:%s" %(ec_address, pub_port))
	# Subscribe socket
	sub_socket = context.socket(zmq.SUB)
	provisional_uid = random.randint(0, 2147483647)
	listen_topic = 'negotiate.{0}'.format(provisional_uid)
	sub_socket.setsockopt(zmq.SUBSCRIBE, listen_topic)
	# logging.info("Waiting for message on topic:%s", listen_topic )
	sub_socket.connect("tcp://%s:%s" %(ec_address, sub_port))

	topic = "negotiate.{0}".format(provisional_uid)
	# logging.info("I am sending a message to topic:%s", topic)
	msg_id = random.randint(0, 2147483647)
	timestamp = time.time()
	msg_header = thrift.MsgHeader(version=1, mtype=thrift.MessageType.INFORM, msg_id=msg_id, source="RC Startup script", ts=timestamp) 
	# Create message body:
	body_msg = thrift.InformMsg(itype=thrift.InformType.NEGOTIATE, field=prefered_name) 
	coded_body_msg = TSerialization.serialize(body_msg)
	# print "\n\n\n"
	logging.info("Name negotiation msg:%s %s %s", topic, msg_header, body_msg)
	pub_socket.send(topic, zmq.SNDMORE)
	pub_socket.send(TSerialization.serialize(msg_header), zmq.SNDMORE)
	pub_socket.send(TSerialization.serialize(body_msg))	

	# Message sent. Now wait for response:
	msg = sub_socket.recv_multipart()
	# TODO: Proper message checking
	# topic = msg[0]									# We don't need it
	# logging.info("Received topic%s", topic)
	msg_header = TSerialization.deserialize(thrift.MsgHeader(), msg[1])
	bodymsg = TSerialization.deserialize(thrift.ConfigMsg(), msg[2])	
	if msg_header.mtype == thrift.MessageType.CONFIGURE and bodymsg.ctype == thrift.ConfigType.ASSIGN_NAME:
		name_assigned = bodymsg.field
		# logging.info("Assigned node_name:%s", name_assigned )
		return name_assigned
	else:
		logging.error("Response message to request_node_name() is malformed")
		return ""


def know_my_name ():
	f = open("/proc/sys/kernel/hostname","r")
	return f.readline().split('\n')[0]
	# return sys.argv[1]

# # Start listening
# listener_t = threading.Thread(target=listener)
# listener_t.daemon = True				# IF it is a daemon it will be killed when the program finishes!!
# listener_t.start()
name_assigned = request_node_name(prefered_name=know_my_name())
# listener_t.join(20)
watcher()

node = rpnode.RPNode(name_assigned) 	# Creates an RC_node. Upon creation, any Resource (as defined in AbstractResource)
													# takes care of registering with EC and subscribing to its topic. It gathers 
													# information about himself here.

