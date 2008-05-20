PROJECT_NAME=Licorn
APP_NAME=licorn
DEST?=/opt
PYTHON_LIB_DIR?=$(DEST)/lib/python2.5/site-packages
PROJECT_LIB_DIR?=$(DEST)/lib/$(BINARY_NAME)
LOCALE_DIR?=$(DEST)/share/locale
SHARE_DIR?=$(DEST)/share/licorn
EXECUTABLES=interfaces/cli/add.py interfaces/cli/mod.py interfaces/cli/del.py interfaces/cli/get.py interfaces/cli/chk.py interfaces/gui/keyword-modify-gui.py interfaces/gui/keyword-query-gui.py

all: build doc

install: binary-install installdoc

configure:

build: configure i18n

binary-install: build
	mkdir -p $(DEST) $(PYTHON_LIB_DIR) $(PROJECT_LIB_DIR) $(DEST)/bin $(DEST)/sbin $(SHARE_DIR)
	cp -a interfaces/gui/*.glade $(SHARE_DIR)
	cp -a interfaces daemon core foundations contrib __init__.py $(PROJECT_LIB_DIR)
	( \
		for executable in $EXECUTABLES; do \
		ln -sf ../$(PROJECT_LIB_DIR)/$$executable \
			$(DEST)/bin/`basename $$executable | sed -e "s%\.py%%g"`; \
		done \
	)
	( cd $(DEST)/sbin; ln -sf ../$(PROJECT_LIB_DIR)/daemon/main.py licornd )
	#mkdir -p $(LOCALE_DIR)
	#find src/po -mindepth 1 -maxdepth 1 -type d -exec cp -a "{}" $(LOCALE_DIR) \;
	
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
			msgfmt locale/$${lang}.po -o locale/$${lang}.mo ; \
		done ;

update-pot:
	rm locale/$(APP_NAME).pot ; cp locale/$(APP_NAME).template.pot locale/$(APP_NAME).pot
	find . -type f \( -name '*.py' -or -name '*.glade' \) | grep -v '_darcs' | xargs xgettext -k_ -kN_ -j -o locale/$(APP_NAME).pot 

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
