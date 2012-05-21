/*
* Licorn WMI menu javascript
*
* Copyright (C) 2011 Robin Lucbernet <robinlucbernet@gmail.com>
* Licensed under the terms of the GNU GPL version 2
*/

function setup_ajaxized_div_loaders(css_selector, div_selector) {

	$(css_selector).click(function() {
		//console.log('click');
		//console.log($(div_selector));
		//console.log($.get($(this).attr('href')));

		the_link = $(this);

		$.get(the_link.attr('href'), function(html) {
			reload_div(div_selector, html);

			if (the_link.hasClass('ajax-push-setup')) {
				push_setup(the_link.attr('href'));
			}

		});
		return false;
	});
}
function setup_ajaxized_links(selector) {

	if (selector == undefined) {
		selector = '.ajax-sidebar-menuitem';
	}

	$(selector).each(function() {

		//console.log('background ' + $(this).attr('href'));

		$(this).click(function() {

			href_url = $(this).attr('href');

			// run the href link action in the background.
			$.get(href_url, function(data) {
					return true;
				});

			// don't follow the link the normal way.
			return false;
		});
	});
}
function setup_ajaxized_confirms(selector) {

	if (typeof(selector) == 'undefined' || selector == '') {
		selector = '.ajax-sidebar-menuitem-confirm';
	}

	$(selector).each(function() {

		// WARNING: the click() must be defined *BEFORE* the confirm() is
		// called, else it doesn't work.

		if ($(this).has_confirm !== undefined)
			return;

		// make this kind of link a confirmed one (user needs to click OK).
        $(this).confirm({
            msg:gettext('Sure?') + '&nbsp;&nbsp;',
            //stopAfter:'ok',
            eventType:'click',
            dialogShow:'fadeIn',
            dialogSpeed:'slow',
            timeout: 3000,
            buttons: {
                wrapper:'<button></button>',
                ok:gettext('Yes'),
                cancel:gettext('No'),
                separator:'  '
            }
        });

		$(this).has_confirm = true;
    });
}
function setup_ajaxized_location_loaders(selector) {
	$(selector).each(function() {

		//console.log($(this).attr('target'));

		if ($(this).attr('target') == undefined){
	        $(this).click(function() {

				next_location = this.href;

				// slide the current menu up
				// TODO: make the following code be done in the callback function
				// of the menu slide up, else the stream close and the return true
				// will be done too early.

				// close the push stream.
				//stream_close();

				$('.menu-current')
					.parent().parent().parent()
					.find(".menu-content").slideUp(function() {
						head_over_to(next_location);
					});

				return false;
			});
		}
    });
}
function setup_ajaxized_dialogs(selector) {

	if (typeof(selector) == 'undefined' || selector == '') {
		selector = '.ajax-sidebar-menuitem-dialog';
	}

	$(selector).each(function() {

		// avoid launching 2 dialogs from the same link.
		if ($(this).has_dialog !== undefined)
			return;

		$(this).click(function() {

			mylink = $(this).attr('href');

			// create a dialog with content coming from the server side,
			// from an URL creafted from the final action URL.
			$.get(mylink + '/dialog', function(dialog_data) {

				mydialog = new dialog(
							$(dialog_data).find('.dialog_title').html(),
							$(dialog_data).find('.dialog_content').html(),
							true, function() {
								// WARNING: don't serialize $('.dialog_content').find(form),
								// it will always be the "not clicked one". We mut get the
								// 'real' one from the current document, not the text-only
								// one we got in the ajax-request-result.
								$.post(mylink, $('form#dialog_form').serialize());
						});
				mydialog.show();
			});
		});

		$(this).has_dialog = true;
    });
}

$(document).ready(function() {

	$(".menu-content").hide();

	// we need to mark the current page
	current_page = window.location.pathname;

	if (current_page == "/") current_page = "HOME";

	$(".menu-item").each(function() {
		link = $(this).find(".menu-title").find('.menu_link').attr('href');

		if (link == "/")
			link = "HOME";

		if (current_page.match(link)) {

			$(this).find(".menu-text").addClass("menu-current");
			$(this).find(".menu-back").css({'background':"0"});
			$(this).css({'background':"url('/media/images/fleche_bleue.png') no-repeat"});
			$(this).find(".menu-content").delay(250).slideDown();
		}
	});

	// menu animation
	$(".menu-text").hover(function() {
		if (! $(this).hasClass('menu-current')) {
			$(this).stop(true, false).animate({ backgroundPositionX: 0 }, 500, 'easeOutCubic');
		}
	}, function() {
		if (! $(this).hasClass('menu-current')) {
			$(this).stop(true, false).animate({ backgroundPositionX: -220 }, 500, 'linear');
		}
	});

	// Setup base "normal links". Items which have CSS attr 'ajax-sidebar-menuitem'
	setup_ajaxized_links();

	// setup (main,sub)content special loaders.
	setup_ajaxized_div_loaders('.ajax-load-content', '#content');
	setup_ajaxized_div_loaders('.ajax-load-main-content', '#main_content');
	setup_ajaxized_div_loaders('.ajax-load-sub-content', '#sub_content');

	setup_ajaxized_location_loaders('.ajax-menu-link-item');

	// NOTE: no need to "re-setup" confirms, they are standard links too.
	// They should have the 2 CSS attributes (link + confirm).
	//setup_ajaxized_links('.ajax-sidebar-menuitem-confirm');

	// WARNING: order matters !
	//'click' must be defined before 'confirm'.
	setup_ajaxized_confirms('.ajax-sidebar-menuitem-confirm');

	setup_ajaxized_dialogs('.ajax-sidebar-menuitem-dialog')
});
