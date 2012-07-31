$(document).ready(function() {
	console.log('licorn_form.js loaded')

	$('.instant_apply_textbox').keyup(function() {
		// who are we editing ?
		handler_id = $(this).data('handler-id')
		handler    = $(this).data('handler')

		$.get($(this).data('instant-url')+$(this).val(), function(data) {
			$('.handler').each(function() {
				if ($(this).data('handler-id') == handler_id) {
					if ($(this).data('handler') == handler) {
						$(this).html(data)
					}
				}
			})
		})
	})
})