/*
* Licorn javascript utils
*
* Copyright (C) 2011 Robin Lucbernet <robinlucbernet@gmail.com>
* Licensed under the terms of the GNU GPL version 2
*/

/*
* URLEncode : allow to encode and decode URLs.
*/
$.extend({URLEncode:function(c){var o='';var x=0;c=c.toString();var r=/(^[a-zA-Z0-9_.]*)/;
  while(x<c.length){var m=r.exec(c.substr(x));
    if(m!=null && m.length>1 && m[1]!=''){o+=m[1];x+=m[1].length;
    }else{if(c[x]==' ')o+='+';else{var d=c.charCodeAt(x);var h=d.toString(16);
    o+='%'+(h.length<2?'0':'')+h.toUpperCase();}x++;}}return o;},
URLDecode:function(s){var o=s;var binVal,t;var r=/(%[^%]{2})/;
  while((m=r.exec(o))!=null && m.length>1 && m[1]!=''){b=parseInt(m[1].substr(1),16);
  t=String.fromCharCode(b);o=o.replace(m[1],t);}return o;}
});

function head_over_to(next_location) {
	/*
	 * Make the browser go to another page, the smart way:
	 * 		- deactivate the push stream to avoid false-positive error messages,
	 * 		- setup the big information screen in case the next page is long to load
	 * 		- make the document location point to it
	 */

	//console.log("HEADING OVER TO " + next_location);

	push_active = false;
	loading_animation(500);
	document.location = next_location;
}

function loading_animation_func() {
	$('body').prepend('<div id="loading_information"><span class="push_reconnection_notification">'
		+ gettext('Collecting data, please wait&hellip;') + '</span></div>');
	$("#loading_information").fadeIn('slow');
}

function loading_animation(delay){
	if (typeof delay == 'undefined') {
		loading_animation_func();
	} else {
		setTimeout(loading_animation_func, delay);
	}
}

/* utility method, since javascript lacks a printf */
function strargs(str, args) {
	// comes from http://jsgettext.berlios.de/

    // make sure args is an array
    if ( null == args ||
         'undefined' == typeof(args) ) {
        args = [];
    } else if (args.constructor != Array) {
        args = [args];
    }

    // NOTE: javascript lacks support for zero length negative look-behind
    // in regex, so we must step through w/ index.
    // The perl equiv would simply be:
    //    $string =~ s/(?<!\%)\%([0-9]+)/$args[$1]/g;
    //    $string =~ s/\%\%/\%/g; # restore escaped percent signs

    var newstr = "";
    while (true) {
        var i = str.indexOf('%');
        var match_n;

        // no more found. Append whatever remains
        if (i == -1) {
            newstr += str;
            break;
        }

        // we found it, append everything up to that
        newstr += str.substr(0, i);

        // check for escpaed %%
        if (str.substr(i, 2) == '%%') {
            newstr += '%';
            str = str.substr((i+2));

        // % followed by number
        } else if ( match_n = str.substr(i).match(/^%(\d+)/) ) {
            var arg_n = parseInt(match_n[1]);
            var length_n = match_n[1].length;
            if ( arg_n > 0 && args[arg_n -1] != null && typeof(args[arg_n -1]) != 'undefined' )
                newstr += args[arg_n -1];
            str = str.substr( (i + 1 + length_n) );

        // % followed by some other garbage - just remove the %
        } else {
            newstr += '%';
            str = str.substr((i+1));
        }
    }

    return newstr;
}

function zeroFill(number, width) {
	//http://stackoverflow.com/questions/1267283/how-can-i-create-a-zerofilled-value-using-javascript
	width -= number.toString().length;
	if ( width > 0 ) {
		return new Array( width + (/\./.test( number ) ? 2 : 1) ).join( '0' ) + number;
	}
	return number;
}
function isInt(x) {
   var y = parseInt(x);
   if (isNaN(y)) return false;
   return x == y && x.toString() == y.toString();
 }

/*
 * Dialog Object
 */
