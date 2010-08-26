PROJECT_NAME=Licorn
APP_NAME=licorn
DESTDIR?=/opt
PREFIX?=$(DESTDIR)
PROJECT_LIB_DIR?=$(DESTDIR)/usr/share/pyshared/$(APP_NAME)
EXEC_LINK_DIR?=../../usr/share/pyshared/$(APP_NAME)
LOCALE_DIR?=$(DESTDIR)/usr/share/locale
SHARE_DIR?=$(DESTDIR)/usr/share/$(APP_NAME)
EXECUTABLES=interfaces/cli/add.py interfaces/cli/mod.py interfaces/cli/del.py interfaces/cli/get.py interfaces/cli/chk.py interfaces/gui/keyword-modify-gui.py interfaces/gui/keyword-query-gui.py

all: build doc

install: binary-install installdoc

configure:

build: configure i18n
	chmod a+x $(EXECUTABLES)
	chmod a+x daemon/main.py

binary-install: build
	mkdir -p $(DESTDIR) $(PROJECT_LIB_DIR) $(DESTDIR)/usr/bin $(DESTDIR)/usr/sbin $(SHARE_DIR)
	cp -a interfaces/gui/*.glade $(SHARE_DIR)
	cp -a interfaces daemon core foundations contrib __init__.py $(PROJECT_LIB_DIR)
	( \
		for executable in $(EXECUTABLES); do \
		ln -sf $(EXEC_LINK_DIR)/$$executable \
			$(DESTDIR)/usr/bin/`basename $$executable | sed -e "s%\.py%%g"`; \
		done \
	)
	( cd $(DESTDIR)/usr/sbin; ln -sf $(EXEC_LINK_DIR)/daemon/main.py licornd )
	mkdir -p $(LOCALE_DIR)
	cp -a locale/* $(LOCALE_DIR)
	#find src/po -mindepth 1 -maxdepth 1 -type d -exec cp -a "{}" $(LOCALE_DIR) \;
	ln -sf ../$(EXEC_LINK_DIR)/interfaces/wmi $(SHARE_DIR)/wmi

doc: 

installdoc: doc
	
clean: cleandoc
	find ./ -type f \( -name '*~' -o -name '.*.swp' \
		-o -name '*.pyc' -o -name '*.pyo' \) -exec rm "{}" \;
	[ -d src/po/fr ] && rm -r src/po/fr || true

lang: i18n

i18n: update-po
	for lang in fr ; \
		do \
			rm -rf locale/$${lang}; mkdir -p locale/$${lang}/LC_MESSAGES; ln -sf ../../$${lang}.mo locale/$${lang}/LC_MESSAGES/$(APP_NAME).mo ; \
			msgfmt locale/$${lang}.po -o locale/$${lang}.mo >/dev/null 2>&1; \
		done ;

update-pot:
	rm locale/$(APP_NAME).pot ; cp locale/$(APP_NAME).template.pot locale/$(APP_NAME).pot
	find . -type f \( -name '*.py' -or -name '*.glade' \) | grep -v '_darcs' | xargs xgettext -k_ -kN_ -j -o locale/$(APP_NAME).pot >/dev/null 2>&1

update-po: update-pot
	#
	# WARNING: don't do this, this will overwrite changes in the .po.
	# this will be handled manually by poedit.
	#
	#for lang in fr ; \
	#	do \
	#		msgmerge -U locale/$${lang}/LC_MESSAGES/$(APP_NAME).po locale/$(APP_NAME).pot ; \
	#	done ;

cleandoc:

.PHONY: all clean install build configure binary-install doc installdoc cleandoc
