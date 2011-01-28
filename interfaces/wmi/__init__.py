# -*- coding: utf-8 -*-

import gettext
_ = gettext.gettext
gettext.textdomain('licorn')

from threading import current_thread

from licorn.foundations        import options, logging
from licorn.foundations.ltrace import ltrace
from licorn.foundations.styles import *
from licorn.foundations.base   import NamedObject

class WMIObject():
	""" Adds WMI-related attributes and method to an extension. """

	_licorn_protected_attrs = [ 'wmi' ]
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
				) for ctx in self.wmi.context_menu_data if len(ctx) == 5 or ctx[5]() ])
	def _countdown(self, name, countdown_seconds, uri=None, limit=0):
		""" Always increment the
			countdown with 2 seconds, else the webpage could refresh too early
			and display a new 1 second countdown, due to rounding errors.

		http://www.plus2net.com/javascript_tutorial/countdown.php """
		return '''
<script type="text/javascript">
function display_{name}(start){{
	window.start_{name} = parseFloat(start);
	// change this to stop the counter at a higher value
	var end_{name} = {limit};
	if(window.start_{name} {counter_test} end_{name}) {{
		// Refresh rate in milli seconds
		mytime=setTimeout('display_countdown_{name}()', 1000)
	}} else {{
		document.location = "{refresh_uri}";
	}}
}}

function display_countdown_{name}() {{
	// Calculate the number of days left
	var days = Math.floor(window.start_{name} / 86400);

	// After deducting the days calculate the number of hours left
	var hours = Math.floor((window.start_{name} - (days *86400))/3600)

	// After days and hours , how many minutes are left
	var minutes = Math.floor((window.start_{name} - (days*86400) - (hours *3600))/60)

	// Finally how many seconds left after removing days, hours and minutes.
	var secs = Math.floor((window.start_{name} - (days*86400) - (hours*3600) - (minutes*60)))

	var x = "";


	if (days > 1)
		x += days + " {days}";

	else if (days > 0)
		x += days + " {day}";

	if (days > 0 && (hours > 0 || minutes > 0 || secs > 0))
		x += ", ";

	if (hours > 1)
		x += hours + " {hours}";

	else if (hours > 0)
		x += hours + " {hour}";

	if (hours > 0 && (minutes > 0 || secs > 0))
		x += ", ";

	if (minutes > 1)
		x += minutes + " {minutes}";

	else if (minutes > 0)
		x += minutes + " {minute}";

	if (minutes > 0 && secs > 0)
		x += ", ";

	if (secs > 1)
		x += secs + " {seconds}";

	else if (secs > 0)
		x += secs + " {second}";

	document.getElementById('countdown_{name}').innerHTML = x;

	// change the operation to make the counter go upwards or downwards
	tt=display_{name}(window.start_{name} {operation} 1);
}}
display_{name}({countdown_seconds});
</script>
<span id='countdown_{name}' class="countdown"></span>'''.format(
		name=name,
		countdown_seconds=countdown_seconds + 2.0,
		day=_('day'), 	days=_('days'),
		hour=_('hour'), hours=_('hours'),
		minute=_('minute'), minutes=_('minutes'),
		second=_('second'), seconds=_('seconds'),
		refresh_uri=uri if uri else ("/" + self.wmi.uri),
		limit=limit,
		operation='+' if limit else '-',
		counter_test='<=' if limit else '>='
	)
	@staticmethod
	def countdown(name, countdown_seconds, uri, limit=0):
		""" Always increment the
			countdown with 2 seconds, else the webpage could refresh too early
			and display a new 1 second countdown, due to rounding errors.

		http://www.plus2net.com/javascript_tutorial/countdown.php """
		return '''
<script type="text/javascript">
function display_{name}(start){{
	window.start_{name} = parseFloat(start);
	// change this to stop the counter at a higher value
	var end_{name} = {limit};
	if(window.start_{name} {counter_test} end_{name}) {{
		// Refresh rate in milli seconds
		mytime=setTimeout('display_countdown_{name}()', 1000)
	}} else {{
		document.location = "{refresh_uri}";
	}}
}}

function display_countdown_{name}() {{
	// Calculate the number of days left
	var days = Math.floor(window.start_{name} / 86400);

	// After deducting the days calculate the number of hours left
	var hours = Math.floor((window.start_{name} - (days *86400))/3600)

	// After days and hours , how many minutes are left
	var minutes = Math.floor((window.start_{name} - (days*86400) - (hours *3600))/60)

	// Finally how many seconds left after removing days, hours and minutes.
	var secs = Math.floor((window.start_{name} - (days*86400) - (hours*3600) - (minutes*60)))

	var x = "";


	if (days > 1)
		x += days + " {days}";

	else if (days > 0)
		x += days + " {day}";

	if (days > 0 && (hours > 0 || minutes > 0 || secs > 0))
		x += ", ";

	if (hours > 1)
		x += hours + " {hours}";

	else if (hours > 0)
		x += hours + " {hour}";

	if (hours > 0 && (minutes > 0 || secs > 0))
		x += ", ";

	if (minutes > 1)
		x += minutes + " {minutes}";

	else if (minutes > 0)
		x += minutes + " {minute}";

	if (minutes > 0 && secs > 0)
		x += ", ";

	if (secs > 1)
		x += secs + " {seconds}";

	else if (secs > 0)
		x += secs + " {second}";

	document.getElementById('countdown_{name}').innerHTML = x;

	// change the operation to make the counter go upwards or downwards
	tt=display_{name}(window.start_{name} {operation} 1);
}}
display_{name}({countdown_seconds});
</script>
<span id='countdown_{name}' class="countdown"></span>'''.format(
		name=name,
		countdown_seconds=countdown_seconds + 2.0,
		day=_('day'), 	days=_('days'),
		hour=_('hour'), hours=_('hours'),
		minute=_('minute'), minutes=_('minutes'),
		second=_('second'), seconds=_('seconds'),
		refresh_uri=uri,
		limit=limit,
		operation='+' if limit else '-',
		counter_test='<=' if limit else '>='
	)

