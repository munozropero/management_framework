
import common
import  Structures.ttypes as thrift
import subprocess
import threading
import time
import signal


import logging


class RPApp (common.Common):


	# binary_path 			 # (String) the path to the binary of this app
##	running_app 			 # Pointer/<Whichever object> pointing to the running app, in order
							 # to manipulate/terminate it
	# pkg_opkg 				 # (String) the name of the OPKG package for this app							
	# pkg_tarball 			 # (String) the URI of the installation tarball of this app
							 # Tarball must contain compiled binaries! Specify installation folder or will be located on default
	# tarball_installdir 		 # (String)	the path where the tarball should be installed to. 
							 # By default: TODO: Define this				
	# force_tarball_install	 # (Boolean) if true then force the installation from tarball even if other distribution
							 # specific installation are available (default false)

	# description 			 # DECISION: Am I actually going to use this for anything?

	# state 					 # (String/Enum) the state of this Application RP (Created, Installed, Stopped, Running, Paused, Finished)
							 # DECISION: Call it 'Created' or maybe better 'InstallING' ??
##	installed 				 # (Boolean) is this application installed? (default false) # IS THIS NECESSARY?

##	map_err_to_out 			 # (Boolean) if true then map StdErr to StdOut for this app (default false)
	# environment 			# The environment variables to set prior to starting this app. 
							# {k1 => v1, ...} will result in "env -i k1=1 ..." (with k1 being either a string or a symbol)
	# clean_env 			 # (Boolean) if true, application will be executed in a clean(=empty) environment (env -i).
						 # Default is TRUE.

	# time_to_close			# Time an application has to terminate itself when receives SIGTERM before it is sent SIGKILL


	# parameters = { 
	# 	paramname1: {
	# 		cmd 		# (String) Command line for the parameter. i.e., if the programm expects 
	# 					# this parameter to appear after "-p" the cmd="-p"
	# 		order 		# (Int) the appearance order on the command line, default FIFO
	# 		type 		# (Numeric|String|Flag) this parameter's type. Will be checked. Flag means that there is no
	# 					# value after the option (for example with 'iperf -c'). So 'True' means present, 'False' means omit it
	# 		default 	# Value given by default to this parameter
	# 		value 		# Value that will be set for this parameter once the arguments are provided
	# 		mandatory 	# (Boolean) This parameter is mandatory. Default false

	# 	}
	# 	paramname2: {...}
	# 	.
	# 	.
		
	# }


# Rcapp specific threads:
# - Install thread
# - has_finished/ is_application_finished thread
# - Running program process!




