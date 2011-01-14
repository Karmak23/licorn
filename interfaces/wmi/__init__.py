# -*- coding: utf-8 -*-

import gettext
_ = gettext.gettext
gettext.textdomain('licorn')

from licorn.foundations.ltrace import ltrace
from licorn.foundations.styles import *
from licorn.foundations.base import NamedObject

class WMIObject():
	""" Adds WMI-related attributes and method to an extension. """

	import utils
	def create_wmi_object(self,uri, name, alt_string,
								context_menu_data,
								successfull_redirect=None):
		"""
			WMI extension pseudo-constructor. Must be called at the end of your
			standard extension constructor (``__init__``).

			You must pass to this method:

			* uri: http://localhost/uri/
			* name: pretty name
			* alt_string: alternative text / description
			* context_menu_data: list of context_links, consisting of elements
			  of the form::

				[ pretty_name, uri, title, css_class, icon_css_class ]

			May pass to constructor (optional):

			* successfull_redirect (string; URI for redirects when successfull
			  action occurs; constructed from uri if not given)

			May define any method with this prototype:

			* methods with name starting with '_wmi_' (eg. ``_wmi_main``) and
			  accepting at least these arguments:

				* ``uri`` as first
				* ``http_user`` as second
				* ``**kwargs`` as last

				.. note:: you can put as many arguments your method requires
					between ``http_user`` and ``**kwargs`` (this one serves as a
					catchall, in fact).

			* method only returns wmi tuples (RET_TYPE, data as string) or raises exceptions.

			Must define at least the method ``_wmi_main`` which follows rules above.

			.. versionadded:: 1.2.4
		"""
		assert ltrace('wmi', '| WMIObject.create_wmi_object(%s, %s)' % (name, uri))
		self.wmi                      = NamedObject(name=uri)
		self.wmi.uri                  = uri[1:] if uri[0] == '/' else uri
		self.wmi.name                 = name
		self.wmi.alt_string           = alt_string
		self.wmi.context_menu_data    = context_menu_data
		self.wmi.successfull_redirect = (uri + '/main'
											if successfull_redirect is None
											else successfull_redirect)
		self.wmi.rewind_message       = _('<br /><br />Go back with your '
											'browser, double-check data and '
											'validate the web-form.')
		self.wmi.parent               = self
		self.setup_methods()
	def setup_methods(self):
		""" Gather all ``_wmi_*`` of current instance and reference them in the
			instance's wmi object, to make them available to WMI with
			standardized names.
		"""

		assert ltrace('wmi', '| %s.setup_methods()' % self.name)

		for key in dir(self):
			if key.startswith('_wmi_'):
				value = getattr(self, key)
				if callable(value):
					setattr(self.wmi, key[5:], value)
	def _ctxtnav(self, active=True):
		""" build a context menu mavigation, active or not. """

		disabled = 'un-clickable'
		onClick  = 'onClick="javascript: return(false);"'

		if active:
			disabled = ''
			onClick = ''

		return '''
		<div id="ctxtnav" class="nav">
			<h2>Context Navigation</h2>
			<ul>
				%s
			</ul>
		</div>
		''' % '\n\t\t'.join(['<li><a href="%s" title="%s" %s class="%s">'
				'<div class="%s %s" id="%s">%s</div></a></li>' % (
					ctx[1], ctx[2],
					onClick, disabled,
					ctx[3],
					disabled,
					ctx[4],
					ctx[0]
				) for ctx in self.wmi.context_menu_data ])


def init():
	""" Initialize the WMI module by importing all WMI objects and making them
		available to the outside world (they must not be used directly). """

	assert ltrace('wmi', '> init()')

	# import pre v1.2.4 WMI objects
	import users, groups, base, utils, server, machines


	# import 1.2.4+ WMI Objects.
	my_globals = globals()
	from licorn.core import LMC

	for controller in LMC:
		if isinstance(controller, WMIObject):
			assert ltrace('wmi', '  collecting WMIObject %s' %
											stylize(ST_NAME, controller.name))
			my_globals[controller.wmi.uri] = controller.wmi

	# FIXME: should we do the same for backends or other objects ?
	# do they satisfy the WMIObject criteria ?

	for ext in LMC.extensions:
		if isinstance(ext, WMIObject):
			assert ltrace('wmi', '  collecting WMIObject %s' %
													stylize(ST_NAME, ext.name))
			my_globals[ext.wmi.uri] = ext.wmi

	assert ltrace('wmi', '< init()')

	#assert ltrace('wmi', '< init(%s)'
	#							% ', '.join(globals()))
