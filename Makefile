PROJECT_NAME=Licorn
APP_NAME=licorn
DESTDIR?=/opt
CONFDIR?=$(DESTDIR)/etc/$(APP_NAME)
PREFIX?=$(DESTDIR)
PROJECT_LIB_DIR?=$(DESTDIR)/usr/share/pyshared/$(APP_NAME)
EXEC_LINK_DIR?=../../usr/share/pyshared/$(APP_NAME)
LOCALE_DIR?=$(DESTDIR)/usr/share/locale
DOC_DIR?=$(DESTDIR)/usr/share/doc
SHARE_DIR?=$(DESTDIR)/usr/share/$(APP_NAME)
EXECUTABLES=interfaces/cli/add.py interfaces/cli/mod.py interfaces/cli/del.py interfaces/cli/get.py interfaces/cli/chk.py interfaces/gui/keyword-modify-gui.py interfaces/gui/keyword-query-gui.py

all: build doc

install: binary-install installdoc

configure:

build: configure i18n
	chmod a+x $(EXECUTABLES)
	chmod a+x daemon/main.py
	chmod a+x tests/core.py tests/wmi.py

binary-install: build
	mkdir -p "$(DESTDIR)" "$(PROJECT_LIB_DIR)" "$(DESTDIR)"/usr/bin "$(DESTDIR)"/usr/sbin "$(SHARE_DIR)" "$(CONFDIR)"
	cp -a config/* "$(CONFDIR)"
	cp -a interfaces/gui/*.glade "$(SHARE_DIR)"
	cp -a interfaces daemon core extensions foundations contrib __init__.py "$(PROJECT_LIB_DIR)"
	( \
		for executable in $(EXECUTABLES); do \
		ln -sf "$(EXEC_LINK_DIR)"/$$executable \
			"$(DESTDIR)"/usr/bin/`basename $$executable | sed -e "s%\.py%%g"`; \
		done \
	)
	( cd "$(DESTDIR)"/usr/sbin; ln -sf "$(EXEC_LINK_DIR)"/daemon/main.py licornd )
	mkdir -p "$(LOCALE_DIR)"
	cp -a locale/* "$(LOCALE_DIR)"
	#find src/po -mindepth 1 -maxdepth 1 -type d -exec cp -a "{}" "$(LOCALE_DIR)" \;
	ln -sf ../"$(EXEC_LINK_DIR)"/interfaces/wmi "$(SHARE_DIR)"/wmi
	ln -sf ../"$(EXEC_LINK_DIR)"/core/backends/schemas "$(SHARE_DIR)"/schemas

doc:
	(cd docs; make html)

installdoc: doc
	mkdir -p "$(DOC_DIR)"
	cp -a docs/_build/html "$(DOC_DIR)"

clean: cleandoc cleanlang
	find ./ -type f \( -name '*~' -o -name '.*.swp' \
		-o -name '*.pyc' -o -name '*.pyo' \) -exec rm "{}" \;
	[ -d src/po/fr ] && rm -r src/po/fr || true

cleanlang:
	rm -f locale/*.mo
	for lang in fr ; \
			do \
				rm -rf locale/$${lang}; \
			done

lang: i18n

i18n: update-po
	for lang in fr ; \
		do \
			mkdir -p locale/$${lang}/LC_MESSAGES; ln -sf ../../$${lang}.mo locale/$${lang}/LC_MESSAGES/$(APP_NAME).mo ; \
			msgfmt locale/$${lang}.po -o locale/$${lang}.mo ; \
		done ;

update-pot:
	rm locale/$(APP_NAME).pot ; cp locale/$(APP_NAME).template.pot locale/$(APP_NAME).pot
	find . -type f \( -name '*.py' -or -name '*.glade' \) | grep -v '_darcs' | xargs xgettext -k_ -kN_ -j -o locale/$(APP_NAME).pot 

update-po: update-pot
	for lang in fr ; \
		do \
			msgmerge -U locale/$${lang}.po locale/$(APP_NAME).pot ; \
		done ;

cleandoc:
	(cd docs && make clean)

.PHONY: all clean install build configure binary-install doc installdoc cleandoc
