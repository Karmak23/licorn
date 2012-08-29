/*
* Licorn WMI main javascript
*
* Copyright (C) 2011 Olivier Cortès <olive@deep-ocean.net>
* Copyright (C) 2011 META IT S.à.S <dev@meta-it.fr>
* Copyright (C) 2011 Robin Lucbernet <robinlucbernet@gmail.com>
* Licensed under the terms of the GNU GPL version 2
*/


var DEBUG = false;
var DEBUG_USER = false;
var DEBUG_GROUP = false;
var DEBUG_UTILS = false;

// these 2 are used in utils.js but must be here to be able
// to cancel them on $(document).keyup('ESC').
var instant_apply_timeout_textbox;
var instant_apply_timeout_pwd;

var body = null;
var body_stay_waiting = false;

function body_wait(maintain) {

	if (typeof maintain === 'undefined'){
		maintain = false;
	}

	if (!body.hasClass('waiting')) {
		body.addClass('waiting');
	}

	if (maintain) {
		body_stay_waiting = true;
	}
}
function body_unwait(remove) {

	if (typeof remove === 'undefined'){
		remove = false;
	}

	if (body.hasClass('waiting')) {

		if(body_stay_waiting) {

			if (remove) {
				setTimeout(function() {
					body_stay_waiting = false;
					body.removeClass('waiting');
				}, 500);
			}
		} else {
			body.removeClass('waiting');
		}
	}
}

function setup_ajax_togglers(selector) {

	if (typeof selector == 'undefined' || selector == '') {
		selector = 'html';
	}
	// multiple selectors in jQuery: http://stackoverflow.com/questions/1047992/jquery-selector-and-operator

	$(selector).find('.ajax-slider-toggle-master').each(function() {
		$(this).click(function() {
			$('#' + $(this).attr('id') +'.ajax-slider-toggle-slave').slideToggle();
		});
	});
}

function setup_ajax_initially_hidden(selector) {

	if (typeof selector == 'undefined' || selector == '') {
		selector = 'html';
	}

	$(selector).find('.ajax-initially-hidden').hide();
}

function refresh_div(div, html, no_effect) {
	/* Compare the content of 2 divs, look for items with class='_refresh',
		find the same id in the new div, and replace content. */

	new_html = $(html);

	if (typeof no_effect == 'undefined' || no_effect) {
		div.find('._refresh').each(function() {
			$(this).html(new_html.find('#' + $(this).attr('id')).html());
		});

	} else {
		div.find('._refresh').each(function() {
			old_data = $(this).html();
			new_data = new_html.find('#' + $(this).attr('id')).html();

			if (new_data != old_data) {
				$(this).html(new_data)
					.animate({
						backgroundColor: $.Color("olive")
							.transition('transparent', 0.75) }, 250,
						function() {
							$(this).animate({
								backgroundColor: $.Color('transparent')
									.transition('transparent', 0.0) }, 1500);
							});
			}
		});
	}

	// Be sure the div is fully visible, in case the animation failed.
	div.css('opacity', 1.0);
}

function reload_div(div_id, html, no_effect) {
	div = $(div_id);

	// orig: true2 > false2 	> can made the div not fadeIn() completely
	//								in some fast-mouse-movement cases.
	// true/false > false/true 	> idem
	// true/true > false/true 	> idem
	// true2 > nothing 			> seems perfect.

	if (no_effect === undefined) {
		div.stop(false, false).fadeOut('fast', function(){
			$(this).html(html).stop(false, true)
				.fadeIn('fast');
		});
	} else {
		div.stop(true, false).html(html);
	}

	// be sure the div is fully visible, in case the animation failed.
	div.css('opacity', 1.0);
}

function lock_sub_content(item_id) {
	if (typeof item_id == 'undefined') { item_id = ''; }
	// lock the content, we generally set the value as the item id
	// to recover it easily
	$('#sub_content').addClass('locked');
	$('#sub_content').attr('value', item_id);
}
function unlock_sub_content() {
	$('#sub_content').removeClass('locked');
	$('#sub_content').attr('value', '');

	// don't crash is no search field in current page.
	try { $("#search_box").focus(); } catch (err) {};
}
function is_sub_content_locked() {
	return $('#sub_content').hasClass("locked");
}

