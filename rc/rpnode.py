#!/usr/bin/env python



import sys
sys.path.append('../thrift_struct/gen-py')

import  Structures.ttypes as thrift
from thrift import TSerialization
import threading
import common

import logging

class RPNode (common.Common):

	def __init__(self, name):
		super(self.__class__, self).__init__("node", name)
		self.os = "OpenWRT"			#MOCKUP
		self.report_time = 60			#MOCKUP. Should not be hard-coded
		# TODO: Here discover the name (only the name of the current interfaces) and create an Iface structure
		# for each one, filling only the name. Instantiate an RCIface for each one and call their self-discovery methods
		# so each interface fills the rest of the information by itself. Once that is done (probably sequentally), you 
		# can call self.register_to_ec()
		self.register_to_ec()
		# We set the first timer to report 'i_am_alive' to the EC
		self.periodic_handler = threading.Timer(self.report_time, self.periodic_action) 	
		# self.periodic_handler.daemon = True
		self.periodic_handler.start()


	def periodic_action(self):
		self.i_am_alive()
		self.periodic_handler = threading.Timer(self.report_time, self.periodic_action) # Restart timer so this happens periodically
		self.periodic_handler.daemon = True
		self.periodic_handler.start()


	def register_to_ec(self):
		logging.info("Register to EC")
		nodeinfo = thrift.NodeInfo()
		nodeinfo.node_name = self.name
		nodeinfo.os = self.os
		#TODO: Here is missing information on nodeinfo.apps and nodeinfo.ifaces!
		self.inform(self.uid, thrift.InformType.REGISTER, nodeinfo=nodeinfo)


	def i_am_alive(self):
		self.inform("events.node.{0}".format(self.name) , thrift.InformType.STATUS, field="Ready")


	def terminate(self):					# The way 'resourcecontroller' finishes the program right now, this method doesn't make
		super(RPNode, self).terminate()		# much sense for rpnode. It is useful to kill child resources, not to end the whole program
		self.periodic_handler.cancel()		# (which consists mostly in killing rpnode)
		print "Node resource has terminated periodic EC report thread"		


	def configure (self, bodymsg):
		if bodymsg.ctype == thrift.ConfigType.SUBSCRIBE:
			self.addtopic(bodymsg.field)
			logging.info("{0} {1} is subscribed to:%s".format(self.type, self.uid) , self.topics)
		elif bodymsg.ctype == thrift.ConfigType.SET_STATE:
			logging.error("Node Resource doesn't allow configuration of attribute 'state'")
			# FOR NOW Only RCApp is meant to have its state configurable