function dialog(title, content, yes_no, yes_action, content_has_to_be_loaded, url_to_be_loaded) {
	if (!yes_no) { yes_no = false; }
	if (!content_has_to_be_loaded) { content_has_to_be_loaded = false; }
	if (!url_to_be_loaded) { url_to_be_loaded = '' }

	if (DEBUG || DEBUG_UTILS) console.log("new dialog : ");
	if (DEBUG || DEBUG_UTILS) console.log(" - title : "+title);
	if (DEBUG || DEBUG_UTILS) console.log(" - yes_no : "+yes_no);
	if (DEBUG || DEBUG_UTILS) console.log(" - content_has_to_be_loaded : "+content_has_to_be_loaded);

    this.title = title;
    this.content = content;
    this.yes_no = yes_no;
    this.content_has_to_be_loaded = content_has_to_be_loaded;
    this.url_to_be_loaded = url_to_be_loaded;

    _DIALOG = this;

    this.show = function() {
		$('#dialog').show();
		$('#dialog-content').show();

		data =  '<div id="dialog-head">';
		data += '	<div id="dialog-title">' + this.title + '</div>';
		data += '	<div id="dialog-close"><img src="/media/images/16x16/croix.png"/></div>';
		data += '</div>';
		data += '<div id="dialog-text">';
		data += '	'+ this.content;
		data += '</div>';
		data += '<div id="dialog-buttons">';

		if (this.yes_no == true) {
			data += '	<div class="dialog-button" id="dialog-action-button">';
			data += gettext("Confirm");
			data += '	</div>';
		}

		data += '	<div class="dialog-button" id="dialog-close-button">';

		if (this.yes_no == true) {
			data += gettext("Cancel");

		} else {
			data += gettext("Close");
		}
		data += '	</div>';
		data += '</div>';

		$('#dialog-content').html(data);
		this.init_events();
	};
	this.hide = function() {
		// unbind keyup event
		$('body').unbind('keyup');

		// hide dialog's divs
		$('#dialog').hide();
		$('#dialog-content').hide();
	};
	this.init_events = function() {
		if (this.content_has_to_be_loaded) {
			//console.log("init_load_event " + this.url_to_be_loaded);
			$.getJSON(this.url_to_be_loaded, function(data) {
				//console.log(data);
				$('#dialog-text').html($.base64Decode(data.content));
			});

		}
		$('#dialog-close').click(function() {
			//console.log("blabla");
			_DIALOG.hide();
		});
		$("#dialog-close-button").click(function() {
			_DIALOG.hide();
		});
		$('body').keyup(function() {
			//console.log("keycode "+event.keyCode);
			if (event.keyCode == 27) { // escape key
				if (!$('#dialog').is(':hidden')) {
					_DIALOG.hide();
				}
			}
			if (_DIALOG.yes_no == true) {

				// if yes_no dialog, call yes_action when enter is pressed
				if (event.keyCode == 13) { // enter key
					if (!$('#dialog').is(':hidden')) {
						//console.log('enter');
						yes_action.call();
						_DIALOG.hide();
					}
				}
			}
			else {
				// if normal dialog, hide the dialog with enter too.
				if (event.keyCode == 13) { // enter key
					if (!$('#dialog').is(':hidden')) {
						if (!$('#dialog').is(':hidden')) {
							_DIALOG.hide();
						}
					}
				}
			}
		});

		if (this.yes_no == true) {
			$('#dialog-action-button').click(function() {
				yes_action.call();
				_DIALOG.hide();
			});
		}
	};
}

/*
 * Notifications
 */
var notification_timeout_interval_func;
var master_notification_timeout  = 0;
var default_notification_timeout = 7000;
var notification_displayed       = false;
var notification_timer_funcs     = new Array();
var notification_counter         = 0;

function decrement_master_notification_timeout() {

	//console.log('notif_timeout: ' + master_notification_timeout);

	if (master_notification_timeout > 0) {
		master_notification_timeout -= 1000;

	} else {
		if (notification_displayed) {
			$('#notification').slideUp('slow', function() {
				notification_displayed = false;
			});
		}

		clearInterval(notification_timeout_interval_func);
	}
}

