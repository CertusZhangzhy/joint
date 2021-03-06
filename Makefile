SHELL=bash
SRC := $(shell pwd)
VERSION ?= 1.0.0
REVISION ?= 0
TGZ = build.tar.gz
SPEC = joint.spec
BUILD_PRODUCT_TGZ=$(SRC)/$(TGZ)

RPM_REVISION ?= 0
RPMBUILD=$(SRC)/../rpmbuild

rpm:
	mkdir -p $(RPMBUILD)/{SPECS,RPMS,BUILDROOT}
	rm -f $(TGZ)
	tar cvzf $(TGZ) __init__.py  joint.py README.md  testbed
	cp $(SPEC) $(RPMBUILD)/SPECS
	( \
        cd $(RPMBUILD); \
        rpmbuild -bb --define "_topdir $(RPMBUILD)" --define "version $(VERSION)" --define "revision $(RPM_REVISION)" --define "tarname $(BUILD_PRODUCT_TGZ)" SPECS/${SPEC}; \
        )
	rm -f $(TGZ)
