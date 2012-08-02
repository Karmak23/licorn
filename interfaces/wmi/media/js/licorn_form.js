$(document).ready(function() {

	var instant_timeout;
	var instant_interval = 1000; // 1 sec

	$('input[type=text].instant').keyup(function() {
		clearTimeout(instant_timeout);
		instant_textbox = $(this)
		instant_timeout = setTimeout(function(){
			$.get(instant_textbox.data('instant-url')+instant_textbox.val())
		}, instant_interval);
	})


})

