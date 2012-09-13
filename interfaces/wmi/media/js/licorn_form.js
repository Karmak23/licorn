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
		console.log('instant click')
		$.get($(this).data('instant-url'))
	});


	$(div).find('.popover_item').click(function() {
			// update the current popover
			user_id = $(this).attr('id');
			new_rel = $(this).attr('value');

			div = $('#sub_content').find('#'+user_id).filter('.click_item');
			div.find('.item_hidden_input').attr('value', ''); // erase old membership
			div.find('input[name$="'+new_rel+'_users"]').attr('value', user_id); // update new membership


			// IF MODE IS NEW
			// visual feedback on users because no instant_apply in new
			//update_relationship('user', user_id, null, new_rel) ;

			//close the popover
			$(".click_item#"+user_id).popover('hide');
		});

}

var relationships = [ 'no_membership', 'guest', 'member', 'resp' ]

function update_relationship(item_id, rel_id) {
	/* Update the relationship of an element */

	new_rel = relationships[rel_id];
	div = $(".click_item#"+item_id);
	popover = $('.popover_item').filter('#'+item_id).parent();
	hidden_input = div.find('input[name$="' + new_rel + '_' + name + 's"]');

	popover.children().show();
	popover.find('.rel_'+new_rel).hide();

	div.attr('value', new_rel)
	div.find('.item_hidden_input').attr('value', ''); // erase old membership
	hidden_input.attr('value', i); // update new membership

	div.find('.item_title')
		.removeClass('no_membership_bkg guest_bkg member_bkg resp_bkg incomplete_bkg')
		.addClass(new_rel+'_bkg');
}