function clear_sub_content_with_id(_id) {
	// the "value" attribute define the object_id (uid, gid ...)
	// of the current object locking the sub_content div
	if ($('#sub_content').attr('value') == _id) {
		reload_div('#sub_content', "");
		unlock_sub_content();
	}
}

$(document).ready(function() {

	// They are already hidden by default (class='hidden')
	//$('#dialog').hide();
	//$('#dialog-content').hide();
	//$('#notification').hide();

	setup_ajax_initially_hidden();
	setup_ajax_togglers();

	body = $('body');

	try {
		//$.preLoadCSSImages();
	} catch (err) {}

	$.ajaxSetup({
		timeout: 0,
	});
	push_setup();
});

$(document).keyup(function(e) {

  //if (e.keyCode == 13) { $('.save').click(); }     // enter

	if (e.keyCode == 27) {    // ESC

		var searchb = $('#search_box');

		if (searchb != [] && searchb.is(':focus') && searchb.val() != "") {
			searchb.val('');
			searchb.keyup();

		} else {
			unlock_sub_content();
			$('#sub_content').fadeOut();
			$('#sub_content').html();

			clearTimeout(instant_apply_timeout_textbox);
			clearTimeout(instant_apply_timeout_pwd);

			// don't crash is no row selected.
			try { unselect_row(); } catch (err) {};
		}
	}
});


function password_helpers(content) {
	//console.log("init password helpers")
	//console.log(content.find('input:password'))
	content.find('input:password').keyup(function() {
		//console.log('keyup')

		var empty = false;
		content.find('input:password').each(function() {
			if ($(this).val() == '') {
				empty = true;
			}
		});

		// while one of the two password field is empty do not do
		// anything.
		if ( !empty ) {
				var first = true;
				var match = true;
				content.find('input:password').each(function() {
					if (first) {
						pwd = $(this).val();
					}
					else {
						if (pwd != $(this).val()) { match = false; }
					}
					first = false;
				});
				if ( match ) {
					//if they match check password strenght
					content.find('#check_pwds').html('<img src="/media/images/16x16/check_ok.png"/>');
					$.get("/users/check_pwd_strenght/"+pwd, function(html) {
						if (html != pwd) {
							content.find('#pwd_strenght').html("<div class='check_pwd_recap' style='color:red;'>" + html +"</div>")
						}
						else {
							content.find('#pwd_strenght').html("<div class='check_pwd_recap' style='color:green;'> Mot de passe sécurisé </div>" )
						}
					});
					passwords_match = true;
				}
				else {
					content.find('#check_pwds').html('<img src="/media/images/16x16/check_bad.png"/>');
					passwords_match = false

					content.find('#pwd_strenght').html('')
				}
		}
		else {
			content.find('#check_pwds').html('')
			content.find('#pwd_strenght').html('')
		}
	});

	$('#generate_pwds').click(function() {
		var pwd_generated = null;
		$.get('/users/generate_pwd/', function(pwd) {
			pwd_generated = pwd
			gen_pwd_dialog = new dialog(gettext("Random password generator"),
				strargs(gettext("<br />The generated password is &ldquo;&nbsp;<strong class=\"bigger\">%1</strong>&nbsp;&rdquo;. If you want to use it, just hit the <code>Confirm</code> button, and remember it."), [pwd_generated]),
				true, function() {
					content.find('input:password').val(pwd_generated).trigger('keyup');
			});
			gen_pwd_dialog.show();
		})

	});
}

function generate_machine() {
	$.each($('.licorn_machine'), function(i, v) {
		mid = $(this).attr('id');

		$.get('/energy/generate_machine_html/'+mid, function(html) {
			$(v).before($(html));
		})
	})
}
