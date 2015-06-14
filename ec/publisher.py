#!/usr/bin/env python

import sys
sys.path.append('../thrift_struct/gen-py')

import  Structures.ttypes as thrift
import random
import time
import zmq
from thrift import TSerialization
import threading

import logging


class Publisher:	# This class must be inside this module (this file), so it can call functions inside this script




	# pending_response  # Add message id of outgoing message when awaiting for a response. key-value=mid-timerhandler



	def __init__(self, host, port):
		# EC will use methods of this class instance to send messages. Create the publisher socket for that
		self.context = zmq.Context()
		# self.pub_socket = context.socket(zmq.PUB)
		# self.pub_socket.bind("tcp://%s:%s" %(host, port))
		self.host = host
		self.port = port

		publisher_t = threading.Thread(target=self.__publisher)
		publisher_t.daemon = True
		publisher_t.start()



	def __publisher (self):
		pipe_socket = self.context.socket(zmq.PULL)
		pipe_socket.bind("inproc://publisher")	
		publisher_socket = self.context.socket(zmq.PUB)
		publisher_socket.bind("tcp://%s:%s" %(self.host, self.port))
		while True:
			msg = pipe_socket.recv_multipart()
			logging.debug("Publishing message: {0}".format(msg))
			publisher_socket.send_multipart(msg)
		


	## METHODS TO SEND Create, Configure, Request & Release MESSAGES ##

	# IMPORTANT! Note that the wildcard (*) after the topic name is being added here for all type of 
	# FRCP messages so it can be abstracted everywhere else in the EC

	def __send(self, *args):
		pipe_socket = self.context.socket(zmq.PUSH)
		pipe_socket.connect("inproc://publisher")
		# message = ["",]	# Use if the API is using a REP socket
		message = [] 		# Use if the API is using a ROUTER socket
		message.extend(args)
		# logging.debug("TOSEND: {0}".format(message))
		pipe_socket.send_multipart(message)	


	def create (self, topic, child_type, *attachments):
		# Create message header:
		msg_id = random.randint(0, 2147483647)
		timestamp = time.time()
		msg_header = thrift.MsgHeader(version=1, mtype=thrift.MessageType.CREATE, msg_id=msg_id, source="ec", ts=timestamp )
		# Create message body:
		body_msg = thrift.CreateMsg(child_type=child_type)

		msg = [msg_header, body_msg]
		msg.extend(attachments)
		to_send = [topic+'.#',]
		logging.info("Creation message sent to topic {0}".format(to_send))
		serialized_msg = map(TSerialization.serialize, msg)
		to_send.extend(serialized_msg)
		# dprint ("INFORM", "msg_to_send:", to_send)
		self.__send(*to_send)

		# self.pub_socket.send(topic, zmq.SNDMORE)	
		# self.pub_socket.send(TSerialization.serialize(msg_header), zmq.SNDMORE)
		# self.pub_socket.send(TSerialization.serialize(body_msg), zmq.SNDMORE)
		# self.pub_socket.send(TSerialization.serialize(attachment))


	def config_subscription (self, topic, subscribe_to ):
		self.__configure (topic, thrift.ConfigType.SUBSCRIBE, subscribe_to+'.#')

	def set_state (self, topic, state):
		logging.info("set_state message sent to {0}. STATE: {1}".format(topic, state))
		self.__configure (topic, thrift.ConfigType.SET_STATE, state)

	def change_parameter (self, topic, parameter, new_argument):
		self.__configure (topic, thrift.ConfigType.CHANGE_PARAMETER, parameter, new_argument)

	def assign_name (self, topic, assigned_name):
		self.__configure (topic, thrift.ConfigType.ASSIGN_NAME, assigned_name)

	def __configure (self, topic, ctype, field, field2=None): 	# ctype must be thrift.ConfigType = {SUBSCRIBE, SET_STATE, ASSIGN_NAME}
		# Create message header:
		msg_id = random.randint(0, 2147483647)
		timestamp = time.time()
		msg_header = thrift.MsgHeader(version=1, mtype=thrift.MessageType.CONFIGURE, msg_id=msg_id, source="ec", ts=timestamp )
		# Create message body:
		body_msg = thrift.ConfigMsg(ctype=ctype, field=field, field2=field2)
		# self.pub_socket.send(topic+'.#', zmq.SNDMORE)	
		# self.pub_socket.send(TSerialization.serialize(msg_header), zmq.SNDMORE)
		# self.pub_socket.send(TSerialization.serialize(body_msg))
		self.__send(topic+'.#', TSerialization.serialize(msg_header), TSerialization.serialize(body_msg))


	def request (self, topic, field):
		# Create message header:
		msg_id = random.randint(0, 2147483647)
		timestamp = time.time()
		msg_header = thrift.MsgHeader(version=1, mtype=thrift.MessageType.REQUEST, msg_id=msg_id, source="ec", ts=timestamp )
		# Create message body:
		body_msg = thrift.RequestMsg(field=field)

		# self.pub_socket.send(topic+'.#', zmq.SNDMORE)
		# self.pub_socket.send(TSerialization.serialize(msg_header), zmq.SNDMORE)
		# self.pub_socket.send(TSerialization.serialize(body_msg), zmq.SNDMORE)
		# self.pub_socket.send(TSerialization.serialize(attachment))
		self.__send(topic+'.#', TSerialization.serialize(msg_header),
		 TSerialization.serialize(body_msg), TSerialization.serialize(attachment))

	def release (self, topic, field):
		# Create message header:
		msg_id = random.randint(0, 2147483647)
		timestamp = time.time()
		msg_header = thrift.MsgHeader(version=1, mtype=thrift.MessageType.RELEASE, msg_id=msg_id, source="ec", ts=timestamp )
		# Create message body:
		body_msg = thrift.ReleaseMsg(field=field)

		# self.pub_socket.send(topic+'.#', zmq.SNDMORE)
		# self.pub_socket.send(TSerialization.serialize(msg_header), zmq.SNDMORE)
		# self.pub_socket.send(TSerialization.serialize(body_msg), zmq.SNDMORE)
		# self.pub_socket.send(TSerialization.serialize(attachment))
		self.__send(topic+'.#', TSerialization.serialize(msg_header),
		 TSerialization.serialize(body_msg), TSerialization.serialize(attachment))

	## ------------------------------------------------------------- ##
