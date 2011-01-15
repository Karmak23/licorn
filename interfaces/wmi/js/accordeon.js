jQuery().ready(function() {
	$(".accordion_toggle").next("div .accordion_content").hide();
	$(".accordion_toggle").click(function() {
		if ($(this).next("div .accordion_content").is(':hidden')) {
			$(".accordion_toggle").next("div .accordion_content:visible").slideUp()
			$(this).next("div .accordion_content").slideDown();
		}
		else {
			$(this).next("div .accordion_content").slideUp();
		}
	});
	
});
