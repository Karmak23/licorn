/*
* Licorn WMI menu javascript
*
* Copyright (C) 2011 Robin Lucbernet <robinlucbernet@gmail.com>
* Licensed under the terms of the GNU GPL version 2
*/

$(document).ready(function() {
	$(".menu-content").hide();
	// we need to mark the current page
	current_page = window.location.pathname;
	if (current_page == "/") current_page = "HOME";
	
	$(".menu-item").each(function() {
		link = $(this).find(".menu-title").find('.menu_link').attr('href');
		if (link == "/") link = "HOME";
		
		if (current_page.match(link)) {
			
			$(this).find(".menu-text").addClass("menu-current");
			$(this).find(".menu-back").css({'background':"0"});
			$(this).css({'background':"url('/images/fleche_bleue.png') no-repeat"});
			$(this).find(".menu-content").delay(250).slideDown();
			
		}
	});

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
