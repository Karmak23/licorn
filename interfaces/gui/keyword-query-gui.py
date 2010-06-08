#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
SearchWindow

Copyright (C) 2007 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.
"""

import os, signal, gtk, pango, gobject, gnomevfs, gnome.ui
from time import localtime, strftime

from licorn.foundations import logging, exceptions, options
from licorn.core        import configuration, keywords
from licorn.harvester   import HarvestClient, LCN_MSG_STATUS_PARTIAL
from licorn.gui.gtkkwd  import LicornKeywordsGtkWindow

class LicornKeywordsQueryWindow(LicornKeywordsGtkWindow):
	""" GUI for querying files with Licorn keyword system."""
	default_application = "gedit"
	
	def __init__(self):				
		""" Create all widgets."""

		LicornKeywordsGtkWindow.__init__(self, 'query')

		LicornKeywordsGtkWindow.connect_checkboxes(self, self.__keyword_clicked)
		self.treeview.set_search_equal_func(self.__treeview_search_func)

		self.treeview.connect('row-activated', self.__treeview_row_activated)

		self.window.show_all()

		#gobject.timeout_add(1000, self.Status)
	def __treeview_row_activated(self, view, path, col):
		""" Launch application when user click on a file in the treeview."""
		#path = self.liststore.get_value(self.liststore.get_iter(store_path), 0)
		filename    = self.liststore[path][1] + '/' + self.liststore[path][0]
		application = gnomevfs.mime_get_default_application(self.get_mime_type(filename)) 
		if application is None:
			application = self.default_application
		else:
			application = application[2]

		if os.fork() == 0:
			os.execvp(application, [ application, filename ])
	def __treeview_search_func(self, model, column, key, iter):
		try: value = self.liststore[iter][0]
		except AttributeError: return True
		else:
			key = key.decode('utf-8')
			return not (value.startswith(key) or value.lower().startswith(key))
	def update_listmodel(self, paths):

		self.liststore.clear()

		for path in paths:
			dirname, basename = path.rsplit('/', 1)
			info              = gnomevfs.get_file_info(path, gnomevfs.FILE_INFO_GET_MIME_TYPE)
			uri_str           = gnomevfs.get_uri_from_local_path(path)
			icon, flags       = gnome.ui.icon_lookup(self.iconTheme,
									self.iconFactory, uri_str, '',
									gnome.ui.ICON_LOOKUP_FLAGS_NONE, info.mime_type, info)

			self.liststore.append((basename, dirname, info.size, info.mtime, icon))
	def clear_checkboxes(self, widget):
		LicornKeywordsGtkWindow.clear_checkboxes(self, widget)
		self.__keyword_clicked(None)
	def __keyword_clicked(self, checkbox):
		""" When a keyword checkbox is clicked """

		if self.clearing: return

		self.window.set_sensitive(False)

		try:
			(status, nrf, paths) = self.hc.KeywordQueryRequest(self.selected_keywords_list())
			if nrf > 1: results = 's'
			else:      results = ''
	
			self.update_listmodel(paths)

			if status == LCN_MSG_STATUS_PARTIAL:
				message = 'Query returned %d result%s but could be incomplete (server is still harvesting data).' % (nrf, results)
			else:
				message = 'Query returned %d result%s.' % (nrf, results)

			self.StatusMessage(message)
			
		except exceptions.LicornHarvestException, e:
			self.StatusMessage(str(e))
		except exceptions.LicornHarvestError, e:
			self.StatusMessage(str(e))

		self.window.set_sensitive(True)
		self.treeview.grab_focus()

if __name__ == "__main__":
	options.SetVerbose(2)
	LicornKeywordsQueryWindow()
	gtk.main()
