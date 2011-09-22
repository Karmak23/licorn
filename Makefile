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

.ONESHELL:
darcs_record_prehook:
	@sed -ie "s/\(@DEVEL@\|dev+r[0-9]*\)/dev+r`expr 1 + $$(darcs changes --count)`/" version.py

localperms:
	@chmod 755 $(EXECUTABLES) daemon/main.py

binary-install: build
	mkdir -p "$(DESTDIR)" "$(PROJECT_LIB_DIR)" "$(DESTDIR)"/usr/bin "$(DESTDIR)"/usr/sbin "$(SHARE_DIR)" "$(CONFDIR)" "$(LOCALE_DIR)"
	cp -a config/* "$(CONFDIR)"
	cp -a interfaces/gui/*.glade "$(SHARE_DIR)"
	cp -a interfaces daemon core extensions foundations contrib __init__.py "$(PROJECT_LIB_DIR)"
	find locale -mindepth 1 -maxdepth 1 -type d -exec cp -a "{}" $(LOCALE_DIR) \;
	ln -sf ../"$(EXEC_LINK_DIR)"/interfaces/wmi "$(SHARE_DIR)"/wmi
	ln -sf ../"$(EXEC_LINK_DIR)"/core/backends/schemas "$(SHARE_DIR)"/schemas
	chown -R root: "$(CONFDIR)" "$(SHARE_DIR)" "$(LOCALE_DIR)" "$(PROJECT_LIB_DIR)"
	find "$(DESTDIR)" -type d -exec chmod 755 "{}" \;
	find "$(DESTDIR)" -type f -exec chmod 644 "{}" \;
	( \
		for executable in $(EXECUTABLES); do \
			ln -sf "$(EXEC_LINK_DIR)"/$$executable \
				"$(DESTDIR)"/usr/bin/`basename $$executable | sed -e "s%\.py%%g"`; \
			chmod 755 "$(PROJECT_LIB_DIR)"/$$executable ; \
		done \
	)
	( cd "$(DESTDIR)"/usr/sbin; ln -sf "$(EXEC_LINK_DIR)"/daemon/main.py licornd )
	chmod a+x "$(PROJECT_LIB_DIR)"/daemon/main.py

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
	# remove compiled message files
	rm -f locale/*.mo
	# remove lang directories
	for lang in fr ; \
		do \
			rm -rf locale/$${lang}; \
		done

lang: i18n

# the .js.MO links are necessary for the gettext2json to work as expected.
i18n: update-po
	mkdir -p interfaces/wmi/js/json
	for lang in fr ; \
		do \
			mkdir -p locale/$${lang}/LC_MESSAGES; \
			msgfmt locale/$${lang}.po -o locale/$${lang}.mo ; \
			msgfmt locale/$${lang}.js.po -o locale/$${lang}.js.mo ; \
			cp locale/$${lang}.mo locale/$${lang}/LC_MESSAGES/$(APP_NAME).mo ; \
			cp locale/$${lang}.js.mo locale/$${lang}/LC_MESSAGES/$(APP_NAME).js.mo ; \
			python locale/gettext2json.py $(APP_NAME).js ./locale $${lang} \
				> interfaces/wmi/js/json/$(APP_NAME).$${lang}.json ; \
		done ;

update-pot:
	rm -f locale/$(APP_NAME).pot locale/$(APP_NAME)js.pot
	cp locale/$(APP_NAME).template.pot locale/$(APP_NAME).pot
	cp locale/$(APP_NAME)js.template.pot locale/$(APP_NAME)js.pot
	find . -type f \( -name '*.py' -or -name '*.glade' \) | grep -v '_darcs' \
		| xargs xgettext -k_ -kN_ -j -o locale/$(APP_NAME).pot
	find interfaces/wmi -type f \( -name '*.js' \) \
		| xargs xgettext -k_ -kN_ -j -o locale/$(APP_NAME)js.pot

update-po: update-pot
	for lang in fr ; \
		do \
			msgmerge -U locale/$${lang}.po locale/$(APP_NAME).pot ; \
			touch locale/$${lang}.js.po ; \
			msgmerge -U locale/$${lang}.js.po locale/$(APP_NAME)js.pot ; \
		done ;

cleandoc:
	(cd docs && make clean)

.PHONY: all clean install build configure binary-install doc installdoc cleandoc