# UNNECESSARY SO FAR:
# Don't keep a self.parameter[param_name].order value. You are already saving the names ordered in a list
# 
# IS IT NECESSARY?:
# Shouldnt parameter.type be already checked in EC?
# 

	def __init__(self, parent, app, appinstance): 
		super(self.__class__, self).__init__("application", appinstance.inst_name, parent)	# Instantiate the 'Common' part of application resource.
			
		# Map all the content of 'app' and 'appinstance' in this RC_application:
		self.binary_path = app.binary_path	# TODO: Think more about this and its relationship with the installation and command line creation
		self.pkg_opkg = app.pkg_opkg
		self.pkg_tarball = app.pkg_tarball
		self.force_tarball_install = app.force_tarball_install
		self.description = app.description
		self.tarball_installdir = None		#MOCKUP	# DECISION: What is the default install dir for tarballs?. Read from config file?
		if app.tarball_installdir != '':
			self.tarball_installdir = app.tarball_installdir
		self.environment = appinstance.environment
		logging.info ( "Environment:%s", self.environment)
		self.clean_env = appinstance.clean_env		

		self.command_line = []
		self.app = app
		self.appinstance = appinstance

		self.build_command_line()
		self.forced_to_terminate = False
		self.state = ''
		self.__update_state('Created') 

		# TODO: Now must check if this application already exists in the system		
		# Check if this application already exists in the system. When found, set installed=True, state=Installed
		# 	- Check if the binary_path file exists in the system	# If no binary path specified then false.
		# 	- Check if the package manager(s) has it installed.	# If no package specified then false. 
		logging.info("I AM JUST BEFORE REPORTING INSTALLED")
		#MOCKUP!!
		self.__update_state('Installed') # For the mockup I will only use already-installed applications
										 # Application installation is out of the scope due to time constraints
		
		# install_thread = threading.Thread(target=install) 	# By creating a thread we relieve the node from waiting
		# install_thread.start()								# for the children to finish installation.

		


	# Build the command line, which will be used to start this app. 
	def build_command_line(self):

		options = []
		no_priority_order = 100		# Ridiculously high number to make sure there is no parameter.order with such a number.
									# Still it works to order in a FIFO fashion the paramters with no fixed order.
		for parameter in self.app.parameters:
			if parameter.name not in self.appinstance.arguments:
				if parameter.mandatory:
					logging.error("Parameter {0} is mandatory, yet no argument was given".format(parameter.name))
				elif parameter.type.lower() == "flag":
					if parameter.default_value.lower() != "true": # default values are given as a string
						continue
					else:
						value = '' 
				else:
					if parameter.default_value: # If a default value was given
						value = ' '+parameter.default_value		
					else:
						continue # If the no argument is passed and there is no default value, do not include parameter
			else:
				if parameter.type.lower() == "flag":
					value = ''
				else:
					value = self.appinstance.arguments[parameter.name]

			option = [parameter.cmd,] if parameter.cmd else []	#e.g.: ['-c', '3000']
			if value:
				option.append(value)
			if parameter.order:
				options.append((option, parameter.order))		
			else:											
				options.append( (option, no_priority_order))
				no_priority_order += 1					

		# Sort 'options' according to the 2nd element of each option tuple i.e., paramter.order or no_priority_order
		ordered_tuples = sorted(options, key= lambda option: option[1])
		self.c_line_options = []
		for tuple_item in ordered_tuples:
			self.c_line_options.extend(tuple_item[0]) 

		self.command_line = [self.binary_path, ]
		self.command_line.extend(self.c_line_options)
		# return command_line


	# Update its own state and generate an inform message for EC reporting the change
	def __update_state(self, state): 
		if state != self.state:
			self.state = state
			self.inform("events.application.{0}".format(self.uid) , thrift.InformType.STATUS, field=state)
			logging.debug ("Reporting state: {0} {1}".format(self.uid, self.state))


	def has_application_finished(self):
		self.running_app.wait() 	# Wait until the application has finished
		if self.running_app.returncode == 0:	 # When wait() returns with returcode==0 it means the app has finished gracefully
			if not self.forced_to_terminate:	 # either by SIGTERM or on its own
				logging.debug("Application finished naturally. Returncode %d", self.running_app.returncode)
				self.__update_state('Finished') 	
			else:
				logging.debug("Application was terminated but finished gracefully with returncode = %d", self.running_app.returncode)
				self.forced_to_terminate = False
		elif abs(self.running_app.returncode) in (signal.SIGTERM, signal.SIGKILL, signal.SIGSTOP):
			logging.info("Application process was stopped or paused. Returncode = {0}".format(self.running_app.returncode))
		else: 
			logging.error("Application finished with unexpected returncode = {0}".format(self.running_app.returncode))
			

	## FUNCTIONS TO BE CALLED BY message_handler ##


	def configure (self, bodymsg):
		map_to_name = ['SUBSCRIBE', 'SET_STATE', 'ASSIGN_NAME', 'CHANGE_PARAMETER'] # Debugging purpose only
		logging.debug("CONFIGURE Message of type {0}".format(map_to_name[bodymsg.ctype]))
		if bodymsg.ctype == thrift.ConfigType.SUBSCRIBE:
			self.addtopic(bodymsg.field)
		elif bodymsg.ctype == thrift.ConfigType.SET_STATE:
			self.configure_state(bodymsg.field)
		elif bodymsg.ctype == thrift.ConfigType.CHANGE_PARAMETER:
			self.change_parameter(bodymsg.field, bodymsg.field2)


	def change_parameter (self, parameter, new_argument):
		logging.debug("Changing parameter %s to %s", parameter, new_argument)
		self.appinstance.arguments[parameter] = new_argument
		self.build_command_line()


 	# State:(Created, Installed, Stopped, Running, Paused, Finished)
	# State Cycle: Created --> Installed --> Running --> Finished/Stopped/Paused --> Running --> Finished/Stopped/Paused -->  ..
	def configure_state (self, desired_state):
		allowed_transitions = ({'Created': [], 'Installed': ['Running'], 'Running': ['Finished', 'Stopped', 'Paused'], 
								'Finished': ['Running'] , 'Stopped': ['Running']  , 'Paused': ['Running', 'Stopped']})
		if desired_state in allowed_transitions[self.state]:
			# globals()['switch_to_'+desired_state.lower()]() # Equal to 'switch_to_<desired_state>()'
			switch_function = getattr(self, 'switch_to_'+desired_state.lower())
			switch_function()
		else:
			logging.error("Illegal state transistion. Current state: {0}. Desired state: {1}".format(self.state, desired_state))


	# 	## FUNCTIONS FOR configure_state ##


	def switch_to_running (self):
		# Switch this Application RP into the 'running' state.
		logging.debug ("Previous state: {0}".format(self.state))
		if self.state in ('Installed','Stopped', 'Finished'):
			# TODO: This is still rudimentary. Must attend to 'map_err_to_out', 'clean_env' and 'environment'
			logging.info ( "build_command_line(): _{0}_".format(self.build_command_line()))
			self.running_app = subprocess.Popen( self.command_line ,stdout=subprocess.PIPE)
			has_finished = threading.Thread(target=self.has_application_finished) 	# We start a thread that will wait for 
			has_finished.daemon = True 
			has_finished.start() # Start the thread that will wait for the application to finish.
		elif self.state == 'Paused': 		
			logging.debug("Entered the 'Paused' branch")
		 	self.running_app.send_signal(signal.SIGCONT)				# Resume application
		self.__update_state('Running')



	def switch_to_stopped(self):
		logging.debug("Entered function")
		self.forced_to_terminate = True
		self.running_app.terminate()	# This is the subprocess.terminate() method!
		time_to_close = 5				# CHECK: Maybe this should be a global parameter? Or read from config file?
		time.sleep(time_to_close)
		if self.running_app.poll() is None:		# This means the subprocess hasn't exited yet
			logging.info ("Application couldn't be terminated. Now it will be killed")
			self.running_app.kill()		# This time the application stops whether it wants it or not

		self.__update_state('Stopped')


	# Switch this Application RP into the 'paused' state. If this is possible at all
	def switch_to_paused (self):
		logging.debug ("Entered function")
		self.running_app.send_signal(signal.SIGSTOP)
		self.__update_state('Paused')

	## FUNCTIONS DECLARED IN 'COMMON' ##


	def terminate(self):
		# This method will only be called from outside
		super(RPApp, self).terminate()	# This terminates the resource topic_listener thread. No more messages will be received.
		self.configure_state('Stopped')
		# has_finished thread is a daemon and also it will die when the program leaves. No need to kill it
		# install_thread.join()
		print "Application Resource {0} terminated".format(self.uid)
		

	## ------------------------------ ##


	# install ():
	# # Switch this Application RP into the 'installed' state.
	# # Can only switch from 'created' state, otherwise all the remaining options mean it is already installed
	# # if installed = False:
	# #	if force_tarball_install==False and pkg_opkg != '':
	# #		install_opkg(pkg_opkg)
	# #	else:
	# #		install_tarball(pkg_tarball, tarball_installdir)

	# __install_tarball (pkg_tarball, tarball_installdir):
	# 	# Create ./tmp folder
	# 	# Download compiled tarball from pkg_tarball uri in ./tmp
	# 	# Untar downloaded file in ./tmp/<tarname>
	# 	# If there is a Makefile among the untar'ed files:
	# 	# 	Execute 'make install' 
	# 	# else:
	# 	# 	mv ./tmp/<tarname>/*  $tarball_installdir
	# 	# installed = True
	# 	# __update_state('Installed')

	# # Installs package out of a tarball located at pkg_tarball URI in tarball_installdir
	# # If anything fails (=catch exception) : Send inform message


	# __install_opkg (pkg_opkg):
	# 	# Run command line 'opkg install <pkg_opkg>'
	# 	# Run 'which <pkg_opkg>' and assign its output to self.binary_path
	# 	# installed = True
	# 	# __update_state(Installed)
	# 	# 
	# 	# If anything fails (catch exception or which doesn't output anything):
	# 	# 	send inform warning message

	# 	KEEP IN MIND THAT IF WHICH CAN FIND IT, THEN YOU DONT NEED TO SPECIFY THE FULL PATH,
	# 	JUST THE NAME, SO THIS DOESNT MAKE MUCH SENSE ASIDE FROM EARLY ERROR DETECTION.


	