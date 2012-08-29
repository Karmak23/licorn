
function setup_popover_clicks() {
	$(document).click(function(event) {

		if (! $(event.target).hasClass('no-click-event')) {

			//console.log('clickkkkkkkk ', event.target)

			$('.popover').each(function(i, popover) {

				//console.log("hidden ", $(popover).is(':hidden'));

				// If the popover is not hidden, we will close it but we need
				// to correctly set the checkbox state.
				if (! $(popover).is(':hidden')) {

					var share_id = $(popover).find('#share_id').attr('value');
					var share_name = $(popover).find('#share_id').attr('name');
					var checkbox = $('#id_checkbox_'+share_id);

					$.get('/shares/'+share_name+'/accepts_uploads', function(response) {

						if (response == "False") {
							// The popover has been close but the
							// share still not accept uploads.
							checkbox.attr('checked', false);
						}
						else {
							checkbox.attr('checked', 'checked');
						}

						// make the change appear in the interface
						checkbox.change();
					})
				}
			});
		}
	});
}
function setup_action_buttons() {

	$('.action_button').each(function() {
		$(this).click(function() {

			thelink = $(this).parent().attr('action');

			$.get(thelink, function(data){
				//console.log(thelink + ' returned ' + data);
			});
		});
	});
}
$(document).ready(function() {

	setup_action_buttons();

	// this one comes from main.js
	setup_ajaxized_links('.ajax-shares-link');

	setup_popover_clicks();
});
