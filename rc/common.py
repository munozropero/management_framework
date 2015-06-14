#!/usr/bin/env python
# FLAGGGG
import sys
sys.path.append('../thrift_struct/gen-py')

import time
import random
import threading
import zmq
from thrift import TSerialization
import  Structures.ttypes as thrift



import logging
# logging.basicConfig(level=logging.DEBUG, format= '%(levelname)s %(module)s %(name)s %(funcName)s(): %(message)s')



class Common (object):
	
	ec_address = "192.168.1.35"
	pub_port = 9000
	sub_port = 10000

	# type = {"node", "application", "iface"}
	# parent = UID of the parent topic. Please note: UID, not name!

	def __init__(self, type, name, parent=None):
		self.name = name
		self.type = type
		self.parent = parent
		if parent:
			self.uid = parent+'.'+name
			self.type_topic = parent+'.'+type
		else:
			self.uid = name
			self.type_topic = type

		logging.debug ("Name:%s", self.name)
		logging.debug ("uid:%s", self.uid)
		self.children = {"node": {}, "application": {}, "iface": {}}
		self.supported_types = {"node": ["application", "iface"], "application": [], "iface":  []} # This is, in fact, hard-coded, but CHECK
		
		self.topics = []
		self.stop_listening = False
		# Get connection parameters from config file (otherwise change implementation to pass it as an argument)

		##THIS HAS BEEN SUBSTITUTED BY THE STATIC VARIABLES OF COMMON
		# self.ec_address = "192.168.1.35"		# MOCKUP: This should not be hard-coded
		# pub_port = 	9000					# Equal to 'topics_port' on EC. MOCKUP: This should not be hard-coded
		# self.sub_port = 	10000				# Equal to EC Publisher port .MOCKUP: This should not be hard-coded
		##------------
		self.context = zmq.Context()	# ZMQContext is thread-safe within the same process

		# Create Publisher socket. 
		self.pub_socket = self.context.socket(zmq.PUB)
		logging.debug("Connecting to tcp://%s:%s", self.ec_address, self.pub_port)
		self.pub_socket.connect("tcp://%s:%s" %(self.ec_address, self.pub_port))

		# Create PAIR socket to update topic_listener's subscription
		self.pair_socket = self.context.socket(zmq.PAIR)
  		self.pair_socket.bind("inproc://addtopic")

		# Start topic_listener thread
		self.topic_listener_thread = threading.Thread(target=self.topic_listener) 
		self.topic_listener_thread.start()

		# Listen by default to:			
		self.addtopic(self.uid+'.#')			# "<uid>.#" . E.g.: "tplink01.#" or "tplink01.iperf_server.#" 
		self.addtopic(self.type_topic+'.#')		# "<parent_topic>.<childresource_type>.#". E.g.: "node.#" or "tplink01.application.#" 

				

	## MESSAGING FUNCTIONS ##		

	def topic_listener(self):
		# Create socket to receive topic subscriptions commands
		get_socket = self.context.socket(zmq.PAIR)
		get_socket.connect("inproc://addtopic")
		# Create socket to listen to topics of its interest
		sub_socket = self.context.socket(zmq.SUB)	
		sub_socket.connect("tcp://%s:%s" %(self.ec_address, self.sub_port))
		# poller.poll() will return when any of the registered sockets got a message
		poller = zmq.Poller()
		poller.register(get_socket, zmq.POLLIN)
		poller.register(sub_socket, zmq.POLLIN)

		while True:		
			socks = dict(poller.poll())		# Waiting for a message on ANY of the registered sockets
			if get_socket in socks and socks[get_socket] == zmq.POLLIN:
				msg = get_socket.recv_multipart()
				if msg[0] == "addtopic":
					topic = msg[1]
					sub_socket.setsockopt(zmq.SUBSCRIBE, topic)
					self.topics.append(topic)					# Keep track of the topics we are listening to.
					logging.info("{0} {1} is subscribed to:%s".format(self.type, self.uid) , self.topics)
				elif msg[0] == "terminate":
					print "Resource's topic_listener thread terminated"
					return
			if sub_socket in socks and socks[sub_socket] == zmq.POLLIN:
				received_msg = sub_socket.recv_multipart()
				logging.info("Common Resource got a message with topic:%s", received_msg[0] )
				self.message_handler(received_msg)
				# message_handler_thread = threading.Thread(target=self.message_handler, args=[received_msg])
				# message_handler_thread.daemon = True 	# CHECK: How do you want this to be?
				# message_handler_thread.start()		


	def message_handler(self, msg):	# CHECK: IS IT NECESSARY TO HAVE IT DECLARED IN THE SUPERCLASS IF YOU HAVE IT IN THE SUBCLASS?
		logging.debug ("Entered function")
		if len(msg) < 3:
			logging.error("ERROR", "Received message is incomplete (topic, header or bodymsg may be missing)")
			# ERROR
		else:
			topic = msg[0]
			msg_header = TSerialization.deserialize(thrift.MsgHeader(), msg[1])
	
			messagetype = ('CREATE', 'CONFIGURE', 'REQUEST', 'RELEASE', 'INFORM')	## DEBUGGING ONLY. ERASE AFTERWARDS!
			logging.info("Got a message of type:%s", messagetype[msg_header.mtype])
			function_mapper = ('CreateMsg', 'ConfigMsg', 'RequestMsg', 'ReleaseMsg')
			# decoding_base = globals()["thrift."+function_mapper[msg_header.mtype]] ## REMOVE. This would produce a key error
			decoding_base = getattr(thrift, function_mapper[msg_header.mtype])
			bodymsg = TSerialization.deserialize(decoding_base(), msg[2])	
			coded_attachments = msg[3:len(msg)]
			if topic != self.name and topic in self.topics: # Then it should be addressed to a group the node is member of
				group = topic.split(".#")[0]	# Since all topics end in ".#", it must be removed to get the group name.
			else:
				group = None
			# TODO: Keep working on making it more generic later
			if msg_header.mtype == thrift.MessageType.CREATE:
				self.create (bodymsg.child_type, group, coded_attachments)
			elif msg_header.mtype == thrift.MessageType.CONFIGURE:	
				self.configure(bodymsg)
			elif msg_header.mtype == thrift.MessageType.REQUEST:	#MOCKUP
				body_base = thrift.RequestMsg()
			elif msg_header.mtype == thrift.MessageType.RELEASE:	#MOCKUP
				body_base = thrift.ReleaseMsg()
			else:
				logging.error("ERROR", "Wrong MessageType: {0}".format(msg_header.mtype))


	def inform(self, _topics, itype, cid=None, field=None, nodeinfo=None):
		# Create message header:
		msg_id = random.randint(0, 2147483647)
		timestamp = time.time()
		# CHECK: Using uid as source
		msg_header = thrift.MsgHeader(version=1, mtype=thrift.MessageType.INFORM, msg_id=msg_id, source=self.uid, ts=timestamp) 
		# Create message body:
		body_msg = thrift.InformMsg(itype=itype, cid=cid, field=field, nodeinfo=nodeinfo) # , nodeinfo=nodeinfo
		coded_body_msg = TSerialization.serialize(body_msg)
		# print "\n\n\n"
		self.pub_socket.send(_topics, zmq.SNDMORE)
		self.pub_socket.send(TSerialization.serialize(msg_header), zmq.SNDMORE)
		self.pub_socket.send(TSerialization.serialize(body_msg))



	def addtopic(self, topic):
		self.pair_socket.send_multipart(["addtopic",topic])


	## -------------------- ##




	## CALLED BY MESSAGE HANDLER ##


	def create (self, child_type, group, coded_attachments):
		from resourcefactory import create_resource
		if child_type not in self.supported_types[self.type]:
				logging.error("This resource cannot create this type of child")
				return	

		if child_type == "application":
			app = TSerialization.deserialize(thrift.App(), coded_attachments[0])
			appinstance =  TSerialization.deserialize(thrift.AppInstance(), coded_attachments [1])
			child_name = appinstance.inst_name
			attachments = [app, appinstance]
			
		elif child_type == "iface":		# Should be ready to use. Just uncomment
			iface = TSerialization.deserialize(thrift.Iface(), coded_attachments[0])
			child_name = iface.if_name
			attachments = [iface,]
			# self.children[child_type][child_name] = Iface(self.uid, iface)

		self.children[child_type][child_name] = create_resource (child_type, self.uid, *attachments)
		if group: 	# If the create FRCP message was addressed to a group, must make them subscribe to group topics this way:
			self.children[child_type][child_name].addtopic(group+'.'+child_name+'.#') # Ex.: "workers.iperf"
			self.children[child_type][child_name].addtopic(group+'.'+child_type+'.#') # Ex.: "workers.application"



	## ------------------------- ##




	def terminate (self):	
		self.pair_socket.send_multipart(["terminate",])









