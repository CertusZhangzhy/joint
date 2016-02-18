#!/usr/bin/env python
#-*- coding:utf-8 -*-

import sys
reload(sys)
sys.setdefaultencoding('utf-8')
from fabric.api import *
from fabric.state import connections
from paramiko.ssh_exception import SSHException
import os
import re
import time
import copy
from testbed.testbed import *

class Logger(object):
    def __init__(self, filename = 'fabric.log'):
        self.terminal = sys.stdout
        self.log = open(filename, 'a')

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def isatty(self):
        return self.terminal.isatty()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

class ErrLogger(Logger):
    def __init__(self, filename = 'fabric.log'):
        super(ErrLogger, self).__init__(filename)
        self.terminal = sys.stderr

sys.stdout = Logger()
sys.stderr = ErrLogger()

@task
def execute_controllers(cmd):
    '''To run a command on controllers.'''
    hosts = get_control_hosts()
    for host in hosts:
        with settings(host_string = host[0], password = host[1], warn_only = True):
            run(cmd)
@task
def execute_computers(cmd):
    '''To run a command on computers.'''
    hosts = get_compute_hosts()
    for host in hosts:
        with settings(host_string = host[0], password = host[1], warn_only = True):
            run(cmd)
@task
def execute_all(cmd):
    '''To run a command on controllers and computers.'''
    execute_controllers(cmd)
    execute_computers(cmd)

def config_ssh():
    '''config ssh free of secret from admin to openstack hosts.'''
    admin_host = get_ceph_admin()
    openstack_hosts = get_control_hosts()+get_compute_hosts()
    with settings(host_string = admin_host[0], password = admin_host[1], warn_only = True):
	run('if [ ! -e /root/.ssh/id_rsa.pub ];then ssh-keygen -f /root/.ssh/id_rsa -t rsa -N \'\';fi')
	get('/root/.ssh/id_rsa.pub', '/tmp/id_rsa.pub')

    for host in openstack_hosts:
        with settings(host_string = host[0], password = host[1], warn_only = True):
            get('/root/.ssh/authorized_keys', '/tmp/authorized_keys')
        local('cat /tmp/id_rsa.pub >> /tmp/authorized_keys')

    for host in openstack_hosts:
        with settings(host_string = host[0], password = host[1], warn_only = False):
	    put('/tmp/authorized_keys', '/root/.ssh/authorized_keys')
    local('rm -f /tmp/id_rsa.pub /tmp/authorized_keys')

def install_ceph():
    '''To install ceph on all openstack nodes'''
    openstack_hosts = get_control_hosts()+get_compute_hosts()
    pkg_name = ""
    for host in openstack_hosts:
        with settings(host_string = host[0], password = host[1], warn_only = False):
	   pardir = os.path.abspath(os.path.join(os.path.dirname('settings.py'),os.path.pardir))
	   release = run('''python -c "from platform import linux_distribution;print linux_distribution()[1].split('.')[0]"''')
	   release = int(release)
	   if release == 6:
	       pkg_name = "ceph-0.94.5-el6.tgz"
	   elif release == 7:
	       pkg_name = "ceph-0.94.5-el7.tgz"
	   filename = str(pardir)+"/packages/"+pkg_name
	   put(filename,'/root')
        with settings(host_string = host[0], password = host[1], warn_only = True):
           cmd = "tar xvzf"+" "+pkg_name
	   run(cmd)
	   run("sh -x setup_ceph.sh")
    
def ceph_check():
    '''To check if ceph is installed.'''
    cmd = "ceph -v"
    hosts = get_control_hosts()+get_compute_hosts()
    for host in hosts:
        with settings(host_string = host[0], password = host[1], warn_only = False):
            output = run(cmd)