function show_message_through_notification(msg, timeout, css_class) {

	notification_counter += 1;

	if(typeof(timeout) == 'undefined' || timeout == '')
		timeout = default_notification_timeout;

	if(typeof(css_class) == 'undefined')
		css_class = "";

	new_msg = "<div class='notification-text "
		+ "' id='number-" + notification_counter + "-wrapper'>"
		+ "<div class='notification-text " + css_class
		+ "' id='number-" + notification_counter
		+ "' " + (notification_displayed ? "style='display: none;'" : "") + ">"
		+ msg + "</div></div>";

	if (notification_displayed) {
		//current = $('#notification').html();
		//$('#notification').html(current + new_msg);
		$('#notification').append(new_msg);

		$('#number-' + notification_counter).slideDown('slow');
		$('#number-' + notification_counter + '-wrapper').fadeIn('slow');

		if (timeout > master_notification_timeout) {
			// make the #notification div wait at max the time of the current
			// new notification. all internal divs will disseaper anyway.
			master_notification_timeout = timeout;
		}

	} else {
		$('#notification').append(new_msg).slideDown('slow', function() {
			notification_displayed = true;
		});

		master_notification_timeout = timeout;

		// always clear, sometimes it gets created twice.
		clearInterval(notification_timeout_interval_func);

		notification_timeout_interval_func = setInterval(decrement_master_notification_timeout, 1000);
	}

	function hide_item(notification_counter) {
		$("#number-" + notification_counter).slideUp('slow');
		$('#number-' + notification_counter + '-wrapper').fadeOut('slow', function() {
			$(this).remove();

			if ($('#notification').html() == '') {
				// force the notification panel to hide if nothing more to show.
				master_notification_timeout = 0;
			}
		});
	}

	notification_timer_funcs["number-" + notification_counter] = setTimeout(hide_item, timeout, notification_counter);
}

function remove_notification(css_class) {

	objekt = $('.' + css_class);

	clearTimeout(notification_timer_funcs[objekt.attr('id')]);

	objekt.slideUp('slow', function() { $(this).remove(); });

}

function init_instant_apply(page_name) {
	// instant apply mechanism initialize

	interval = 1000;

	form_div = $('#table')

	form_div.find('input:text').keyup(function() {
		//console.log('keyUp');
		clearTimeout(instant_apply_timeout_textbox);

		page='/'+page_name+'/mod/'+ form_div.attr('name') +'/' + $(this).attr('name') + '/' + $(this).val();
		//console.log(page);
		instant_apply_timeout_textbox = setTimeout(function(){
			$.get(page);
		}, interval);

	});

	form_div.find('input:checkbox').click(function() {
		checked = this.checked;
		if (this.checked == true) {
			checked = 'True';
		}
		else {
			checked = '';
		}
		page='/'+page_name+'/mod/'+ form_div.attr('name') +'/' + $(this).attr('name') + '/' + checked;
		//console.log(page);
		$.get(page);
	});

	form_div.find('input:password').keyup(function() {

		var empty = false;
		form_div.find('input:password').each(function() {
			if ($(this).val() == '') {
				empty = true;
			}
		});

		// while one of the two password field is empty do not do
		// anything.
		if ( !empty ) {
			clearTimeout(instant_apply_timeout_pwd);
			instant_apply_timeout_pwd = setTimeout(function(){
				var first = true;
				var match = true;
				form_div.find('input:password').each(function() {
					if (first) {
						pwd = $(this).val();
					}
					else {
						if (pwd != $(this).val()) { match = false; }
					}
					first = false;
				});
				if ( match ) {
					url = '/users/mod/'+ form_div.attr('name') +'/password/'+pwd;
					//console.log(url)
					$.get(url);
				}
				else {
					show_message_through_notification("Incorrect passwords");
				}
			}, interval);
		}
	});

	var instant_apply_timeout_select;
	form_div.find('select').change(function() {
		clearTimeout(instant_apply_timeout_select);
		page='/'+page_name+'/mod/'+ form_div.attr('name') +'/' + $(this).attr('name') + '/' + $.URLEncode($(this).val());
		//console.log(page);
		instant_apply_timeout_select = setTimeout(function(){
				$.get(page);
			}, interval);
	});

	var rel_ids = {
		'no_membership' : 0,
		'guest'         : 1,
		'member'        : 2,
		'resp'          : 3 }

	$('.instant_apply_click').click(function() {
		//console.log('group click '+$('#sub_content').attr('value'))
		div = $('#sub_content').find('#'+$(this).attr('id')).filter('.click_item');
		//console.log(div)
		div.find('.item_hidden_input').addClass('item_currently_selected');

		if (page_name == 'users') {
			url = ('/users/mod/' + $('#sub_content').attr('value')
					+ '/groups/' + $(this).attr('id')
					+ '/' + rel_ids[$(this).attr('value')]);
		}
		else {
			url = ('/groups/mod/' + $('#sub_content').attr('value')
					+ '/users/' + $(this).attr('id')
					+ '/' + rel_ids[$(this).attr('value')]);
		}
		//console.log(url)
		$.get(url);
	});
}
function get_user_groups_list(pattern) {
	groups = [];
	$(pattern).each(function() {
		gid = $(this).find('.item_hidden_input').attr('value');
		if (gid != '') {
			groups.push(gid);
			//console.log($(this));
		}
	});
	return groups.join(',');
}

