
function password_helpers(content) {
	//console.log("init password helpers")
	//console.log(content.find('input:password'))

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
		console.log('keyup')
		clearTimeout(url_tim)

		var empty = false;
		content.find('input:password').each(function() {
			if ($(this).val() == '') {
				empty = true;
			}
		});
		console.log('One is empty ', empty)
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
					console.log('match')
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
					passwords_match = true;
				}
				else {
					pwd_check.html('<img src="/media/images/16x16/check_bad.png"/>');
					passwords_match = false

					pwd_strenght.html('')
					console.log('no match')

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

	function do_sort(div, sort_item) {
		console.log("do_sort on ", sort_item)
		tab = $('#'+div+' '+elements)
		console.log($(tab))
		tab.sort(function(a, b) {
			//console.log($(a).data('rel'), $(b).data('rel'))
			if (sort_item == 'alpha') {

				a = $(a).find('.'+alpha_search).text().toLowerCase()
				b = $(b).find('.'+alpha_search).text().toLowerCase()

				return sort_alphanum(a, b);





			}
			else if (sort_item == 'relation') {
				arel = $(a).data('rel')
				brel = $(b).data('rel')

				// sort on relationship, and, if equal sort string
				if (arel == brel) {
					a = $(a).find('.'+alpha_search).text().toLowerCase()
					b = $(b).find('.'+alpha_search).text().toLowerCase()

					return sort_alphanum(a, b);
				}
				else {
					if (arel > brel) {
						return -1
					}
					else {
						return 1
					}



					return ($(a).data('rel') - $(b).data('rel'))
				}



			}
		})
		if (sort_item == 'relation') {
			//$.fn.reverse = [].reverse;
			//tab = tab.reverse();
		}

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
