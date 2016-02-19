Name:		fabric-joint
Version:	%{version}
Release:	%{?revision}
Summary:	join ceph to openstack

Group:		Application/File
License:	GPL
URL:		https://github.com/CertusZhangzhy/joint
Source0:	%{name}_%{version}.tar.gz

#BuildRequires:	
#Requires:	

%description


%prep
#%setup -q


%install
echo "install"
mkdir -p %{buildroot}
cd %{buildroot}
mkdir -p ./opt/fabric-joint
cd opt/fabric-joint
tar xfz %{tarname}

%clean
echo "clean"
[ "$RPM_BUILD_ROOT" != "/" ] && rm -rf "$RPM_BUILD_ROOT"

%files
/opt/fabric-joint



%changelog

