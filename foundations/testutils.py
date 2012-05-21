# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

cache - small in-memory cache for Licorn®.
	because memcached is overkill on thin clients, and beaker is too much for what I need.

:copyright:
	* 2012 Olivier Cortès <olive@deep-ocean.net>
:license: GNU GPL version 2
"""

def monkey_patch_unittest():
	""" We need to patch ``unittest``, for the ``Django`` TS to succeed when
		launched from inside the Licorn® daemon. The patch consists of just
		disabling ``unittest``'s ``installHandler`` method, which would fail
		because not done from ``MainThread``.

		This is a hack, but ``Django`` doesn't offer the ability to disable the
		handlers (nor ``unittest``).
	"""

	import unittest
	unittest.installHandler = lambda: True

__all__ = ('monkey_patch_unittest', )