def init():
	""" Initialize the WMI module by importing all WMI objects and making them
		available to the outside world (they must not be used directly). """

	assert ltrace('wmi', '> init()')

	# import pre v1.2.4 WMI objects
	import users, groups, base, utils, server


	# import 1.2.4+ WMI Objects.
	my_globals = globals()
	from licorn.core import LMC

	for controller in LMC:
		if isinstance(controller, WMIObject):
			assert ltrace('wmi', '  collecting WMIObject %s' %
											stylize(ST_NAME, controller.name))
			try:
				my_globals[controller.wmi.uri] = controller.wmi
			except AttributeError:
				logging.warning2('unitialized WMIObject '
					'instance %s (harmless).' % controller.name)

	# FIXME: should we do the same for backends or other objects ?
	# do they satisfy the WMIObject criteria ?

	for ext in LMC.extensions:
		if isinstance(ext, WMIObject) and ext.enabled:
			assert ltrace('wmi', '  collecting WMIObject %s' %
													stylize(ST_NAME, ext.name))
			my_globals[ext.wmi.uri] = ext.wmi

	assert ltrace('wmi', '< init()')

	#assert ltrace('wmi', '< init(%s)'
	#							% ', '.join(globals()))

def wmi_register(wmiobj):
	""" meant to be run from any core object or extension, if they occur to
		create their WMI part after the collect process.

	"""

	my_globals = globals()

	if wmiobj.wmi.uri in my_globals.keys():
		logging.warning('WMI: overwriting %s object '
			'with new instance.' % wmiobj.name)

	my_globals[wmiobj.wmi.uri] = wmiobj.wmi
	assert ltrace('wmi', '  %s: successfully registered object %s.' %(
		current_thread().name, wmiobj.name))

def wmi_unregister(wmiobj):
	""" meant to be run from any core object or extension, if they need to
		unregister themselves from the WMI (eg. a dynamically disabled
		extension).
	"""
	my_globals = globals()

	if wmiobj.wmi.uri in my_globals.keys():
		del my_globals[wmiobj.wmi.uri]
		assert ltrace('wmi', '  %s: successfully unregistered object %s.' %(
			current_thread().name, wmiobj.name))

	else:
		logging.warning('WMI: unknown object %s, cannot unregister'
		 % wmiobj.name)

