# -*- coding: utf-8 -*-
"""
SearchWindow

Copyright (C) 2007 Olivier Cortès <olive@deep-ocean.net>,
Partial Copyright (C) 2007 Régis Cobrun <reg53fr@yahoo.fr>
Licensed under the terms of the GNU GPL version 2.
"""

import signal, gtk, gtk.glade, pango, gnomevfs, gnome.ui
from time import localtime, strftime

from licorn.foundations import exceptions, hlstr
from licorn.core        import configuration, keywords
from licorn.harvester   import HarvestClient, LCN_MSG_STATUS_PARTIAL

class LicornKeywordsGtkWindow:
	""" base GUI for keywords operations. """

	def __init__(self, gui_name):
		""" Create all widgets."""

		# import keywords from current system.
		self.kw = keywords.KeywordsController(configuration)
		self.hc = HarvestClient()

		self.gui_name = gui_name
		# get some widgets from GLAde file
		self.gui        = gtk.glade.XML("%s/hkew.glade" % configuration.share_data_dir)
		self.window     = self.gui.get_widget('%s_window' % self.gui_name)

		self.statusbar  = self.gui.get_widget("%s_statusbar" % self.gui_name)
		self.clearbut   = self.gui.get_widget('%s_clear_button' % self.gui_name)

		self.sellabel   = self.gui.get_widget('%s_cursel_value_label' % self.gui_name)
		# used to avoid a bunch of requests to the server when clearing all checkboxes.
		self.clearing   = False

		self.context_id = self.statusbar.get_context_id("Toto est content.")
		self.message_id = None

		signal.signal(signal.SIGQUIT, self.destroy_event)
		signal.signal(signal.SIGINT, self.destroy_event)
		signal.signal(signal.SIGTERM, self.destroy_event)
		signal.signal(signal.SIGHUP, self.destroy_event)

		self.window.connect("delete_event",  self.destroy_event)
		self.window.connect("destroy_event", self.destroy_event)
		self.window.connect("destroy",       self.destroy_event)
		self.clearbut.connect("clicked",     self.clear_checkboxes)

		if self.gui_name == 'query':
			self.geometry_hints = [500, 800]
		else:
			self.geometry_hints = [400, 650]
		self.window.resize(self.geometry_hints[0], self.geometry_hints[1])

		self.__init_notebook()
		self.__init_treeview()

		self.iconTheme   = gtk.icon_theme_get_default()
		self.iconFactory = gnome.ui.ThumbnailFactory(gnome.ui.THUMBNAIL_SIZE_NORMAL)

	def __init_notebook(self):
		""" Build notebook's pages with keywords: one page per parent and children are the content."""

		self.notebook = self.gui.get_widget("%s_notebook" % self.gui_name)

		notebook_page = None
		k_nrc         = {}

		for k in self.kw.keywords:
			k_nrc[k] = len(self.kw.Children(k))
			if k_nrc[k] == 0:
				del k_nrc[k]

		min_nrc = min(k_nrc.values())

		for k in self.kw.keywords:
			kw_children = self.kw.Children(k)
			if kw_children != []:
				notebook_page = gtk.VBox()
				notebook_page.set_border_width(5)
				notebook_page.set_spacing(5)

				if self.kw.keywords[k]['description'] != "":
					descr_label = gtk.Label(self.kw.keywords[k]['description'])
					descr_label.set_ellipsize(pango.ELLIPSIZE_START)
					notebook_page.add(descr_label)

				if len(kw_children) > min_nrc:
					horiz_page = gtk.HBox()
					horiz_page.set_spacing(5)

					cnt = 0
					page = gtk.VBox()
					page.set_spacing(5)
					left_to_add = False
					for kw_child in kw_children:
						if cnt == min_nrc:
							horiz_page.add(page)
							page = gtk.VBox()
							page.set_spacing(5)
							cnt = 0
							left_to_add = False
						description = self.kw.keywords[kw_child]['description']
						if description != "": description = " (%s)" % description
						chkbox = gtk.CheckButton('%s%s' % (kw_child, description))
						page.pack_start(chkbox, False)
						cnt += 1
						left_to_add = True
					if left_to_add:
						horiz_page.add(page)

					notebook_page.add(horiz_page)

				else:
					for kw_child in kw_children:
						description = self.kw.keywords[kw_child]['description']
						if description != "": description = " (%s)" % description
						chkbox = gtk.CheckButton('%s%s' % (kw_child, description))
						notebook_page.add(chkbox)

				self.notebook.append_page(notebook_page, gtk.Label(k))
	def __init_treeview(self):
		"""Build a TreeView and a TreeModel."""
		self.treeview  = self.gui.get_widget("%s_treeview" % self.gui_name)
		self.treeview.set_rules_hint(True)

		pxb_render = gtk.CellRendererPixbuf()
		pxb_render.set_property('xpad', 2)
		pxb_render.set_property('ypad', 2)
		pxb_render.set_property('width', 54)
		pxb_render.set_property('height', 54)

		render = gtk.CellRendererText()
		render.set_property('ellipsize', pango.ELLIPSIZE_END)

		if self.gui_name == 'query':
			self.liststore = gtk.ListStore(str, str, int, int, str)

			iconcol = gtk.TreeViewColumn('Fichier', pxb_render)
			def cell_data_pb(column, cell, model, iter):
				icon = model[iter][4]
				if icon == '': cell.set_property('pixbuf', None)
				elif icon[0] == '/': cell.set_property('pixbuf', gtk.gdk.pixbuf_new_from_file_at_size(icon, 48, 48))
				else:cell.set_property('pixbuf', self.iconTheme.load_icon(icon, 48, gtk.ICON_LOOKUP_NO_SVG))
			iconcol.set_cell_data_func(pxb_render, cell_data_pb)

			self.treeview.append_column(iconcol)

			self.tvcolumn0 = gtk.TreeViewColumn('Fichier', render)
			self.tvcolumn0.set_sort_column_id(0)
			self.tvcolumn0.set_resizable(True)
			# quand on veut un contenu de cellule plus "fancy", on definit un renderer custom
			self.tvcolumn0.set_cell_data_func(render, self.__query_cell_render)
		else:
			self.liststore = gtk.ListStore(str)
			self.tvcolumn0 = gtk.TreeViewColumn('Chemin', render)
			self.tvcolumn0.set_sort_column_id(0)
			self.tvcolumn0.set_resizable(True)
			# quand on veut un rendu "de base" avec une seule ligne de texte.
			self.tvcolumn0.add_attribute(render, 'text', 0)

		self.treeview.set_model(self.liststore)
		self.treeview.append_column(self.tvcolumn0)
	def __query_cell_render(self, column, cell, model, iter):
		"""Take a filename and render it as Pango markup with fancy informations for a fancy TreeView."""
		row = model[iter]
		size_str = hlstr.statsize2human(row[2])
		mod_str  = strftime('%d %B %Y à %H:%M', localtime(row[3]))
		color    = '#999999'
		cell.set_property('markup', '<big><b>%s</b></big>    <span foreground="%s">%s</span>\n        <small><span foreground="%s">dans</span> <tt>%s</tt>\n<span foreground="%s">modifié le</span> %s</small>' % (row[0], color, size_str, color, row[1].split('/', 2)[2], color, mod_str))
	def destroy_event(self, widget, event = None, data = None):
		self.hc.EndSession()
		gtk.main_quit()
		return False
	def clear_checkboxes(self, widget):
		"""TODO"""

		def clear_checkbox(obj):
			if type(obj) == gtk.CheckButton:                 obj.set_active(False)
			elif type(obj) in (gtk.Box, gtk.VBox, gtk.HBox): obj.foreach(clear_checkbox)

		self.clearing = True

		for i in range(0, self.notebook.get_n_pages()):
			self.notebook.get_nth_page(i).foreach(clear_checkbox)

		self.clearing = False
	def connect_checkboxes(self, func):
		"""TODO"""

		def connect_checkbox(obj):
			if type(obj) == gtk.CheckButton: obj.connect("clicked", func)
			elif type(obj) in (gtk.Box, gtk.VBox, gtk.HBox): obj.foreach(connect_checkbox)

		for i in range(0, self.notebook.get_n_pages()):
			self.notebook.get_nth_page(i).foreach(connect_checkbox)
	def selected_keywords_list(self):
		""" Look all keyword checkboxes and build a list with their names. """

		tmp = []

		def looking_for_selected_keywords(obj):
			if type(obj) == gtk.CheckButton and obj.get_active():
				tmp.append(obj.get_label())
			elif type(obj) in (gtk.Box, gtk.VBox, gtk.HBox):
				obj.foreach(looking_for_selected_keywords)

		for i in range(0, self.notebook.get_n_pages()):
			self.notebook.get_nth_page(i).foreach(looking_for_selected_keywords)

		try:
			# some windows don't have sellabel, don't fail.
			if tmp == []:
				self.sellabel.set_text('-')
			else:
				self.sellabel.set_markup('<b>%s</b>' % '</b>, <b>'.join(tmp))
		except: pass

		return tmp
	def get_mime_type(self, path):
		""" get GNOME mime-type for path. """
		return gnomevfs.get_mime_type(gnomevfs.get_uri_from_local_path(path))
	def Status(self):
		""" TODO. """
		try:
			(status, load, nrk, nrf) = self.hc.StatusRequest()

			if nrf > 1: fresults = 's'
			else:      fresults = ''

			if nrk > 1: kresults = 's'
			else:      kresults = ''

			if status == LCN_MSG_STATUS_PARTIAL:
				message = '''Server is harvesting, loaded to %2f ; can't determine status with precision.''' % (load)
			else:
				message = 'Server is ready, with currently %d keyword%s and %d file%s in its database.' % (nrk, kresults, nrf, fresults)
			self.StatusMessage(message)

		except exceptions.LicornHarvestException, e:
			self.StatusMessage(str(e))
		except exceptions.LicornHarvestError, e:
			self.StatusMessage(str(e))
	def StatusMessage(self, message):
		""" Push a message into the status bar after having cleaned it. """
		if self.message_id is not None:
			self.statusbar.pop(context_id)
			self.statusbar.remove(self.context_id, self.message_id)

		self.statusbar.push(self.context_id, message)
