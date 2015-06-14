#!/usr/bin/env python


from rpnode import RPNode 
from rpapp import RPApp
# from iface import iface ?

import logging



def create_resource (child_type, parent_uid, *args):
	map_to_class = {'node': 'RPNode', 'application': 'RPApp', 'iface': 'RPIface'}
	# print globals()
	return globals()[map_to_class[child_type]](parent_uid, *args)