def joint_openstack_and_ceph():
    admin_host = env.roledefs['admin'][0]
    admin_password = env.passwords[env.roledefs['admin'][0]]
    admin_path = '/etc/ceph'
    script = '''import ConfigParser
ini = ConfigParser.ConfigParser()
ini.read('ceph.conf')
if not ini.has_section('mon'):
    ini.add_section('mon')
ini.set('mon', 'mon warn on legacy crush tunables', 'false')
ini.set('mon', 'mon pg warn max per osd', '2048')
fp = file('ceph.conf', 'wb')
ini.write(fp)
'''
    ceph_hosts = get_ceph_hosts()
    control_hosts = get_control_hosts()
    compute_hosts = get_compute_hosts()
    openstack_hosts = control_hosts+compute_hosts

    ceph_hosts = copy.deepcopy(ceph_hosts)
    ceph_hosts.extend(control_hosts)
    ceph_hosts.extend(compute_hosts)
    ceph_hosts = list(set(ceph_hosts))
 

    uuid = ''
    with settings(host_string = admin_host, password = admin_password, warn_only = True):
        with cd(admin_path):
            run('ceph osd pool create volumes 128')
            run('ceph osd pool create images 128')
            run('ceph osd pool create vms 128')
            #run('ceph osd pool create backups 128')

            file('temp.py', 'wb').write(script)
            put('temp.py', admin_path)
            run('python %s' % 'temp.py')
            os.remove('temp.py')
            run('rm -rf temp.py')

            for openstack_host in openstack_hosts:
                run('ceph-deploy --overwrite-conf admin %s' % openstack_host[0])

            script = ("ceph auth get-or-create client.cinder mon "
                        "'allow r' osd 'allow class-read object_prefix "
                        "rbd_children, allow rwx pool=volumes, allow rwx pool=vms, "
                        "allow rwx pool=images'")
            run(script)

            script = ("ceph auth get-or-create client.glance mon "
                        "'allow r' osd 'allow class-read object_prefix "
                        "rbd_children, allow rwx pool=images'")
            run(script)
            for control_host in control_hosts:
                run('ceph auth get-or-create client.glance | '
                    'ssh %s tee /etc/ceph/ceph.client.glance.keyring' % control_host[0])

                run('ceph auth get-or-create client.cinder | tee ceph.client.cinder.keyring')
                run('scp ceph.client.cinder.keyring %s:/etc/ceph/' % control_host[0])

                    #run('ceph auth get-or-create client.cinder-backup | '
                    #    'ssh %s tee /etc/ceph/ceph.client.cinder-backup.keyring' % control_host[0])

            for compute_host in compute_hosts:
                run('scp ceph.client.cinder.keyring %s:/etc/ceph/' % compute_host[0])

            uuid = str(run('uuidgen')).strip()
            script = '''cat > secret.xml <<EOF
<secret ephemeral='no' private='no'>
  <uuid>%s</uuid>
  <usage type='ceph'>
    <name>client.cinder secret</name>
  </usage>
</secret>
EOF''' % uuid
            run(script)

            for compute_host in compute_hosts:
                run('ceph auth get-key client.cinder | '
                    'ssh %s tee client.cinder.key' % compute_host[0])
                run('scp secret.xml %s:' % compute_host[0])
                run('ssh %s "virsh secret-define --file secret.xml"' % compute_host[0])

                key = run('ssh %s "cat client.cinder.key"' % compute_host[0])
                key = str(key).strip()
		
		cmd = "virsh secret-set-value --secret "+uuid+" --base64 "+key
                #script = 'ssh %s "virsh secret-set-value --secret %s --base64 %s' % (compute_host[0], uuid, key)
		script = 'ssh %s %s' % (compute_host[0], cmd)
                run(script)
    for control_host in control_hosts:
        with settings(host_string = control_host[0], password = control_host[1]):
            #glance
	    run("cp /etc/glance/glance-api.conf /etc/glance/glance-api.conf.bak")
            run("sed -i '0,/^\[DEFAULT\]/a show_image_direct_url = True' "
                "/etc/glance/glance-api.conf")
            run("sed -i '0,/^\[DEFAULT\]/a rbd_store_chunk_size = 8' "
                "/etc/glance/glance-api.conf")
            run("sed -i '0,/^\[DEFAULT\]/a rbd_store_pool = images' "
                "/etc/glance/glance-api.conf")
            run("sed -i '0,/^\[DEFAULT\]/a rbd_store_user = glance' "
                "/etc/glance/glance-api.conf")
            run("sed -i '0,/^\[DEFAULT\]/a default_store = rbd' "
                "/etc/glance/glance-api.conf")

            #cinder
	    run("cp /etc/cinder/cinder.conf /etc/cinder/cinder.conf.bak")
            run("sed -i '0,/^\[DEFAULT\]/a glance_api_version=2' "
                "/etc/cinder/cinder.conf")
            run("sed -i '0,/^\[DEFAULT\]/a rados_connect_timeout = -1' "
                "/etc/cinder/cinder.conf")
            run("sed -i '0,/^\[DEFAULT\]/a rbd_store_chunk_size = 4' "
                "/etc/cinder/cinder.conf")
            run("sed -i '0,/^\[DEFAULT\]/a rbd_max_clone_depth = 5' "
                "/etc/cinder/cinder.conf")
            run("sed -i '0,/^\[DEFAULT\]/a rbd_flatten_volume_from_snapshot = false' "
                "/etc/cinder/cinder.conf")
            run("sed -i '0,/^\[DEFAULT\]/a rbd_ceph_conf = \/etc\/ceph\/ceph.conf' "
                "/etc/cinder/cinder.conf")
            run("sed -i '0,/^\[DEFAULT\]/a rbd_pool = volumes' "
                "/etc/cinder/cinder.conf")
            run("sed -i '0,/^\[DEFAULT\]/a rbd_user = cinder' "
                "/etc/cinder/cinder.conf")
            run("sed -i '0,/^\[DEFAULT\]/a volume_driver = cinder.volume.drivers.rbd.RBDDriver' "
                "/etc/cinder/cinder.conf")

    #nova
    #self.logger('configure compute-nodes')
    for compute_host in compute_hosts:
        with settings(host_string = compute_host[0], password = compute_host[1]):
	    run("cp /etc/nova/nova.conf /etc/nova/nova.conf.bak")
            run("sed -i '0,/^\[DEFAULT\]/a rbd_secret_uuid = %s' "
                "/etc/nova/nova.conf" % uuid)
            run("sed -i '0,/^\[DEFAULT\]/a rbd_user = cinder' "
                "/etc/nova/nova.conf")
            run("sed -i '0,/^\[DEFAULT\]/a libvirt_images_rbd_ceph_conf = \/etc\/ceph\/ceph.conf' "
                "/etc/nova/nova.conf")
            run("sed -i '0,/^\[DEFAULT\]/a libvirt_images_rbd_pool = vms' "
                "/etc/nova/nova.conf")
            run("sed -i '0,/^\[DEFAULT\]/a libvirt_images_type = rbd' "
                "/etc/nova/nova.conf")
    for compute_host in compute_hosts:
        with settings(host_string = compute_host[0], password = compute_host[1], warn_only = True):
            run('systemctl restart libvirtd')
	    #run('service libvirtd restart')
            run('systemctl restart openstack-nova-compute')
	    #run('service openstack-nova-compute restart')
    for control_host in control_hosts:
        with settings(host_string = control_host[0], password = control_host[1], warn_only = True):
            run('service glance-api restart')
	    run('service glance-registry restart')
            run('service cinder-api restart')
            run('service cinder-volume restart')
            #run('service openstack-cinder-backup restart')

        #self.logger('Successfully provision ceph & openstack')

def get_control_hosts():
    result = []
    hosts = env.roledefs['controllers']
    for host in hosts:
        result.append((host, env.passwords[host]))
    return result

def get_compute_hosts():
    result = []
    hosts = env.roledefs['computers']
    for host in hosts:
        result.append((host, env.passwords[host]))
    return result

def get_ceph_hosts():
    result = []
    hosts = env.roledefs['ceph-nodes']
    for host in hosts:
        result.append((host, env.passwords[host]))
    return result

def get_ceph_admin():
    host = env.roledefs['admin'][0]
    return(host, env.passwords[host])

if __name__ == '__main__':
    config_ssh()
    install_ceph()
    ceph_check()
    joint_openstack_and_ceph()
