
function password_helpers(content) {
	//console.log("init password helpers")
	//console.log(content.find('input:password'))
	content.find('input:password').keyup(function() {
		//console.log('keyup')

		var empty = false;
		content.find('input:password').each(function() {
			if ($(this).val() == '') {
				empty = true;
			}
		});

		// while one of the two password field is empty do not do
		// anything.
		if ( !empty ) {
				var first = true;
				var match = true;
				content.find('input:password').each(function() {
					if (first) {
						pwd = $(this).val();
					}
					else {
						if (pwd != $(this).val()) { match = false; }
					}
					first = false;
				});
				if ( match ) {
					//if they match check password strenght
					content.find('#check_pwds').html('<img src="/media/images/16x16/check_ok.png"/>');
					$.get("/users/check_pwd_strenght/"+pwd, function(html) {
						if (html != pwd) {
							content.find('#pwd_strenght').html("<div class='check_pwd_recap' style='color:red;'>" + html +"</div>")
						}
						else {
							content.find('#pwd_strenght').html("<div class='check_pwd_recap' style='color:green;'> Mot de passe sécurisé </div>" )
						}
					});
					passwords_match = true;
				}
				else {
					content.find('#check_pwds').html('<img src="/media/images/16x16/check_bad.png"/>');
					passwords_match = false

					content.find('#pwd_strenght').html('')
				}
		}
		else {
			content.find('#check_pwds').html('')
			content.find('#pwd_strenght').html('')
		}
	});

	$('#generate_pwds').click(function() {
		var pwd_generated = null;
		$.get('/users/generate_pwd/', function(pwd) {
			pwd_generated = pwd
			gen_pwd_dialog = new dialog(gettext("Random password generator"),
				strargs(gettext("<br />The generated password is &ldquo;&nbsp;<strong class=\"bigger\">%1</strong>&nbsp;&rdquo;. If you want to use it, just hit the <code>Confirm</code> button, and remember it."), [pwd_generated]),
				true, function() {
					content.find('input:password').val(pwd_generated).trigger('keyup');
			});
			gen_pwd_dialog.show();
		})

	});
}

var tab_sort = { "alpha": true, "relation": false}
	
function setup_sort_items(elements, sort_items, alpha_search) {
	console.log('setup_sort_items', elements, sort_items)

	$.each(sort_items, function(i, item) {
		console.log(item, tab_sort, $(item).data('sort'))
		// setup interface
		if (tab_sort[$(item).data('sort')]) {
			$(item).addClass('active')
		}
		else {
			$(item).removeClass('active')
		}
	})
	$(sort_items).click(function(e) {
		
		do_sort($(this).data('id'), $(this).data('sort'));

	})
	//do_sort();

	function do_sort(div, sort_item) {
		console.log("do_sort on ", sort_item)
		tab = $('#'+div+' '+elements)
		console.log($(tab))
		tab.sort(function(a, b) {
			//console.log($(a).data('rel'), $(b).data('rel'))
			if (sort_item == 'alpha') {
				if ($(a).find('.'+alpha_search).text().toLowerCase() < $(b).find('.'+alpha_search).text().toLowerCase()) {
					return -1
				}
				else if ($(a).find('.'+alpha_search).text().toLowerCase() > $(b).find('.'+alpha_search).text().toLowerCase()) {
					return 1
				}
				else {
					return 0
				}
			}
			else if (sort_item == 'relation') {
				return ($(a).data('rel') - $(b).data('rel'))
			}
		})
		if (sort_item == 'relation') {
			$.fn.reverse = [].reverse;
			tab = tab.reverse();
		}
		console.log('sorted', $(tab))

		//$.each(tab, function(i, item) {
		//	console.log($(item))
		//})

		$('#'+div+' '+elements).hide()
		$.each(tab, function(i, item) {
			$('#'+div).append($(item))
		})

		$('#'+div+' '+elements).show()






	}

}
