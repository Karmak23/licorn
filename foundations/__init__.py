# -*- coding: utf-8 -*-
"""
Licorn Foundations - http://docs.licorn.org/foundations.html

Copyright (C) 2007-2010 Olivier Cortès <olive@deep-ocean.net>
Licensed under the terms of the GNU GPL version 2
"""

from licorn.version import version

# ===================================================== foundations imports
import bootstrap

# warning: import gettext *after* bootstrap (for UTF8 setup).
import gettext

from _options  import options
from _settings import settings

# a small trick to be able to import licorn.foundations.json
# without our json module to conflict with python's when importing
# the python one into ours.
import _ljson as json

__all__ = [ 'version', 'options', 'settings', 'json', 'gettext' ]
