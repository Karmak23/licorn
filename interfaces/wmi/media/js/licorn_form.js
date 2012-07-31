$(document).ready(function() {

	console.log('licorn_form.js loaded')

	$('input[type=text].instant').keyup(function() {
		$.get($(this).data('instant-url')+$(this).val())
	})


})

