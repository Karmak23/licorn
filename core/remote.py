# -*- coding: utf-8 -*-
"""
Licorn core: remote access - http://docs.licorn.org/core.html

Classes, methods and decorators used to access Licorn® core remotely.

:copyright:
    * 2012 Olivier Cortès <olive@licorn.org>
    * 2011 Olivier Cortès <oc@meta-it.fr>
    * 2011 META IT http://meta-it.fr/
:license:
    * GNU GPL version 2
"""

# Python imports
import time, Pyro.errors
import cPickle as pickle
from functools import wraps, partial

# Licorn® imports
from licorn.foundations        import logging
from licorn.foundations.styles import *
from licorn.core               import LMC

# This type is missing from :file:`types.py`
# -> http://mail.python.org/pipermail/python-bugs-list/2010-January/089470.html
# -> http://bugs.python.org/issue1605#msg116811
PropertyType = type(property())

def lmc_connected(retry=2):
	""" This **decorator** will automatically connect to the LMC when
		the decorated function is called.

		:param retry: an ``integer``, specifying how many times a reconnection
			will be attempted if the first fails. Defaults to 2.

		.. warning:: Currently, this decorator is meant to be used on functions
			only, **not instance nor class methods**. This could change in a
			future release, or another dedicated decorator could be created
			for methods.

		.. versionadded:: 1.3
	"""
	def decorated(view_func):
		@wraps(view_func)
		def wrapped(*args, **kwargs):
			# avoid a "global / UnboundLocalError: local variable 'retry'
			# referenced before assignment" quasi-obscure error.
			local_retries = retry

			while local_retries >= 0:
				try:
					force_release = False

					try:
						# we need to wait a little, to avoid cycle restarts.
						LMC.connect(delayed_daemon_start=True)

						#print '>> lmc_connected[1] for', func.__name__, str(a), str(kw)
						try:
							return view_func(*args, **kwargs)

						except:
							logging.exception(
									_(u'Exception while running {0}({1}, {2})'),
										(ST_NAME, view_func.__name__),
										u', '.join(str(a) for a in args),
										u', '.join((u'%s=%s' % (k, v))
											for k, v in kwargs.iteritems())
								)

					except pickle.PickleError:
						logging.exception(_(u'{0}: Pickle error on licornd side, '
									u'passing this turn.'), current_thread().name)

					except (Pyro.errors.ConnectionClosedError, Pyro.errors.ProtocolError):
						# The connection was already open, but it died between the time
						# it was open, and now that we are using it to make another
						# remote call.
						# We must try to reconnect, but only one time. One time will
						# avoid connection loop in case of a real network problem. In
						# case of a `licornd` reboot, the retry will solve the problem
						# and the user won't ever notice it.

						logging.exception(_(u'Pyro connection closed, retrying{0}.'), (
										_(u' forever') if local_retries < 0 else ''))

						# Force-release the LMC to close all connections.
						force_release = True

					except:
						# any other exception here is very bad. Any view_func
						# exception have already been catched, so we are facing an
						# unhandled one in the decorator or in the Pyro code.

						# Just raise it, after having tryed to release the LMC.
						force_release = True
						raise

				finally:
					try:
						LMC.release(force=force_release)

					except:
						logging.exception(_(u'Exception while releasing LMC.'))

				local_retries -= 1
				if local_retries < 0:
					time.sleep(1.0)
		return wrapped
	return decorated

class CoreObjectProxy(object):
	''' Greatly inspired (Borrowed?) from https://raw.github.com/macdiesel/Python-Proxy-Objects/master/proxy.py
		See http://stackoverflow.com/questions/6102747/checking-if-property-is-settable-deletable-in-python
		for the property details.
	'''

	def __init__(self, obj):
		self._my_wmi_proxied_object_reference = obj
	def __str__(self):
		return '<%s at 0x%x> for %s' % (self.__class__.__name__, id(self), self.__remote_call('__str__')())
	@lmc_connected()
	def __getattr__(self, attr_name):
		obj = self._my_wmi_proxied_object_reference

		try:
			if type(type(obj).__dict__[attr_name]) == PropertyType:
				# read the remote property via Pyro.
				if hasattr(obj, 'controller_name'):
					return LMC.rwi.generic_core_object_property_get(
												obj.controller_name,
												getattr(obj, obj._id_field),
												attr_name
											)
				else:
					return LMC.rwi.generic_core_object_property_get(
												obj.controller_pickle_name_,
												getattr(obj, obj._id_field),
												attr_name
											)
		except KeyError:
			pass

		thing = getattr(obj, attr_name)

		if callable(thing):
			# A method should be called remotely, return a special callable
			# that will wrap the call and return the result.
			return self.__remote_call(attr_name)
		else:
			return thing
	def __remote_call(self, attr_name):

		obj = self._my_wmi_proxied_object_reference

		if hasattr(obj, 'controller_name'):
			return partial(
								self.__proxy_method_call,
								obj.controller_name,
								getattr(obj, obj._id_field),
								attr_name
							)
		else:
			return partial(
								self.__proxy_method_call,
								obj.controller_pickle_name_,
								getattr(obj, obj._id_field),
								attr_name
							)
	def proxy_dir(self):
		return dir(self._my_wmi_proxied_object_reference)
	@lmc_connected()
	def __setattr__(self, attr_name, value):

		if attr_name == '_my_wmi_proxied_object_reference':
			# this one is special, store it locally.
			# Any other goes via the network.
			self.__dict__['_my_wmi_proxied_object_reference'] = value
			return

		obj = self._my_wmi_proxied_object_reference

		if type(type(obj).__dict__[attr_name]) == PropertyType:
			if hasattr(obj, 'controller_name'):
				LMC.rwi.generic_core_object_property_set(
												obj.controller_name,
												getattr(obj, obj._id_field),
												attr_name, value
											)
			else:
				LMC.rwi.generic_core_object_property_set(
												obj.controller_pickle_name_,
												getattr(obj, obj._id_field),
												attr_name, value
											)

		else:
			# FIXME: this won't do what we expect, will it??
			thing = getattr(obj, attr_name)
	@lmc_connected()
	def __proxy_method_call(self, controller_name, object_id, method_name, *args, **kwargs):

		#print '>> CALL', controller_name, object_id, method_name
		return LMC.rwi.generic_core_object_method_call(
													controller_name,
													object_id, method_name,
													*args, **kwargs
												)
	def __iter__(self):
		for val in getattr(self, 'values')():
			yield CoreObjectProxy(val)

@lmc_connected()
def select(*a, **kw):
	""" Mimics the daemon.rwi.select() method, but wraps the results into
		CoreObjectProxies for easier and transparent operations on the WMI side. """

	#print '>> selecting', str(a), str(kw), 'in', LMC, LMC.rwi, LMC._connections, LMC.system.noop()

	remote_selection = LMC.rwi.select(*a, **kw)

	#lprint(remote_selection)

	return [ CoreObjectProxy(x) for x in remote_selection ]

@lmc_connected()
def select_one(*a, **kw):

	#print '>> selecting ONE', str(a), str(kw), 'in', LMC, LMC.rwi, LMC._connections, LMC.system.noop()

	return CoreObjectProxy(LMC.rwi.select(*a, **kw)[0])

__all__ = ('lmc_connected', 'CoreObjectProxy', 'select', 'select_one')