function init_sub_list_height() {
	nb_list      = $('.sub_content_list').length;
	nb_one_ligne = $('.one_line').length;
	nb_big_ligne = $('.big_line').length;
	nb_title     = $('.sub_content_title').length;

	nb_items_total = 0;
	percentage = [];
	nb_items = [];
	cpt = 0;
	$('.sub_content_list').each(function() {
		nb_items_in_list = $(this).find('.click_item').length;
		if (nb_items_in_list > 50) { nb_items_in_list = 50; }
		if (nb_items_in_list < 5) { nb_items_in_list = 5; }
		nb_items[cpt] = nb_items_in_list;
		nb_items_total += nb_items_in_list;
		cpt += 1;
	});

	$.each(nb_items, function(k, v) {
		percentage[k] = v / nb_items_total;
	});
	//console.log("main : "+$('#main_content').innerHeight())
	//console.log("sub  : "+$('#sub_content').innerHeight())
	//console.log("nb_ol   : "+nb_one_ligne)
	//console.log("ol   : "+$('.one_line').height())
	//console.log("nb_bl   : "+nb_big_ligne)
	//console.log("bl   : "+$('.sub_content_title').outerHeight(true))

	//console.log("table   : "+$('#table').height())
	//console.log("header   : "+$('#sub_content_header').outerHeight(true))
	height = $('#sub_content').innerHeight() - nb_one_ligne * $('.one_line').height() - nb_title * $('.sub_content_title').outerHeight(true)- nb_big_ligne * $('.sub_content_line').outerHeight(true) - $('#sub_content_header').outerHeight(true) -20;
	//console.log(" h:"+height);
	cpt = 0;

	$('.sub_content_list').each(function() {
		_height = height*percentage[cpt];
		$(this).height(_height);
		cpt += 1;
	});
}

function no_accent(s) {
	var r=s.toLowerCase();
    r = r.replace(new RegExp("[àáâãäå]", 'g'),"a");
    r = r.replace(new RegExp("æ", 'g'),"ae");
    r = r.replace(new RegExp("ç", 'g'),"c");
    r = r.replace(new RegExp("[èéêë]", 'g'),"e");
    r = r.replace(new RegExp("[ìíîï]", 'g'),"i");
    r = r.replace(new RegExp("ñ", 'g'),"n");
    r = r.replace(new RegExp("[òóôõö]", 'g'),"o");
    r = r.replace(new RegExp("œ", 'g'),"oe");
    r = r.replace(new RegExp("[ùúûü]", 'g'),"u");
    r = r.replace(new RegExp("[ýÿ]", 'g'),"y");
    return r;
}

