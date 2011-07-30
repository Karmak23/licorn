/*
* Licorn WMI menu javascript
*
* Copyright (C) 2011 Robin Lucbernet <robinlucbernet@gmail.com>
* Licensed under the terms of the GNU GPL version 2
*/

$(document).ready(function() {
	// deal with links which need to display something in the sub_content part
	/*$(".link_display_in_sub_content").each(function() {
		//$(this).attr("href", $(this).attr("href")+'/ajax');
		//$(this).attr('onClick', 'return false;');
		$(this).click(function() {
			if (sub_content_locked) {
				stop_user_sub_content_lock();
			}
			sub_content_locked = true;
			change_content_of_sub_content_main($(this).attr('href'));
		});
	});*/
	// deal with menu sublinks opacity
	// TODO : do this with css
	/*$(".menu-content-item").click(function() {
	 *	$(".menu-content-item").css({'opacity' : 0.5});
	 *	$(this).css({'opacity' : 1});
	 *});
	*/



	//console.log("BLABLIBLU");

	/*
	 *	menu
	 */


	$(".menu-content").hide();
	// we need to mark the current page
	current_page = window.location.pathname;
	if (current_page == "/") current_page = "HOME";
	//console.log('current page = '+current_page);
	$(".menu-item").each(function() {
		link = $(this).find(".menu-title").find('.menu_link').attr('href');
		if (link == "/") link = "HOME";
		//console.log("its link ="+ link );
		if (current_page.match(link)) {
			//console.log(link+" == "+current_page);
			$(this).find(".menu-text").addClass("menu-current");
			$(this).find(".menu-back").css({'background':"0"});
			$(this).css({'background':"url('/images/fleche_bleue.png') no-repeat"});
			$(this).find(".menu-content").delay(250).slideDown();
			//$(this).find(".menu-out").hide();
		}
		else {
			//console.log(link+" != "+current_page);
		}
	});

	// menu's horizontal slide
	//$('.menu-over').hide();
	//make_my_menu_sliding("#mainnav .menu-item");
	//make_my_menu_sliding("#auxnav li");

	// menu animation
	$(".menu-text").hover(function() {
		if (! $(this).hasClass('menu-current')) {
			$(this).stop(true, true).animate({'background-position': '0px top' }, 250, 'easeOutCubic');
		}
	}, function() {
		if (! $(this).hasClass('menu-current')) {
			$(this).stop(true, true).animate({'background-position': '-220px top' }, 250, 'linear');
		}
	});
});
