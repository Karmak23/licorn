$(document).ready(function() {

	var submit_callback_called = false;

	$('#logo').delay(500).fadeIn('slow');

	$('h2').delay(500).fadeIn('slow');

	$('#real_form_wrapper').delay(750).slideDown('slow', function(){
			$('#id_username').focus();
	});

	$('#login_form').submit(function(){

		if (submit_callback_called) {
			return true;

		} else {
			$('#login_form_wrapper').fadeOut('medium');

			$('#logo').delay(500).fadeOut('medium');

			form1 = $('#real_form_wrapper');
			cur_pos = form1.position().left;

			// we've got to manually set margin-left to the current
			// position, else it will start sliding from 0px — producing
			// a visual glitch, because margin-left is currently 'auto'.
			form1.css('margin-left', cur_pos)
				.animate({marginLeft: '1000px'}, 'medium')
				.delay(500, function(){
					$('#login_form').submit();
				});

			submit_callback_called = true;
			return false;
		}
	});
});
