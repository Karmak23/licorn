
function init_instant_apply(page_name) {
	// instant apply mechanism initialize

	interval = 1000;

	form_div = $('#table')
	console.log("init_instant_apply")
	$('input:text').keyup(function() {
		//console.log('keyUp');
		clearTimeout(instant_apply_timeout_textbox);

		page='/'+page_name+'/mod/'+ form_div.attr('name') +'/' + $(this).attr('name') + '/' + $(this).val();
		//console.log(page);
		instant_apply_timeout_textbox = setTimeout(function(){
			$.get(page);
		}, interval);

	});

	$('input:checkbox').click(function() {
		checked = this.checked;
		if (this.checked == true) {
			checked = 'True';
		}
		else {
			checked = '';
		}
		page='/'+page_name+'/mod/'+ form_div.attr('name') +'/' + $(this).attr('name') + '/' + checked;
		//console.log(page);
		$.get(page);
	});

	$('input:password').keyup(function() {

		var empty = false;
		form_div.find('input:password').each(function() {
			if ($(this).val() == '') {
				empty = true;
			}
		});

		// while one of the two password field is empty do not do
		// anything.
		if ( !empty ) {
			clearTimeout(instant_apply_timeout_pwd);
			instant_apply_timeout_pwd = setTimeout(function(){
				var first = true;
				var match = true;
				form_div.find('input:password').each(function() {
					if (first) {
						pwd = $(this).val();
					}
					else {
						if (pwd != $(this).val()) { match = false; }
					}
					first = false;
				});
				if ( match ) {
					url = '/users/mod/'+ form_div.attr('name') +'/password/'+pwd;
					//console.log(url)
					$.get(url);
				}
				else {
					show_message_through_notification("Incorrect passwords");
				}
			}, interval);
		}
	});

	var instant_apply_timeout_select;
	form_div.find('select').change(function() {
		clearTimeout(instant_apply_timeout_select);
		page='/'+page_name+'/mod/'+ form_div.attr('name') +'/' + $(this).attr('name') + '/' + $.URLEncode($(this).val());
		//console.log(page);
		instant_apply_timeout_select = setTimeout(function(){
				$.get(page);
			}, interval);
	});

	var rel_ids = {
		'no_membership' : 0,
		'guest'         : 1,
		'member'        : 2,
		'resp'          : 3 }

	$('.instant_apply_click').click(function() {
		//console.log('group click '+$('#sub_content').attr('value'))
		div = $('#sub_content').find('#'+$(this).attr('id')).filter('.click_item');
		//console.log(div)
		div.find('.item_hidden_input').addClass('item_currently_selected');

		if (page_name == 'users') {
			url = ('/users/mod/' + $('#sub_content').attr('value')
					+ '/groups/' + $(this).attr('id')
					+ '/' + rel_ids[$(this).attr('value')]);
		}
		else {
			url = ('/groups/mod/' + $('#sub_content').attr('value')
					+ '/users/' + $(this).attr('id')
					+ '/' + rel_ids[$(this).attr('value')]);
		}
		//console.log(url)
		$.get(url);
	});
}