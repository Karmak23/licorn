/*
* Licorn WMI menu javascript
*
* Copyright (C) 2011-2012 Olivier Cortès <olive@licorn.org>
* Copyright (C) 2011-2012 META IT S.à.S http://meta-it.fr/
* Copyright (C) 2011 Robin Lucbernet <robinlucbernet@gmail.com>
*
* Licensed under the terms of the GNU GPL version 2
*/

function setup_ajaxized_modal_loaders() {
	$('.ajax-load-modal').click(function(){
		the_link = $(this);
		$.get(the_link.attr('href'), function(html) {
			$('#modal').html(html).modal();
		})
	})
}

function setup_ajaxized_div_loaders(css_selector, div_selector) {

	$(css_selector).click(function() {
		//console.log('click');
		//console.log($(div_selector));
		//console.log($.get($(this).attr('href')));

		the_link = $(this);

		$.get(the_link.attr('href'), function(html) {

			//console.log('reload '+ div_selector);

			reload_div(div_selector, html);

			if (the_link.hasClass('ajax-push-setup')) {
				push_setup(the_link.attr('href'));
			}

		});
		return false;
	});
}
function setup_ajaxized_links(selector, exclude) {

	if (selector == undefined) {
		selector = '.ajax-sidebar-menuitem';
	}

	if (exclude == undefined) {
		exclude = [];
	}

	$(selector).each(function() {

		//console.log('background ' + $(this).attr('href'));

		should_apply   = true;
		current_target = $(this);

		exclude.forEach(function(css_klass) {
			if (current_target.hasClass(css_klass)) {
				should_apply = false;
			}
		});

		if (should_apply) {
			$(this).click(function() {

				href_url = $(this).attr('href');

				// run the href link action in the background.
				$.get(href_url, function(data) {

						//console.log('ajaxized! ' + href_url);

						return true;
					});

				// don't follow the link the normal way.
				return false;
			});
		}
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

	//console.log(selector);

	$(selector).each(function() {

		//console.log($(this).attr('target'));

		if ($(this).attr('target') == undefined){

	        $(this).click(function() {

				//console.log($(this));

				next_location = this.href;

				// slide the current menu up
				// TODO: make the following code be done in the callback function
				// of the menu slide up, else the stream close and the return true
				// will be done too early.

				// close the push stream.
				//stream_close();

				current = $('.menu-current');

				if (current.length) {
						current.parent().parent().parent()
							.find(".menu-content").slideUp(function() {
								head_over_to(next_location);
							});
				} else {
					// jQuery returned no selection. We could be in the 404
					// template, where there can be no current menu if the
					// address is really bad. We should JUST MOVE!

					head_over_to(next_location);
				}

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
	setup_ajaxized_links('.ajax-sidebar-menuitem', ['ajax-load-content',
		'ajax-load-main-content', 'ajax-load-sub-content', 'ajax-menu-link-item']);

	// setup (main,sub)content special loaders.
	setup_ajaxized_div_loaders('.ajax-load-content', '#content');
	setup_ajaxized_div_loaders('.ajax-load-main-content', '#main_content');
	setup_ajaxized_div_loaders('.ajax-load-sub-content', '#sub_content');

	setup_ajaxized_modal_loaders()

	setup_ajaxized_location_loaders('.ajax-menu-link-item');

	// NOTE: no need to "re-setup" confirms, they are standard links too.
	// They should have the 2 CSS attributes (link + confirm).
	//setup_ajaxized_links('.ajax-sidebar-menuitem-confirm');

	// WARNING: order matters !
	//'click' must be defined before 'confirm'.
	setup_ajaxized_confirms('.ajax-sidebar-menuitem-confirm');

	setup_ajaxized_dialogs('.ajax-sidebar-menuitem-dialog');

	//console.log('Menu links setup OK');
});
