
#include "Messages.thrift"


struct Parameter {
	1: string name,
	2: string cmd
	3: string type,
	4: string default_value,
	5: bool mandatory = false,
	6: i16 order
}

struct App {
	1: string ap_name
	2: string binary_path										
	3: list<Parameter> parameters 
	4: string pkg_opkg								
	5: string pkg_tarball							
	6: string tarball_installdir			
	7: bool force_tarball_install								
	8: string description									
}
	

struct AppInstance { 
	1: string inst_name
	2: string app_name
	3: map<string,string> arguments     # { "client": 'True', "port" : '3000'}
	4: map<string,string> environment
	5: bool clean_env					# If true, application will be executed in a clean(=empty) environment (env -i).
	6: bool map_err_to_out

}

#struct IfaceInfo {
#	1: string if_name,	
#	2: string phy,
#	3: string mode,
#	4: i16 channel,
#}

struct AppInfo {
	1: string app_name
	2: string inst_name
	3: string state
}





struct Iface {
	1: string if_name
	2: string phy
	3: string mode
	4: i32 channel
	5: string start_ipaddress			# If 192.168.1.10 is given and the group members are [node1, node2,node3]
										# The IP's will be assigned like this: node1:192.168.1.10, node2:192.168.1.11, node3:192.168.1.12
	6: map <string,string> ip_mapping	# Map keys are the nodes names and string is the IP associated to it
	7: string essid
}


struct NodeInfo {
	1: string node_name,
	2: string os,
	3: list<AppInfo> apps,
	4: list<Iface> ifaces
}


struct EventTrigger {	
	1: string name 								
	2: map<string,string> conditions		# Examples tkn.tplink01.iperf.state = Finished tkn.tplink02.state = Ready 
	3: i32 timer 						# Seconds until the timer is triggered. If none given, it won't be timer activated
	4: bool enabled								# Is the event enabled? Timer starts once enabled 
	5: bool periodic							# Does it trigger once or every 'timer' seconds ?
												# For an event with conditions and timer. The timer will only fire if the conditions are met.
												# Also, conditions won't fire anything until timer "rings"
												# If only conditions or timer are given 
	#X: list <string> checkfor					# JUST AN IDEA
}

# <node/group>.<target_app>.<attribute>  . Although so far <attribute> is ignored
	# Examples: TPLINK.iperf_server.status



##----------- MESSAGES ----------- ##


enum MessageType {
	CREATE,
	CONFIGURE,
	REQUEST,
	RELEASE,
	INFORM
}


enum ConfigType {
	SUBSCRIBE,
	SET_STATE,
	ASSIGN_NAME,
	CHANGE_PARAMETER
}




enum InformType {
	CREATION_OK,		 	# Uid of the child resource in 'field'
	CREATION_FAILED,		# Uid of the failed child resource in 'field'
	STATUS,					# Status in 'field'
	NEGOTIATE,				# Negotiate name of recently started node. Include 'prefered_name' in 'field'
	REGISTER,				# First node registration to EC. Include NodeInfo structure
	RELEASED,				# Uid of the released child resource in 'field'
	ERROR,					# Describe error in 'field'
	WARN					# Describe error in 'field'
}




struct CreateMsg {
	1: string child_type
}

struct ConfigMsg {
	1: ConfigType ctype,
	2: string field,
	3: string field2
}

struct RequestMsg {
	1: string field
}

struct ReleaseMsg {
	1: required string field
}



struct InformMsg {
	1: InformType itype, 		# Inform message subtype
	2: i32 cid, 					# Which msg id where are answering to
	3: optional string field,
	4: optional NodeInfo nodeinfo
}


struct MsgHeader { 
	1: i32 version,
	2: MessageType mtype,
	3: i32 msg_id,
	4: string source,
	5: double ts	#timestamp in seconds since the epoch. Floating point number
}
