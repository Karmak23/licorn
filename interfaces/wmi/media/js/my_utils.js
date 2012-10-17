
function password_helpers(content) {
	// setup password helpers such as 'Password matching', 'Password strenght',
	// 'Password generator'

	// setup interface, add  the #check_pwds and #pwd_strenght spans
	pwd_strenght = $('<span></span>')
	pwd_check = $('<span></span>')

	generate_pwd = $('<span><img id="generate_pwds" src="/media/images/16x16/generate.png" alt="'+ gettext("Generate passwords") +'"/></span>')
	generate_pwd.clickover({
		title : gettext("Random password generator"),
		content : '',
	})
	$.get('/users/generate_pwd/', function(html) {
		generate_pwd.attr("data-content", html);
	})

	content.find("input:password:first").parent().append(generate_pwd).append(pwd_strenght)
	content.find("input:password:last").parent().append(pwd_check)

	var url_tim;
	content.find('input:password').keyup(function() {

		clearTimeout(url_tim)

		var one_password_empty = false;
		content.find('input:password').each(function() {
			if ($(this).val() == '') {
				one_password_empty = true;
			}
		});

		// while one of the two password field is empty do not do anything.
		if ( !one_password_empty ) {
				var first = true;
				var passwords_match = true;
				content.find('input:password').each(function() {
					if (first) {
						pwd = $(this).val();
					}
					else {
						if (pwd != $(this).val()) { passwords_match = false; }
					}
					first = false;
				});
				if ( passwords_match ) {
					// if passwords match, check password strenght and present it to the user
					pwd_check.html('<img src="/media/images/16x16/check_ok.png"/>');

					$.get("/users/check_pwd_strenght/"+pwd, function(html) {
						if (html != pwd) {
							pwd_strenght.html("<div class='check_pwd_recap' style='color:red;'>" + html +"</div>")
						}
						else {
							pwd_strenght.html("<div class='check_pwd_recap' style='color:green;'> Mot de passe sécurisé </div>" )
						}
						url_tim = setTimeout(function() {
							$.get($('input:password:last').data('instant-url')+$('input:password:last').val())
						}, 1000);
					});
				}
				else {
					// passwords not matching
					pwd_check.html('<img src="/media/images/16x16/check_bad.png"/>');
					pwd_strenght.html('')
				}
		}
		else {
			content.find('#check_pwds').html('')
			content.find('#pwd_strenght').html('')
		}
	});

	generate_pwd.click(function() {
		var pwd_generated = null;
		$.get('/users/generate_pwd/', function(html) {
			generate_pwd.attr("data-content", html);
		})
		$('#confirm_generated_password').click(function(event) {
			content.find('input:password').val($('#generated_password').val()).keyup();
		})

	});
}


var reA = /[^a-zA-Z]/g;
var reN = /[^0-9]/g;

function sort_alphanum(a, b) {
	var aA = a.replace(reA, "");
    var bA = b.replace(reA, "");
    if(aA === bA) {
        var aN = parseInt(a.toString().replace(reN, ""), 10);
        var bN = parseInt(b.toString().replace(reN, ""), 10);
        return aN === bN ? 0 : aN > bN ? 1 : -1;
    } else {
        return aA > bA ? 1 : -1;
    }
}


var tab_sort = { "alpha": true, "relation": false}

function setup_sort_items(elements, sort_items, alpha_search) {
	// sort elements in differents ways

	// initialize interface item
	$.each(sort_items, function(i, item) {
		// setup interface
		if (tab_sort[$(item).data('sort')]) {
			$(item).addClass('active')
		}
		else {
			$(item).removeClass('active')
		}
	})
	// on click, start sorting
	$(sort_items).click(function(e) {
		do_sort($(this).data('id'), $(this).data('sort'));
	})

	// function that make the sort
	function do_sort(div, sort_item) {

		tab = $('#'+div+' '+elements)
		tab.sort(function(a, b) {

			// we currently have two way to sort : alphanumeric and by relationship
			if (sort_item == 'alpha') {
				a = $(a).find('.'+alpha_search).text().toLowerCase()
				b = $(b).find('.'+alpha_search).text().toLowerCase()

				return sort_alphanum(a, b);
			}

			else if (sort_item == 'relation') {
				arel = $(a).attr('data-rel')
				brel = $(b).attr('data-rel')

				// sort on relationship, and, if equal sort alphanumeric way
				if (arel == brel) {
					a = $(a).find('.'+alpha_search).text().toLowerCase()
					b = $(b).find('.'+alpha_search).text().toLowerCase()

					return sort_alphanum(a, b);
				}
				else {
					// bigger relation in top
					if (arel > brel) {
						return -1
					}
					else {
						return 1
					}
				}
			}
		})

		// hide elements, re-append them in the good order and finally show them
		$('#'+div+' '+elements).hide()

		$.each(tab, function(i, item) {
			$('#'+div).append($(item))
		})

		$('#'+div+' '+elements).show()
	}

}
