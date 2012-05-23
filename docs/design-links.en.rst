
.. _design-links.en:

==============
External links
==============


CSS / jQuery hints
------------------

Various sources and links:

	http://lesscss.org/
	http://border-radius.com/
	http://jscompress.com/
	http://stackoverflow.com/questions/5784781/how-to-turn-a-whole-tr-into-a-link
	http://stackoverflow.com/questions/7510753/trhover-not-working
	http://stackoverflow.com/questions/1160008/which-keycode-for-escape-key-with-jquery
	https://github.com/jquery/jquery-color

image / css preloader

	http://binarykitten.me.uk/dev/jq-plugins/107-jquery-image-preloader-plus-callbacks.html

Animate background-position doesn't work anymore with jQuery 1.5+:

	http://www.screenfeed.fr/blog/jquery-1-5-remedier-au-bug-de-animate-avec-background-position-0296/

This could help one day:

	http://www.webinventif.fr/wp-content/uploads/projets/wslide/index.htm

DJango / Jinja2
---------------

http://exyr.org/2010/Jinja-in-Django/ (url_for)

Python cache
------------

http://stackoverflow.com/questions/1427255/is-there-a-python-caching-library
http://stackoverflow.com/questions/5157696/python-cache-library
http://wiki.python.org/moin/PythonDecoratorLibrary#Memoize


(probably) Useful Python modules (to study for inclusion)
---------------------------------------------------------

Ptrace as a working alternative to "inotify on /proc"
http://help.lockergnome.com/linux/inotify-proc--ftopict486108.html
https://bitbucket.org/haypo/python-ptrace/wiki/Home

Various notes
-------------

Generate a 503 instead of a 500
	http://mathieu.agopian.info/blog/2011/04/django-et-le-handler500-retourner-une-erreur-503/

msg push > 250 bytes
	http://markmail.org/message/jekfsuvw2ajwigo3

http://lucumr.pocoo.org/

http://net.tutsplus.com/tutorials/python-tutorials/10-insanely-useful-django-tips/


HTTP Stream / push, etc
-----------------------

Base principle:
	http://en.wikipedia.org/wiki/Comet_%28programming%29
	http://ajaxpatterns.org/HTTP_Streaming

Examples with gevent:
	http://blog.gevent.org/2009/10/10/simpler-long-polling-with-django-and-gevent/
	https://bitbucket.org/denis/gevent/src/tip/examples/webchat/chat/views.py

http://blog.gevent.org/2009/12/05/more-comet-with-gevent/
https://bitbucket.org/denis/stream-web/changeset/25640cac0c65


WebSockets:
	http://websocket.org/quantum.html
	http://pypi.python.org/pypi/gevent-websocket/
	http://blog.chromium.org/2011/08/new-websocket-protocol-secure-and.html
		dans chrome depuis la version 14.x

Reconnection during a long-polling phase:
	très long: http://jsguy.com/?p=103
	plus court: http://stackoverflow.com/questions/333664/simple-long-polling-example-code

A Throbber:
	http://stackoverflow.com/questions/6021848/block-ui-spinning-preloader

## Multiple web sessions in multiple tabs

http://stackoverflow.com/questions/368653/how-to-differ-sessions-in-browser-tabs
http://stackoverflow.com/questions/4479995/managing-webapp-session-data-controller-flow-for-multiple-tabs
https://github.com/chrisdew/subsession
