PROJECT_NAME=Licorn
APP_NAME=licorn
DESTDIR?=/opt
CONF_DIR?=$(DESTDIR)/etc/$(APP_NAME)
PREFIX?=$(DESTDIR)
PROJECT_LIB_DIR?=$(DESTDIR)/usr/share/pyshared/$(APP_NAME)
LOCALE_DIR?=$(DESTDIR)/usr/share/locale
DOC_DIR?=$(DESTDIR)/usr/share/doc
SHARE_DIR?=$(DESTDIR)/usr/share/$(APP_NAME)
CACHE_DIR?=$(DESTDIR)/var/cache/$(APP_NAME)
EXECUTABLES=interfaces/cli/add.py interfaces/cli/mod.py interfaces/cli/del.py interfaces/cli/get.py interfaces/cli/chk.py interfaces/gui/keyword-modify-gui.py interfaces/gui/keyword-query-gui.py
APT_INSTALL=sudo apt-get --yes --force-yes --quiet install
PIP_INSTALL=sudo pip install

boottest:
	@echo "development directory is: $(DEVEL_DIR) (should not be empty)"

all: build doc

install: binary-install installdoc

configure:

build: configure i18n

.ONESHELL:
darcs_record_prehook:
	@sed -ie "s/\(@DEVEL@\|dev+r[0-9]*\)/dev+r`expr 1 + $$(darcs changes --count)`/" version.py

binary-install: build
	mkdir -p "$(DESTDIR)" "$(PROJECT_LIB_DIR)" "$(DESTDIR)"/usr/bin "$(DESTDIR)"/usr/sbin "$(SHARE_DIR)" "$(CONF_DIR)" "$(LOCALE_DIR)" "$(CACHE_DIR)"
	cp -a config/* "$(CONF_DIR)"
	cp -a interfaces/gui/*.glade "$(SHARE_DIR)"
	cp -a interfaces daemon core extensions foundations upgrades contrib __init__.py version.py "$(PROJECT_LIB_DIR)"
	find locale -mindepth 1 -maxdepth 1 -type d -exec cp -a "{}" $(LOCALE_DIR) \;
	ln -sf ../"$(PROJECT_LIB_DIR)"/interfaces/wmi "$(SHARE_DIR)"/wmi
	ln -sf ../"$(PROJECT_LIB_DIR)"/core/backends/schemas "$(SHARE_DIR)"/schemas
	chown -R root: "$(CONF_DIR)" "$(SHARE_DIR)" "$(LOCALE_DIR)" "$(PROJECT_LIB_DIR)"
	find "$(DESTDIR)" -type d -exec chmod 755 "{}" \;
	find "$(DESTDIR)" -type f -exec chmod 644 "{}" \;
	chmod a+x "$(PROJECT_LIB_DIR)"/daemon/main.py
	chmod a+x "$(PROJECT_LIB_DIR)"/interfaces/cli/???.py

uninstall:
	@rm -f "$(DESTDIR)"/usr/bin/{add,mod,del,get,chk}
	@rm -f "$(DESTDIR)"/usr/sbin/licornd*
	@rm -rf "$(SHARE_DIR)" "$(CACHE_DIR)" "$(PROJECT_LIB_DIR)" "$(CONF_DIR)"

# In developer install, the first 'make lang' will fail because Django
# is not yet installed. But this will go far enough to compile the PO
# files for the daemon to start, and then install the other required packages
# for the second call to 'make lang' to succeed.
devinstall_packages:
	#
	# REMINDER: this process involves SUDO,
	#	you should be able to invoke it to continue.
	#
	@make lang >/dev/null 2>&1 || true
	@sudo python contrib/dev_install.py --install-all-packages


# we must call a pre_devinstall target, else the $(shell) will fail unless
# packages are already installed. This is a `make` behaviour workaround, to
# circumvent the $(shell) beiing called before running all the commands.
devinstall: devinstall_packages perms
	@sudo python contrib/dev_install.py --make-symlinks DEVEL_DIR=$(shell python -m foundations/bootstrap)
	@sudo python contrib/dev_install.py
	@python contrib/dev_install.py --user-post-installation
	@make lang  >/dev/null 2>&1
	#
	# You can play now :-)
	#

devuninstall: uninstall

doc:
	(cd docs; make html)

installdoc: doc
	mkdir -p "$(DOC_DIR)"
	cp -a docs/_build/html "$(DOC_DIR)"

perms: localperms

permissions: localperms

localperms:
	@chmod 755 $(EXECUTABLES) daemon/main.py tests/*.py

docsync: doc
	( cd docs; rsync -av --delete _build/html/ \
			dev.licorn.org:/home/groups/darcs-Licorn/docs/_build/html )

clean: cleandoc cleanlang
	find ./ -type f \( -name '*~' -o -name '.*.swp' \
		-o -name '*.pyc' -o -name '*.pyo' \) -exec rm "{}" \;
	[ -d src/po/fr ] && rm -r src/po/fr || true

cleanlang:
	# remove compiled message files
	rm -f locale/*.mo
	# remove lang directories
	for lang in fr ; \
		do \
			rm -rf locale/$${lang}; \
		done

lang: i18n

i18n: update-po
	for lang in fr ; \
		do \
			mkdir -p locale/$${lang}/LC_MESSAGES; \
			msgfmt locale/$${lang}.po -o locale/$${lang}.mo ; \
			cp locale/$${lang}.mo locale/$${lang}/LC_MESSAGES/$(APP_NAME).mo ; \
			(cd interfaces/wmi ; django-admin compilemessages -l $${lang} || django-admin.py compilemessages -l $${lang}) ; \
		done ;

update-pot:
	cp locale/$(APP_NAME).template.pot locale/$(APP_NAME).pot
	find . -type f \( -name '*.py' -or -name '*.glade' \) \
		| grep -vE '(_darcs|interfaces/wmi)' \
		| xargs xgettext -k_ -kN_ -j -o locale/$(APP_NAME).pot

update-po: update-pot
	# We insert django-admin.py in case Django was installed via PIP.
	for lang in fr ; \
		do \
			msgmerge -U locale/$${lang}.po locale/$(APP_NAME).pot ; \
			touch locale/$${lang}.js.po ; \
			( \
				cd interfaces/wmi ; \
				django-admin makemessages -d django -l $${lang} || django-admin.py makemessages -d django -l $${lang} ; \
				django-admin makemessages -d djangojs -l $${lang} || django-admin.py makemessages -d djangojs -l $${lang} \
			) ; \
		done ;

cleandoc:
	(cd docs && make clean)

.PHONY: all clean install build configure binary-install doc installdoc cleandoc devinstall
