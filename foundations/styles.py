# -*- coding: utf-8 -*-
"""
Licorn foundations - http://dev.licorn.org/documentation/foundations

styles - ascii colors and python "pseudo CSS".

Copyright (C) 2005-2008 Olivier Cortès <oc@5sys.fr>
Licensed under the terms of the GNU GPL version 2

"""

# bright is to be added to dark colors (00;XXm) to obtain the brighter colors.
#   "bright" : '\x1b[0;01m',

ST_NO     = 0
ST_RED    = 1
ST_BRICK  = 2
ST_FOREST = 3
ST_GREEN  = 4
ST_BROWN  = 5
ST_YELLOW = 6
ST_NAVY   = 7
ST_BLUE   = 8
ST_PURPLE = 9
ST_MAGENTA= 10
ST_CADET  = 11
ST_CYAN   = 12
ST_GRAY   = 13
ST_WHITE  = 14

__ascii = {
	ST_RED    : '\x1b[01;31m',
	ST_BRICK  : '\x1b[00;31m',
	ST_FOREST : '\x1b[00;32m',
	ST_GREEN  : '\x1b[01;32m',
	ST_BROWN  : '\x1b[00;33m',
	ST_YELLOW : '\x1b[01;33m',
	ST_NAVY   : '\x1b[00;34m',
	ST_BLUE   : '\x1b[01;34m',
	ST_PURPLE : '\x1b[00;35m',
	ST_MAGENTA: '\x1b[01;35m',
	ST_CADET  : '\x1b[00;36m',
	ST_CYAN   : '\x1b[01;36m',
	ST_GRAY   : '\x1b[00;37m',
	ST_WHITE  : '\x1b[01;37m',
	ST_NO     : '\x1b[0;0m'
	}

ST_OK        = 1
ST_BAD       = 2
ST_IMPORTANT = 3
ST_SECRET    = 4
ST_PATH      = 5
ST_URL       = 6
ST_ATTR      = 7
ST_ATTRVALUE = 8
ST_NAME      = 9
ST_APPNAME   = 10
ST_OPTION    = 11
ST_DEBUG     = 12
ST_NOTICE    = 13
ST_MODE      = 14
ST_PKGNAME   = 15
ST_DEFAULT   = 16
ST_ACL       = 17
ST_SPECIAL   = 18
ST_UGID      = 19
ST_LOGIN     = 20
ST_LINK      = 21
ST_REGEX     = 22
ST_LOG       = 23
ST_LIST_L1   = 24
ST_LIST_L2   = 25
ST_LIST_L3   = 26
ST_LIST_L4   = 27
ST_LIST_L5   = 28
ST_LIST_L6   = 29
ST_DEBUG2    = 30
ST_DEBUG     = 31
ST_NOTICE    = 32
ST_INFO      = 33
ST_WARNING   = 34
ST_ERROR     = 35

colors = {
	ST_NO        : __ascii[ST_NO],
	ST_OK        : __ascii[ST_GREEN],
	ST_BAD       : __ascii[ST_RED],
	ST_IMPORTANT : __ascii[ST_RED],
	ST_SECRET    : __ascii[ST_BRICK],
	ST_PATH      : __ascii[ST_NAVY],
	ST_ATTR      : __ascii[ST_NAVY],
	ST_URL       : __ascii[ST_BLUE],
	ST_LOGIN     : __ascii[ST_CADET],
	ST_NAME      : __ascii[ST_CADET],
	ST_APPNAME   : __ascii[ST_YELLOW],
	ST_OPTION    : __ascii[ST_NAVY],
	ST_DEBUG	  : __ascii[ST_BROWN],
	ST_REGEX     : __ascii[ST_BROWN],
	ST_MODE      : __ascii[ST_FOREST],
	ST_ATTRVALUE : __ascii[ST_FOREST],
	ST_PKGNAME   : __ascii[ST_CADET],
	ST_DEFAULT   : __ascii[ST_WHITE],
	ST_SPECIAL   : __ascii[ST_CYAN],
	ST_LINK      : __ascii[ST_CYAN],
	ST_UGID      : __ascii[ST_BLUE],
	ST_ACL       : __ascii[ST_FOREST],
	ST_LOG       : __ascii[ST_YELLOW],
	ST_LIST_L1   : __ascii[ST_BLUE],
	ST_LIST_L2   : __ascii[ST_BLUE],
	ST_LIST_L3   : __ascii[ST_BLUE],
	ST_LIST_L4   : __ascii[ST_BLUE],
	ST_LIST_L5   : __ascii[ST_BLUE],
	ST_LIST_L6   : __ascii[ST_BLUE],
	ST_DEBUG2    : __ascii[ST_BROWN],
	ST_DEBUG     : __ascii[ST_BROWN],
	ST_NOTICE    : __ascii[ST_YELLOW],
	ST_INFO      : __ascii[ST_YELLOW],
	ST_WARNING   : __ascii[ST_RED],
	ST_ERROR     : __ascii[ST_RED]
	}


def stylize_choose(type, what) :
	""" On first call of the function, choose what styling will be done for the entire run. """	

	global stylize

	# we must do this here, else it will produce a circular loop at first load of 'styles".
	# this happens because 'styles' is here (in foundations). It will be moved out of here
	# one day.
	from licorn.foundations import options

	if options.no_colors :
		stylize = stylize_cli_no_colors
	else :
		stylize = stylize_cli_colors
	
	# TODO: create and use options.web_output and stylize_web()
	
	# after the choice was made, call the real function
	return stylize(type, what)

def stylize_cli_no_colors(type, what) :
	"""Return a non-colorized acsii string."""
	return what

def stylize_cli_colors(type, what) :
	"""	Return a colorized acsii string.
		This won't work as expected on nested styles, but in CLI they shouldn't be used anyway.
	"""
	return "%s%s%s" % (colors[type], what, colors[ST_NO])

# on instanciation, use the first function that will choose the right one after 'options" is
# initialized. This must be done this way because in 99% of cases, the 'styles" modules is
# loaded before the 'options" are set.
stylize = stylize_choose

