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
 * List Object
 * Object representing a custom list. This object need several functions
 * to work correctly. These functions are specific to object you deal
 * with in your list.
 *
 * You need to declare and to implement these functions :
 * 		- refresh_item_row
 * 		- generate_items_list
 * 		- sort_items_list
 * 		- init_events_list_header
 * 		- create_items
 */

reverse_order=[];
order_pic=[];
reverse_order['asc'] = 'desc';
reverse_order['desc'] = 'asc';
order_pic['asc'] = '<img src="/images/12x12/sort_asc.png" alt="asc order image">';
order_pic['desc'] = '<img src="/images/12x12/sort_desc.png" alt="desc order image">';


/*
 * change_content_of_sub_content_main function
 * Change the content of the sub_content part.
 * Parameter :
 * 		- url_page (string) : url to get
 */

 function change_content_of_sub_content_main(url_page, check_lock) {
	if (DEBUG || DEBUG_UTILS) console.log('> change_content_of_sub_content_main(page='+url_page+')');
	if (!check_lock) { check_lock = false; }	
	// if url_page is null, clear #sub_content_main
	if (url_page == null) {
		$('#sub_content_main').fadeOut(function() {
			$('#sub_content_main').html("");
			$('#sub_content_main').fadeIn();
		});
	}
	else {
		// hide the sub_content_main
		$('#sub_content_main').fadeOut(function() {
			apply(url_page, 'change_sub_content');
		});
	}
	if (DEBUG || DEBUG_UTILS) console.log('< change_content_of_sub_content_main()');
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
		data += '	<div id="dialog-title">'+this.title+'</div>';
		data += '	<div id="dialog-close"> <img src="/images/16x16/croix.png"/> </div>';
		data += '</div>';
		data += '<div id="dialog-text">';
		data += '	'+ this.content;
		data += '</div>';
		data += '<div id="dialog-buttons">';
		data += '	<div class="dialog-button" id="dialog-close-button">';
		if (this.yes_no == true) {
			data += _("No");
		}
		else {
			data += _("Close");
		}
		data += '	</div>';
		if (this.yes_no == true) {
			data += '	<div class="dialog-button" id="dialog-action-button">';
			data += _("Yes");
			data += '	</div>';
		}
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
var notification_timeout;
var notification_timeout_value = 7500;
notification_displayed = false;
tab_timeout_text = new Array();
compt = 0;
function show_message_through_notification(msg) {
	compt +=1;
	new_msg = "<div class='notification-text' id='number-"+ compt +"'>"+ msg +"</div>";

	if (notification_displayed) {
		clearTimeout(notification_timeout);
		current = $('#notification').html();
		$('#notification').html(current + new_msg);
	}
	else {

		notification_displayed = true;
		$('#notification').html(new_msg).fadeIn();
	}

	tab_timeout_text[compt] = setTimeout(hide_item, notification_timeout_value, compt);

	function hide_item(compt) {
		$("#number-"+compt).slideDown();
		$("#number-"+compt).fadeOut();
	}

	notification_timeout = setTimeout(function() {
		$('#notification').fadeOut(function() {
			notification_displayed = false;
		});
	}, notification_timeout_value);
}
function init_instant_apply() {
	interval = 1000;

	function function_apply(page, action) {
		apply(page, action);
	}

	var instant_apply_timeout_textbox;
	
	$(".instant_apply_textbox").keyup(function() {
		clearTimeout(instant_apply_timeout_textbox);
		value = $.URLEncode(this.value);
		page=$(this).attr('action') + value;
		login = $(this).attr('action').split('/')[3];
		instant_apply_timeout_textbox = setTimeout(function_apply, interval, page, 'instant_apply');
	});
	var instant_apply_timeout_checkbox;
	$(".instant_apply_checkbox").click(function() {
		clearTimeout(instant_apply_timeout_checkbox);
		checked = this.checked;
		page=$(this).attr('action') + $.URLEncode(checked);
		login = $(this).attr('action').split('/')[3];
		instant_apply_timeout_checkbox = setTimeout(function_apply, interval, page, 'instant_apply');
	});
	var instant_apply_timeout_pwd;
	function one_password_is_empty() {
		r = false;
		$(".instant_apply_password").each(function() {
			if ($(this).val() == "") {
				r = true;
			}
		});
		return r;
	}
	$(".instant_apply_password").keyup(function() {
		if ( !one_password_is_empty() ) {

			clearTimeout(instant_apply_timeout_pwd);

			login  = $(this).attr('action').split('/')[3];
			action = $(this).attr('action');

			instant_apply_timeout_pwd = setTimeout(function(){
				pwds = new Array();
				compt = 0;
				pwds_match = false;
				$(".instant_apply_password").each(function() {
					pwds[compt] = $(this).val();
					compt += 1;
				});
				ref = pwds[0];
				for (i=1;i<pwds.length;i++) {
					if (pwds[i] == ref) {
						pwds_match = true;
					}
				}
				if (pwds_match) {
					page =  action + ref;
					apply(page, 'instant_apply');
				}
				else {
					show_message_through_notification(strargs(_("Incorrect password for user %1"), [login]));
				}
			}, interval);
		}
	});
	var instant_apply_timeout_select;
	$(".instant_apply_select").change(function() {
		clearTimeout(instant_apply_timeout_select);
		page = $(this).attr('action') + $.URLEncode($(".instant_apply_select option:selected").val());
		login = $(this).attr('action').split('/')[3];
		instant_apply_timeout_select = setTimeout(function(){
				apply(page, 'instant_apply');
			}, interval);
	});

	var instant_apply_timeout_click;
	$(".instant_apply_click").click(function() {
		clearTimeout(instant_apply_timeout_click);

		groups = get_items_selected('.click_item');
		action = $(this).attr('action');
		login = $(this).attr('action').split('/')[3];
		page = '';

		instant_apply_timeout_click = setTimeout(function(){
			page= action + '/' + groups;
			apply(page, 'instant_apply');
		}, 3000);
	});
}
function get_items_selected(pattern) {
	group_text = ''
	$(pattern).each(function() {
		gname = $(this).find('.item_hidden_input').attr('value');
		relation = $(this).find('.item_hidden_input').attr('name');
		if (relation != 'no_membership') {
			prefix = '';
			if (relation == 'guest') {
				prefix = 'gst-';
			}

			if (relation == 'resp') {
				prefix = 'rsp-';
			}

			if (group_text == '') {
				group_text += prefix + gname;
			}
			else {
				group_text += ',' + prefix + gname;
			}
		}
	});
	return group_text;
}

/*
 * function apply
 */
function apply(page, action) {
	if (DEBUG || DEBUG_UTILS) console.log('> apply(page='+page+', action='+action+')');

   start_time = new Date();

	$.getJSON(page, function(json_input) {
		if (DEBUG || DEBUG_UTILS) console.log('> SUCCESS for page '+page+'.');
		if (DEBUG || DEBUG_UTILS) console.log(' AJAX REPONSE : '+page);
		if (DEBUG || DEBUG_UTILS) console.log('-----------------------');
		if (DEBUG || DEBUG_UTILS) console.log(json_input);
		if (DEBUG || DEBUG_UTILS) console.log('-----------------------');

		error = false;
		if (json_input.notif != "") {
			show_message_through_notification($.base64Decode(json_input.notif));
		}

		if (json_input.content != '' && json_input.content != 'None' ) {
			if (action == 'instant_apply')  {
				if (DEBUG || DEBUG_UTILS) console.log("Refreshing user_row.");
				console.log(json_input.content)
				refresh_item_row(json_input.content);
			}
			else if (action == 'delete')  {
				item = json_input.content;

				$.each(item, function(key, i) {
					//remove item from list array
					_PAGE.current_list.items = jQuery.grep(_PAGE.current_list.items, function(value) {
						return $(value).attr(_PAGE.current_list.main_attr) != i;
					});
					div = $('#'+_PAGE.current_list.main_attr + '_' + i);
					if (div.hasClass('item_selected')) {
						_PAGE.stop_sub_content_lock();
					}
					$('#'+_PAGE.current_list.main_attr + '_' + i).remove();
				});

				// in case it was the last item in the list
				if (_PAGE.current_list.items.length == 0) {
					template = '<span id="new_item_purpose"> No '+ _PAGE.current_list.name + ' yet on your system. Would you like to <span id="new_item">create one</a>?</span></span>'
					$('#search_bar').remove();
					$('#'+_PAGE.current_list.name+'_list_header').remove();
					$('#'+_PAGE.current_list.name + '_list').find('.item_list_content').remove();
					
					$('#'+_PAGE.current_list.name + '_list').find('.list_content').append(template);
				}
				else {
					_PAGE.current_list.sort_items_list('asc', _PAGE.current_list.main_attr);
				}
				_PAGE.current_list.count_items();

			}
			else if (action == 'change_sub_content') {
				// lock mecanism:
				//	if page is locked : hovers are not prompted
				if (_PAGE.is_locked() && page.search('view') != -1)   {
					return false; 
				}
				// write data in sub_content_main
				content = $.base64Decode(json_input.content);
				$('#sub_content_main').html(content);
				// show sub_content_main
				$('#sub_content_main').fadeIn();
				if (page.match('/edit/')) {
					$('#sub_content_back').click(function() {
						_PAGE.stop_sub_content_lock();
					});
					_PAGE.acquire_lock();
					init_events_on_subcontent_change();
				}
				else if (page.match('/new')) {
					$('#sub_content_back').click(function() {
						_PAGE.stop_sub_content_lock();;
					});
					_PAGE.acquire_lock();
					init_events_sub_content_new();
				}
			}
			else if (action == 'create') {
				if (json_input.content != $.base64Encode('"None"')) {

					_PAGE.current_list.items.push(json_input.content);

					list_name = _PAGE.current_list.name;
					list_obj = _PAGE.current_list;

					// if it is the first item
					if (_PAGE.current_list.items.length == 1) {
						// hide creation purpose
						$('#new_item_purpose').remove();
						// we need to display headers as it is the first element
						template = _PAGE.current_list.generate_list_header();
						template += "			<div class='item_list_content'>"
						template += "			</div>"
						
						$('#'+_PAGE.current_list.name + '_list').find('.list_content').append(template);
					}
					$('#'+_PAGE.current_list.name + '_list').find('.item_list_content').append(generate_item_row(json_input.content));
					list_obj.sort_items_list('asc',list_obj.main_attr);
					list_obj.count_items();
					list_obj.initialize_row_events($(json_input.content).attr(list_obj.main_attr));
					_PAGE.stop_sub_content_lock();
				}
			}

			// update timer :
			end_time = new Date();
			$('#timer').html((end_time-start_time)+ _(" ms of javascript execution"));
		}
		else {
			if (DEBUG || DEBUG_UTILS) console.log("Nothing to display.");
		}
	});

	if (DEBUG || DEBUG_UTILS) console.log("< apply");
}

function Page(name) {
	if (DEBUG || DEBUG_UTILS) { console.log("<> initialising new Page object (name="+name+")"); }
	// list : array of List = lists objects in the page
	this.lists = [];
	// locked : boolean = lock for item hover event
	this.locked = false;
	// name : string = name of the page
	this.name = name;
	// current list : List = current list displayed
	this.current_list;
	// list_mouseover_timeout = timeout object for item hover event
	this.list_mouseover_timeout;

	// we keep a trace of this object
	_PAGE = this;

	// function get_list_by_id(id)
	//	id : int
	// returns the specified List object
	this.get_list_by_id = function(id) {
		return this.lists[id];
	}
	// function get_list_by_name(name)
	//	name : string
	// returns the specified List object
	this.get_list_by_name = function(name) {
		for(i=0;i<this.lists.length;i++) {
			//console.log('searching '+name+' in '+this.lists[i].name);
			if (this.lists[i].name == name) {
				//console.log('ok');
				return this.lists[i];
			}
		}
	}

	// lock mechanism
	this.is_locked = function() {
		return this.locked
	};
	this.acquire_lock = function() {
        this.locked = true;
    };
    this.release_lock = function() {
        this.locked = false;
    };

    this.stop_sub_content_lock = function() {
		this.release_lock();
		$('.item_selected').removeClass('item_selected');
		$('.bkg_selected').removeClass('bkg_selected');
		change_content_of_sub_content_main(null);
	}
    // function initialize_list()
    // initialize the template
	this.initialize_list = function(index) {
		if (DEBUG || DEBUG_UTILS) { console.log("<> PAGE.initialize_list ()"); }

		// the reference of the current list
		current_list = this.lists[index];

		content_height = 100 - ( this.lists.length * 5 );
		//assuming max(header + search) = 12%
		height_list_content = content_height - 12;

		$("#"+current_list.name+'_list').children('.list_title').hide().height('3.5%').fadeIn(500);

		$('.list_content').hide().css({'height' : 0});
		$('.list_displayed').css({'height' : content_height+'%'}).show();
		$('.item_list_content').css({'height' : height_list_content+'%'});

		$('.list_title').click(function() {
			//console.log('CLICK');
			if ($(this).next('.list_content').is(':hidden')) {
				_PAGE.stop_sub_content_lock();
				_PAGE.current_list = _PAGE.get_list_by_name($(this).attr('id'));

				//when we change of list, we need to erase the sub_content
				change_content_of_sub_content_main(null);

				$('.list_content').slideUp(500);
				$(this).next('.list_content').css({'height':content_height+'%'}).slideDown(500);
			}
		});
	}
}
function Licorn_List(list_obj) {
	if (DEBUG || DEBUG_UTILS) { console.log("<> initialising new List object (name="+name+")"); }
	// items : array of item = array of items represented in the list
	this.items     = list_obj.items;
	// title : string = title of the list
	this.title     = list_obj.title;
	// displayed : boolean = true if this list is the first displayed
	this.displayed = list_obj.displayed
	// name : string = name of the list
	this.name      = list_obj.name;
	// main_attr : string = main attribute of the list (login for users, name for groups/privs ...)
	this.main_attr = list_obj.main_attr;
	// uri : string = string representing the uri of the list
	this.uri       = list_obj.uri;
	// list_obj : List object = keep a trace of the JSON list object
	this.list_obj  = list_obj;

	// keep a trace of the list
	// WARNING : this need to be a 'VAR' to be a private variable.
	var _LIST = this;

	// function get_item(text)
	//	text : string = main attribute representing an item
	// returns an item of the list
	this.get_item = function(text) {
		for(i=0;i<this.items.length;i++) {
			if ($(this.items[i]).attr(this.main_attr) == text) {
				return this.items[i];
			}
		}
	};

	// function count_items()
	// count and display the number of items
	this.count_items = function() {
		var nb_items = this.items.length;
		var text = '('+nb_items+')';
		$('#'+_LIST.name+'_count').html(text);
	};

	// function initialize_header_events()
	// initialize events for the list's header
	this.initialize_header_events = function() {
		
		// in case there is no items, initialize the "create one" link
		if (_LIST.items == '') {
			$("#new_item").click(function() {
				page = '/'+_LIST.uri+'/new';

				change_content_of_sub_content_main(page);
				$('.item_selected').removeClass('item_selected');
				$('.bkg_selected').removeClass('bkg_selected');
				
			});
		}
		else {

			// search bar
			var search_box = $('#list_content_'+_LIST.name).find('#search_box');
			//console.log(search_box);
			search_box.keyup(function(event) {
				if (DEBUG || DEBUG_USER) { console.log('<> KEYUP EVENT : on search box of '+_LIST.name+' => '+search_box.val()); }
				_LIST.search(search_box.val());
			});


			// header item click : sort
			$("."+_LIST.name+"_header_item").click(function() {
				item_sort = $(this).attr("id");
				sort_way = $(this).attr("value");

				if (sort_way == 'desc') {
					new_sort = 'asc';
				}
				else {
					new_sort = 'desc';
				}

				$(this).attr("value", new_sort);

				// sort icons
				$('#'+_LIST.name+'_list').find("#"+item_sort).attr("value", reverse_order[sort_way]);
				$('#'+_LIST.name+'_list').find(".item_header_sort").html('');
				$('#'+_LIST.name+'_list').find("#"+item_sort).find(".item_header_sort").html(order_pic[sort_way]);

				if (DEBUG || DEBUG_USER) { console.log('<> CLICK EVENT : on header item '+item_sort+' of '+_LIST.name+' => '+ sort_way); }

				_LIST.sort_items_list(sort_way, item_sort);
			});


			// init massive select
			$('#'+_LIST.name+'_massive_select').click(function() {
				current_status = $(this).attr('checked');
				if (DEBUG || DEBUG_UTILS) { console.log('> CLICK EVENT : on massive select / currently checked : '+current_status); }
				for(i=0;i<_LIST.items.length;i++) {
					item = _LIST.items[i];
					if (! $('#'+_LIST.main_attr+'_'+$(item).attr(_LIST.main_attr)).is(':hidden')) {
						//if the row is not hidden
						$('#checkbox_'+$(item).attr(_LIST.main_attr)).attr('checked', current_status);
					}
				}
				if (DEBUG || DEBUG_UTILS) { console.log('< CLICK EVENT : on massive select'); }

			});

			// init specif events if needed
			init_events_list_header(_LIST);
		}
	}
	// function get_selected_items()
	//	returns items selected in the list
	this.get_selected_items = function() {
		var selected_items = [];
		$.each(this.items, function(k, item) {
			item_div = $('#'+_LIST.main_attr+'_'+$(item).attr(_LIST.main_attr));
			//console.log(item_div);
			//console.log(item_div.find('#checkbox_'+$(item).attr(_LIST.main_attr)));
			if (item_div.find('#checkbox_'+$(item).attr(_LIST.main_attr)).is(':checked')) {
				selected_items.push(item);
			}
		});
		return selected_items
	};

	// function generate_html()
	//	returns the html code representing the list
	this.generate_html = function() {
		if (this.displayed == 'True') {
			displayed = 'list_displayed';
		}
		else {
			displayed = '';
		}
		
		template = "<!-- list "+this.name+" -->"
		template += "	<div id='"+this.name+"_list' class='list'>"
		template += "		<div class='list_title' id='"+this.name+"'>"
		template += "			"+this.title+"<div id='"+_LIST.name+"_count' class='list_title_count'></div>";
		template += "		</div>"
		template += "		<div class='list_content "+displayed+"' id='list_content_"+this.name+"'>"
		if (this.items != '') {
			template += this.generate_list_header();
			template += "			<div class='item_list_content'>"
			$.each(this.items, function (k, item) {
				template += generate_item_row(item);
			});
			template += "			</div>"
		}
		else {
			template += '<span id="new_item_purpose">'
			template += 	strargs(_("No %1 yet on your system. Would you like to "), [this.name]);
			template += '	<span id="new_item">'
			template += _("create one?");
			template += '</span></span>'
		}
		template += "		</div>"
		template += "	</div>"

		return template
	}

	// function initialize_events(list)
	// initialize events of the list
	this.initialize_events = function() {
		if (DEBUG || DEBUG_UTILS) console.log('> LICORN_LIST.initialize_events()');

		this.count_items();

		this.initialize_header_events();

		for(i=0;i<this.items.length;i++) {
			this.initialize_row_events($(this.items[i]).attr(this.main_attr));
		}
		if (DEBUG || DEBUG_UTILS) console.log('< LICORN_LIST.initialize_events()');
	}

	// function search(search_string)
	//	search_string : string = string to search
	// filter items of the list and display them
	this.search = function(search_string) {
		var len = search_string.length;
		if (len == 0)
			len = 0.86;

		effect_duration = 650 / len;

		search_string = search_string.toLowerCase();

		// this is used when reorganizing the visuals.
		compt = 0;

		// go through all attributes of each item, and keep only items
		// whose attributes (one or more) match.
		$.each(this.items, function(key, obj) {
			// OBJECT part of the search.

			match = false;
			//console.log(obj.search_fields);
			$.each(obj.search_fields, function(k, v) {
				if ($(obj).attr(v).toLowerCase().search(search_string) != -1) {
					match = true;

					// break the $.each(), no need to search further in this item.
					return false;
				}
			});

			// VISUAL / HTML part of the search.

			if (compt % 2 != 0) {
				add_classes = [ 'users_row_odd', 'row_odd', 'odd' ];
				del_classes = [ 'users_row_even', 'row_even', 'even' ];
			} else {
				del_classes = [ 'users_row_odd', 'row_odd', 'odd' ];
				add_classes = [ 'users_row_even', 'row_even', 'even' ];
			}

			the_div = $('#'+_LIST.main_attr+'_'+$(obj).attr(_LIST.main_attr));

			if (match) {
				if (the_div.is(':hidden')) {
					the_div.stop(true, true).fadeIn(effect_duration).animate({'margin-top': compt*51+'px' },
										effect_duration * Math.random(), 'swing');
				} else {
					the_div.stop(true, true).animate({'margin-top': compt*51+'px' }, effect_duration * Math.random(), 'swing');
				}
				compt += 1;

				the_div.find('.odd_even_typed').each(function() {
					for (i=0; i<del_classes.length; i++) {
						$(this).removeClass(del_classes[i]);
					}
					for (i=0; i<add_classes.length; i++) {
						$(this).addClass(add_classes[i]);
					}
				});
			}
			else {
				the_div.stop(true, true).fadeOut(effect_duration);
			}
		});
	}

	// function initialize_row_events(item)
	//	item : string = main attr of the item to initialize
	//	initialize an item row
	this.initialize_row_events = function(item) {
		//console.log('initialize_row_events on '+ item +" , "+ "#"+ this.main_attr + "_" + item);

		me = $("#"+_LIST.main_attr+"_" + item);
		child = me.find("."+_LIST.name+"_content");

		// hover event of item_content
		child.hover(function() {
				login_hover = $(this).attr(_LIST.main_attr);
				if (DEBUG || DEBUG_UTILS) console.log('> HOVER EVENT : on item '+login_hover);

				$("#"+ _LIST.main_attr +"_"+login_hover).addClass('hover');

				if (!_PAGE.is_locked()) {
					clearTimeout(_PAGE.list_mouseover_timeout);
					page = '/'+_LIST.uri+'/view/' + login_hover;
					_PAGE.list_mouseover_timeout = setTimeout(function(){
						//console.log("bla");
						change_content_of_sub_content_main(page, true);
					}, 1000);

				}

				if (DEBUG || DEBUG_UTILS) console.log('< MOUSEOVER EVENT ');
			},
			function() {
				if (DEBUG || DEBUG_UTILS) console.log('< HOVER EVENT : on item '+login_hover);

				if ($("#"+ _LIST.main_attr +"_"+login_hover).hasClass('hover')) {
					clearTimeout(_PAGE.list_mouseover_timeout);
					$("#"+ _LIST.main_attr +"_"+login_hover).removeClass('hover');
				}
			});

		// deal with click event on item_content
		child.click(function() {
			_item = $(this).attr(_LIST.main_attr);

			if (DEBUG || DEBUG_UTILS) console.log('> CLICK EVENT : on item '+_item);

			clearTimeout(_PAGE.list_mouseover_timeout);
			if ($("#"+ _LIST.main_attr +"_"+_item).hasClass('item_selected')) {
				// if item is already selected
				_PAGE.stop_sub_content_lock();
				if (DEBUG || DEBUG_UTILS) console.log('< CLICK EVENT : item '+_item+' already selected, releasing lock');
				change_content_of_sub_content_main(null);
			}
			else {
				$('.item_selected').removeClass('item_selected');
				$('.bkg_selected').removeClass('bkg_selected');
				$("#"+ _LIST.main_attr +"_"+_item).addClass('item_selected');
				$("#"+ _LIST.main_attr +"_"+_item).children().addClass('bkg_selected');
				$("#"+ _LIST.main_attr +"_"+_item).find("."+ _LIST.name +"_content").children().addClass('bkg_selected');

				page = "/"+_LIST.uri+"/edit/";

				change_content_of_sub_content_main("/"+_LIST.uri+"/edit/"+_item);
				if (DEBUG || DEBUG_UTILS) console.log('< CLICK EVENT : item '
								+ _item + ' is now selected, acquiring lock');
			}
		});

		// init nav on each rows
		me.hover(function() {
				if (DEBUG || DEBUG_USER) { console.log('> HOVER EVENT : display .item_menu'); }

				if (!_PAGE.is_locked()) {
					$(this).find(".item_menu").show();
				}
			}, function() {
				if (DEBUG || DEBUG_USER) { console.log('< HOVER EVENT : hide .item_menu'); }

				if (!_PAGE.is_locked()) {
					$(this).find(".item_menu").hide();
				}
			}
		);
		me.click(function() {
			$(".item_menu").hide();

			// don't allow remove/reapply when in edit mode.
			//$(this).find(".item_menu").show();
		});

		// init specifics events
		init_events(me);

	}

	// function my_sort(sort_way, sort_items)
	//	sort_way : string = 'asc' or 'desc'
	//	sort_items : string = attribute to sort the list with
	// returns this.items array sorted
	this.my_sort = function(sort_way, sort_items) {

		var selectors = sort_items;

		this.items.sort(function(a, b) {
			// run through each selector, and return first non-zero match
			for(var i = 0; i < selectors.length; i++) {
				var selector = selectors[i];
				var first = $(a).attr(selector);
				var second = $(b).attr(selector);

				var isNumeric = Number(first) && Number(second);
				if(isNumeric) {
					(sort_way == 'asc') ? diff=first-second : diff=second-first;

					if(diff != 0) {
						return diff;
					}
				}
				else if(first != second) {
					(sort_way == 'asc') ? r=(first<second) ? -1 : 1 : r=first>second ? -1 : 1;
					return r;
				}
			}

			return 0;
		});
		return this.items;
	}

	// function generate_list_header()
	//	returns the html code of the header
	this.generate_list_header = function() {

		order = 'asc';
		sort_column = _LIST.main_attr;

		if (order == "asc") { reverseorder = "desc"; }
		else { reverseorder = "asc"; }

		html = '<span id="search_bar">';

		if (this.list_obj.massive_operations.displayed == 'True') {
			html += '		<span id="search_bar_nav">';
			html += '			<div id="search_bar_nav_content">';
			$.each(this.list_obj.massive_operations.items, function(k, ope) {
				html += '			<img src="'+ope.icon_link+'" id="'+ope.id+'"/>';
			});

			html += '			</div>';
			html += '			<div id="search_bar_nav_title">';
			html += _("Mass actions: ");
			html += '			</div>';
			html += '		</span>';
		}

		if (this.list_obj.search.displayed == 'True') {
			html += '		<span id="search_bar_search">';
			html += '			<input type="text" name="search" id="search_box">';
			html += '			<!--<img id="search_button" src="/images/24x24/preview.png" title="search"/>-->';
			html += '		</span>';
		}
		html += '	</span>';

		if (this.list_obj.headers.displayed == 'True') {

			list_name = list_obj.name
			html += '	<div id="'+list_name+'_list_header"> <!-- start '+list_name+'_list_header -->';

			$.each(this.list_obj.headers.items, function(k, item) {
				if (item.sortable == 'True') {
					if (sort_column == item.name) {
						sort_html = '<img src="/images/12x12/sort_'+order+'.png" alt="'+order+' order image" />';
					}
					else {
						sort_html = '';
					}

					html += '<div class="'+list_name+'_header_'+item.name+' '+list_name+'_header_item list_header_item" id="'+item.name+'" value="'+reverseorder+'">';
					html += '	<div class="user_header_content">';
					html += '		<a title="'+_("Click to sort on this column.")+'">';
					html += '			'+item.content;
					html += '		</a>';
					html += '	</div>';
					html += '	<div class="item_header_sort">';
					html += '		'+sort_html;
					html += '	</div>';
					html += '</div>';
				}
				else {
					html += '<div class="'+list_name+'_header_'+item.name+' list_header_item">';
					html += '	<div class="user_header_content">';
					html += '		<a title="'+_("Click to sort on this column.")+'">';
					html += '			'+item.content;
					html += '		</a>';
					html += '	</div>';
					html += '	<div class="item_header_sort">';
					html += '		&nbsp';
					html += '	</div>';
					html += '</div>';
				}
			});
			html += '</div> <!-- end '+list_name+'_list_header -->';
		}
		return html;
	}

	// function sort_items_list
	//	sort_way : string = 'asc' or 'desc'
	//	sort_items : string = attribute to sort the list with
	// sort and display the list
	this.sort_items_list = function(sort_way, item_sort) {

		sort_items = [item_sort];
		if (item_sort != this.main_attr) {
			sort_items.push(this.main_attr);
		}

		users_list_return = this.my_sort(sort_way, sort_items);
		//console.log(users_list_return);

		hidden = 0;
		$.each(users_list_return, function(key, obj) {
			if($('#'+this.main_attr+'_'+$(obj).attr(_LIST.main_attr)).is(':hidden')) { hidden += 1; }
		});

		// 75ms * number of visible elements seems fine, because a human expects
		// 75ms * number of visible elements seems fine, because a human expects
		// a list to be sorted faster if there are fewer elements.
		effect_duration = 75 * (users_list_return.length - hidden);


		// but we need to floor and ceil the values, else it can be
		// too long or too fast to see the effect.
		if (effect_duration == 0)
			effect_duration = 100;

		if (effect_duration > 750)
			effect_duration = 750;

		final_width = $('#'+_LIST.name+'_list_header').width();

		css_classes = Array({
				'del_classes' : 'users_row_odd row_odd odd',
				'add_classes' : 'users_row_even row_even even'
			}, {
				'add_classes' : 'users_row_odd row_odd odd',
				'del_classes' : 'users_row_even row_even even'
			})
		cpt=0;
		$.each(users_list_return, function(key, obj) {
			the_div = $('#'+_LIST.main_attr+'_'+$(obj).attr(_LIST.main_attr));

			final_position   = cpt*51+'px';
			current_position = the_div.css('margin-top');

			if (final_position == current_position) {
				the_div.css({ 'z-index': 5000 });
			} else {
				the_div.css({ 'z-index': key });
			}
			the_div.stop(true, true).animate({ 'margin-top': final_position },
							effect_duration * Math.random(),
							'swing').width(final_width);

			if(! the_div.is(':hidden')) {
				the_div.find('.odd_even_typed').each(function() {
					classes = css_classes[cpt%2];
					$(this).removeClass(classes.del_classes);
					$(this).addClass(classes.add_classes);
				});
				cpt +=1;
			}
		});
	}
}
