#!/usr/bin/env python

import common

class RPIface (common.Common):

	def __init__(self, parent, iface):
		super(self.__class__, self).__init__("iface", iface.if_name, parent)