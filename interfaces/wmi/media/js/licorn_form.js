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
	$('input[type=checkbox].instant').click(function() {
		clearTimeout(instant_timeout);
		instant_checkbox = $(this)
		console.log('instant_checkbox val ', instant_checkbox.is(':checked'))
		if (instant_checkbox.is(':checked')) {
			is_checked = "True"
		}
		else {
			is_checked = ""
		}
		instant_timeout = setTimeout(function(){
			console.log(instant_checkbox.data('instant-url')+is_checked)
			$.get(instant_checkbox.data('instant-url')+is_checked)
		}, instant_interval);
	})

	$('select.instant').change(function() {
		clearTimeout(instant_timeout);
		instant_select = $(this)
		
		instant_timeout = setTimeout(function(){
			$.get(instant_select.data('instant-url')+$.URLEncode(instant_select.val()))
		}, instant_interval);
	})
	

})

function init_instant_click(div) {
	$(div).find('.instant_click').click(function(){
		$.get($(this).data('instant-url'))
	});
}

var button_types = [ 'default', 'primary', 'success', 'danger', 'warning' ];
var get_relationship_img = [
	"",
	'<img src="/media/images/24x24/guest+3px.png"/>',
	'<img src="/media/images/24x24/member+3px.png"/>',
	'<img src="/media/images/24x24/resp+3px.png"/>',
	"",
]

function update_relationship(item_id, rel_id) {
	/* Update the relationship of an element */
	console.log('update', item_id, rel_id)

	// find the popover
	popover = $('#popover_'+item_id)
	
	// update the current click_item
	btn = $('#btn_'+item_id)
	console.log("btn", btn)
	btn.attr('data-rel', rel_id)
	btn.removeClass('btn-default btn-primary btn-success btn-danger btn-warning').addClass('btn-'+button_types[rel_id])

	//show all relationship and hide the current
	btn.find('.popover .instant_click').show()
	btn.find('.popover .rel_'+rel_id).hide()

	// update image
	btn.find('.rel_img').html(get_relationship_img[rel_id])
}

