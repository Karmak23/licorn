#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
"""
SetKeywordsWindow

Copyright (C) 2007 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.
"""

import gtk, gnomevfs
import sys, os.path, stat

from licorn.foundations import logging
from licorn.core        import keywords
from licorn.gui.gtkkwd  import LicornKeywordsGtkWindow

class LicornModifyKeywordsWindow(LicornKeywordsGtkWindow):
	""" GUI for files and directories keywords managing. """
	def __init__(self, args = []):

		LicornKeywordsGtkWindow.__init__(self, 'modify')
		self.TARGET_TYPE_TEXT = 80

		drag_dest = self.gui.get_widget('modify_paths_frame')
		drag_dest.drag_dest_set(
			gtk.DEST_DEFAULT_ALL,
			[ ("text/plain", 0, self.TARGET_TYPE_TEXT ) ],
			gtk.gdk.ACTION_COPY)
		drag_dest.connect("drag_data_received", self.receive_dnd)

		self.recursive = self.gui.get_widget('modify_recursive_chkbtn')
		self.recursive.connect('clicked', self.recursive_clicked)

		LicornKeywordsGtkWindow.connect_checkboxes(self, self.__keyword_clicked)

		self.keyword_usage = {}
		# just to be able to read the tests more easily.
		self.unknown      = -1
		self.unchecked    = 0
		self.checked      = 1
		self.inconsistent = 2

		self.kframe = self.gui.get_widget('modify_keywords_frame')

		self.empty = self.gui.get_widget('modify_empty_button')
		self.empty.connect('clicked', self.empty_clicked)

		self.treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
		self.treeview.connect('key-press-event', self.__treeview_key_pressed)

		self.window.show_all()

		# add paths given on the command line.
		map(lambda x: self.liststore.append((x,)), args)

		self.update_keyword_usage()
		self.update_notebook()
	def __treeview_key_pressed(self,  widget, event):
		if (event.keyval, event.state) == gtk.accelerator_parse("Delete"):
			self.__treeview_remove(None)
			return True
		return False
	def __treeview_remove(self, item):
		model, paths = self.treeview.get_selection().get_selected_rows()
		if model:
			map(self.liststore.remove, map(self.liststore.get_iter, paths))
			self.update_keyword_usage()
			self.update_notebook()

	def __keyword_clicked(self, checkbox):
		""" When a keyword checkbox is clicked """

		if self.clearing: return

		self.StatusMessage("Applying keywords, please wait…")
		self.window.set_sensitive(False)

		if checkbox.get_inconsistent():
			# add keywords to all files at first click.
			checkbox.set_inconsistent(False)
			checkbox.set_active(True)

		kw  = checkbox.get_label()
		rec = self.recursive.get_active()

		logging.progress('__keyword_clicked(%s) called.' % kw)

		if checkbox.get_active():
			func    = self.kw.AddKeywordsToPath
			message = "Added keyword %s to %s."
			status  = self.checked
		else:
			func    = self.kw.DeleteKeywordsFromPath
			message = "Removed keyword %s from %s."
			status  = self.unchecked

		for (path, ) in self.liststore:
			try:
				func(path, [ kw ], rec)
				self.keyword_usage[kw] = status
				logging.progress(message % (kw, path))
				self.hc.UpdateRequest(path)

			except (OSError, IOError), e:
				if e.errno not in (61, 95):
					# TODO: refactor messagebox.
					msgbox = gtk.MessageDialog(parent=self.window, type=gtk.MESSAGE_ERROR,
						buttons=gtk.BUTTONS_CLOSE, message_format=str(e))
					msgbox.set_modal(True)
					msgbox.show()

		self.window.set_sensitive(True)
		self.StatusMessage("Done applying keywords.")
	def empty_clicked(self, widget):
		""" When empty liststore is clicked. """

		self.liststore.clear()
		self.update_keyword_usage()
		self.update_notebook()
	def recursive_clicked(self, checkbox):
		""" When recursive option checkbox is clicked. """

		logging.progress('recursive_clicked() called.')

		self.update_keyword_usage()
		self.update_notebook()
	def update_keyword_usage(self):
		""" TODO """

		logging.progress('update_keyword_usage() called.')

		self.StatusMessage("Updating keywords notebook, please wait…")
		self.window.set_sensitive(False)

		# restart with nothing (all unknown)
		for kw in self.kw.keywords.keys():
			self.keyword_usage[kw] = self.unknown

		for (path, ) in self.liststore:

			if os.path.isfile(path):
				file_keywords = []
				try:
					file_keywords = self.kw.GetKeywordsFromPath(path)
					assert logging.debug('file has keywords: %s.' % str(file_keywords))
				except (OSError, IOError), e:
					if e.errno != 61: raise e

				for kw in self.keyword_usage.keys():
					if kw in file_keywords:
						if self.keyword_usage[kw] == self.unknown:
							self.keyword_usage[kw] = self.checked
						elif self.keyword_usage[kw] != self.checked:
							self.keyword_usage[kw] = self.inconsistent
					else:
						if self.keyword_usage[kw] == self.unknown:
							self.keyword_usage[kw] = self.unchecked
						elif self.keyword_usage[kw] != self.unchecked:
							self.keyword_usage[kw] = self.inconsistent

			elif os.path.isdir(path):
				keyword_usage_dir = self.get_keyword_usage_in_dir(path)

				kuk = keyword_usage_dir.keys()
				for kw in self.keyword_usage.keys():
					if kw in kuk:
						if self.keyword_usage[kw] == self.unknown:
							self.keyword_usage[kw] = keyword_usage_dir[kw]
						elif self.keyword_usage[kw] != keyword_usage_dir[kw]:
							self.keyword_usage[kw] = self.inconsistent
					else:
						if self.keyword_usage[kw] == self.unknown:
							self.keyword_usage[kw] = self.unchecked
						elif self.keyword_usage[kw] != self.unchecked:
							self.keyword_usage[kw] = self.inconsistent

		assert logging.debug('kwusage after update: %s.' % str(self.keyword_usage))

		self.window.set_sensitive(True)
		self.StatusMessage("Done updating keywords notebook.")
	def update_notebook(self):
		""" TODO. """

		logging.progress('update_notebook() called.')

		if len(self.liststore):
			self.kframe.set_sensitive(True)
		else:
			self.kframe.set_sensitive(False)
			return

		def update_checkbox(obj):
			if type(obj) == gtk.CheckButton:
				label = obj.get_label()

				if self.keyword_usage[label] == self.checked:
					obj.set_inconsistent(False)
					obj.set_active(True)
				elif self.keyword_usage[label] == self.unchecked:
					obj.set_inconsistent(False)
					obj.set_active(False)
				else:
					obj.set_active(False)
					obj.set_inconsistent(True)

			elif type(obj) in (gtk.Box, gtk.VBox, gtk.HBox): obj.foreach(update_checkbox)

		self.clearing = True

		for i in range(0, self.notebook.get_n_pages()):
			self.notebook.get_nth_page(i).foreach(update_checkbox)

		self.clearing = False
	def get_keyword_usage_in_dir(self, path):
		""" Look the keywords in subfiles of path.
			A keyword which is present in all files will be checked (visualy),
			and a keyword which is present in only some files will be
			inconsistent (visualy).
		"""
		keyword_usage = {}
		keyword_usage['@fc@'] = 0

		def count_keywords(file_path):
			keyword_usage['@fc@'] += 1
			try:
				for kw in self.kw.GetKeywordsFromPath(file_path):
					if kw in keyword_usage.keys():
						keyword_usage[kw] += 1
					else:
						keyword_usage[kw] = 1
			except (OSError, IOError), e: pass

		if self.recursive.get_active(): max = 99
		else:                           max = 1

		map( lambda x: count_keywords(x),
			fsapi.minifind(path, maxdepth=max, itype=stat.S_IFREG))

		assert logging.debug('Dir %s, %d files, kwu: %s.' % (styles.stylize(styles.ST_PATH, path), keyword_usage['@fc@'], keyword_usage))

		# look if each keyword is on all file or on only some files
		kuk = keyword_usage.keys()
		for kw in self.kw.keywords.keys():
			if kw in kuk:
				if keyword_usage[kw] == keyword_usage['@fc@']:
					keyword_usage[kw] = self.checked
				else:
					keyword_usage[kw] = self.inconsistent
			else:
				keyword_usage[kw] = self.unchecked

		assert logging.debug('Dir %s, %d files, final kwu: %s.' % (styles.stylize(styles.ST_PATH, path), keyword_usage['@fc@'], keyword_usage))

		return keyword_usage
	def receive_dnd (self, widget, context, x, y, selection, targetType, time):
		""" TODO """
		if targetType == self.TARGET_TYPE_TEXT:
			# the DND data are separated by the MS-DOS newline…
			files = selection.data.split('\r\n')
			for file in files:
				# and the split() gives an empty last argument, we must test «file»…
				if file:
					path = gnomevfs.get_local_path_from_uri(file)
					logging.progress("Received %s by DND." % styles.stylize(styles.ST_PATH, path))

					if os.path.exists(path):
						if os.path.isdir(path) or os.path.isfile(path):
							if path not in [ p for (p, ) in self.liststore ]:
								self.liststore.append((path,))
						else:
							StatusMessage('''Sorry, can't apply keywords on %s, refusing it.''' % path)

			self.update_keyword_usage()
			self.update_notebook()

if __name__ == "__main__":
	options.SetVerbose(2)
	LicornModifyKeywordsWindow(sys.argv[1:])
	gtk.main()
