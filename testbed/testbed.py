from fabric.api import env

S='123456'
S_A='certus2015'

# hosts info
admin = 'root@172.16.33.14'
controller1 = 'root@172.16.161.202'
controller2 = 'root@172.16.161.201'
controller3 = 'root@172.16.161.204'
computer1 = 'root@172.16.161.161'
computer2 = 'root@172.16.161.171'
#computer3 = 'root@172.16.161.157'
#computer4 = 'root@172.16.161.160'
#computer5 = 'root@172.16.161.172'
#ctrl1='root@172.16.120.160'
#cmpt1='root@172.16.120.162'

env.roledefs = {
		'admin': [admin], 
		'ceph-nodes': [admin],
		'controllers' : [controller1, controller2, controller3],
		'computers' : [computer1, computer2],
		#'controllers' : [ctrl1],
		#'computers' : [cmpt1]
		}

# password of each host
env.passwords = {admin: S_A, controller1: S, controller2: S, controller3: S, computer1: S, computer2: S}


