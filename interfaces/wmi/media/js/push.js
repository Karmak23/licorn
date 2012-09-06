/*
 * Copyright (C) 2011-2012 Olivier Cortès <olive@licorn.org>
 * Copyright (C) 2011-2012 META IT S.à.S http://meta-it.fr/
 *
 * Licensed under the terms of the GNU GPL version 2
 */

var push_active       = true;
var push_stream_error = false;
var push_setup_done   = false;
var current_push_url  = null;

function push_setup(base_location) {

	if (base_location === undefined) {
		// from http://blah/foo/bar?baz we get '/foo/bar?baz'

		if (current_push_url) {
			base_location = current_push_url;

		} else {
			base_location = ('/setup/'
				+ document.location.toString().split('/').slice(3).join('/'))
					.replace('//', '/');
		}
	} else {
		base_location = '/setup' + base_location;
	}

	// store the current URL for future reconnection attempts.
	current_push_url = base_location

	//console.log('PUSH: stream setup for ' + base_location + '.');

	// setup the listeners and collectors on the server side,
	// for the current location (only first part is taken,
	// eg for '/users/new', we transmit only '/users/'
	//console.log(('/' + document.location.toString().split('/')[3] + '/setup').replace('//', '/'));

	$.get(current_push_url)

		// in case of a previous error, this will display a "reconnected"
		// message and clear the error-related variables.
		.success(push_setup_success)

		// on any error, try to do something usefull
		.error(push_error);
}
function push_setup_success() {

	if (push_active) {
		if (push_stream_error) {
			push_stream_error = false;
			show_message_through_notification(
					gettext('Push connection back online, rock\'n roll!'), 5000);
		}
	}

	// once the setup request is completed (which is why we are here),
	// we can begin the long-polling cycle.
	push_get();
}
function push_get() {
	$.get('/push')

		// evaluate one or more json calls returned by the request.
		.success(push_evaluate)

		// relauch the whole push process in case of an error.
		.error(push_error);
}
function push_error() {

	//console.log('PUSH: connection lost, reconnection in 5 seconds.');

	if (push_active) {

		if (push_stream_error) {
			show_message_through_notification(
					gettext('Push connection lost. Retrying in 5 seconds.'),
					5000, 'push_reconnection_notification');
		} else {
			/* We have to delay the first notification, because push connection
			 is known to break when we reload the current page in the browser,
			 or when we click on another page. Displaying a notification
			 would be a false-negative, because it's perfectly normal that the
			 browser closed the stream. */

			setTimeout(function(){
					show_message_through_notification(
							gettext('Push connection lost. Retrying in 3 seconds.'),
							3000, 'push_reconnection_notification');
					}, 2000);

			// on the first error encountered, set the global error state.
			push_stream_error = true;
		}
	}

	// try to re-establish a push connection in 5 seconds, even if the
	// push-stream is inactive; this will be completely silent, but will
	// reconnect it in case we can.
	setTimeout(push_setup, 5000);
}
function push_evaluate(data) {

	//console.log(data);

	calls_list = data.data;

	//console.log('PUSH GOT DATA: ' + calls_list.length + ' JSON calls');

	for(i=0, l=calls_list.length; i<l; i++) {

		curobj = calls_list[i];

		try {
			//console.log(curobj.method);

			if (push_active) {
				eval(curobj.method + "(" + curobj.arguments.join(',') + ")");
			} else {
				//console.log('PUSH inactive, but should have executed '
				//	+ curobj.method + "(" + curobj.arguments.join(',') + ")");
			}

		} catch (err) {
			// don't crash on error, just display it and continue.
			try {
				console.log(err);

			} catch (err) {
				// don't re-crash on IE which doesn't have console.log().
			}
		}
	}

	// loop over the push_get() function to acheive the long-polling mechanism.
	push_get();
}
