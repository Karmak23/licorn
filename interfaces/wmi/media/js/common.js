function emit(handler, id, value) {
	$('.'+handler).each(function() {
		if ($(this).data('id') === id) {
			$(this).html(value)
		}
	});
}

var page_cleaner_interval;

function update_instance(model, iid, new_html, callback) {
	// This function will work with anything, but best for replacing a <tr>
	// with a new one, already rendered.
	//
	
	new_  = $(new_html);

	table = $('#model_' + model + '_table');

	old   = $('#' + model + '_' + iid);

	
	if (old.length) {
		// this instance was already known.
		// remove the old corresponding ROW.
		old.attr('id', 'old_' + old.attr('id'));
		old.addClass('to-remove');

		old.before(new_);

		old.hide();

	} else {
		// we've got a new challenger, insert it at the end.
		last = table.find('tr:last');
		last.after(new_);

		if (last.hasClass('no-data')) {
			// we previously had no data in the table.
			// Mark the place-holder as removable now
			// that we have.
			last.addClass('to-remove');
			last.hide();
		}

		// Update the total number of elements.
		count = $('#model_' + model + '_count');
		count.html(parseInt(count.html()) + 1);
	}

	new_.show();

	if (callback != null) {
		// if a callback is set, call it with the new row as parameter
		if (typeof(callback) == "string") {
			var fn = window[callback];
			fn(new_);
		}
		else {
			callback(new_);
		}

	}

	/* OLD CALBACK 
	// don't forget links, modals, popoversâ€¦
	setup_everything(new_);

	//console.log('re-sort on ' + [table.get(0).config.sortList]);
	*/
	
	// re-sort the table.
	table.trigger("update")
		.trigger("sorton", [table.get(0).config.sortList]);
	  //.trigger("appendCache");
	  //.trigger("applyWidgets");
	

	// remove old stuff marked as such.
	page_cleaner();
}
function popover_placement(objekt, parent) {

	if ($(parent).hasClass('popover-left')){
		return 'left';

	} else if ($(parent).hasClass('popover-bottom')){
		return 'bottom';

	} else if ($(parent).hasClass('popover-top')){
		return 'top';

	} else {
		return 'right';
	}
}
function table_sort_extractor(node) {
	s = $(node).data('sort');

	if (typeof s === 'undefined') {
		return node.innerHTML;

	} else {
		return s;

	}
}
function page_cleaner() {
	// most of the time, this operation fails when run from inside the
	// update_instance() function, but succeeds when run from outside.
	// Don't ask me why. But it has to be done, else the page is more
	// and more cluttered when time passes by.

	try {
		$('body').find('.to-remove').each(function(){
			$(this).remove();
			
		});

	} catch (err) {
		try {
			console.log('page_cleaner: ' + err);

		} catch (err) {
			// nothing. Silently ignored.
		}
	}
}
function setup_table_sorter(sort_list) {
	if (sort_list == null) { sort_list = [[0, 0], [1, 0]]; }
	$("table.sortable").tablesorter({
		sortList: sort_list,
		textExtraction: table_sort_extractor,
	});
	//.bind('sortEnd', function(sorter) {
	//	currentSort = sorter.target.config.sortList;
	//});
}
function setup_table_filter(table_element, input_element) {
	input_element.keyup(function(event) {
		$.uiTableFilter( table_element, input_element.val() );
	});
}
function setup_table_row_selectable(table_element, active_class, ignore_class) {
	// selectable rows
	table_element.iselectable({
		active: active_class,
		exclude: ignore_class
	});
}
function get_selected_rows(table_element, active_class) {
	rows = [];
	$.each(table_element.children(), function(index, row) {
		if ($(row).hasClass(active_class)) {
			rows.push(row);
		}
	});
	return rows;
}
function setup_table_row_doubleclick(elements, _function) {
	// double click on a row will call _function with td as parameter
	elements.each(function(index, row) {
		$(row).dblclick(function(event) {
			_function($(event.target).parent());
		});
	});
}
function setup_popovers(parent){

	if (typeof parent == 'undefined') {
		parent = $('body');
	}

	// We need the "click" for touch interfaces to be able to close
	// twitter popovers. Not needed for clickovers, though, which
	// work perfectly.
	// https://github.com/twitter/bootstrap/issues/3417
	parent.find('[rel="popover"]').popover({
			placement: popover_placement }).click(function(e) {
		$(this).popover('toggle');
	});
}
function setup_clickovers(parent) {

	if (typeof parent == 'undefined') {
		parent = $('body');
	}

	parent.find('[rel="clickover"]').each(function(){

		if ($(this).hasClass('iframed')) {
			$(this).clickover({ width: 800, height: 450, placement: popover_placement });

		} else if ($(this).hasClass('clickover-auto-close')) {
			$(this).clickover({ auto_close: 5000, placement: popover_placement });

		} else {
			$(this).clickover({ placement: popover_placement });
		}
	});
}
function setup_delayed_loaders(parent) {
	// https://github.com/twitter/bootstrap/issues/2380

	if (typeof parent == 'undefined') {
		parent = $('body');
	}

	parent.find('.delayed-loader').each(function() {
		$(this).click(function(){
			target = $('body').find($(this).attr('href')).find('.delayed-target');

			//console.log('(delayed until now) loading of ' + target.attr('delayed-src'));

			target.attr('src', target.attr('delayed-src'));
		});
	});
}
function setup_everything(parent) {

	setup_popovers(parent);
	setup_clickovers(parent);
	setup_delayed_loaders(parent);
}
function setup_auto_cleaner() {
	// every 10 minutes, the page is cleaned from old and orphaned elements.

	page_cleaner_interval = setInterval(page_cleaner, 600000);
}

/* this is now a librairy 

$(document).ready(function() {
	setup_everything();

	setup_table_sorter();
	setup_auto_cleaner();

});*/

function reload_div(div_id, html, no_effect) {
	div = $(div_id);

	// orig: true2 > false2 	> can made the div not fadeIn() completely
	//								in some fast-mouse-movement cases.
	// true/false > false/true 	> idem
	// true/true > false/true 	> idem
	// true2 > nothing 			> seems perfect.

	if (no_effect === undefined) {
		div.stop(false, false).fadeOut('fast', function(){
			$(this).html(html).stop(false, true)
				.fadeIn('fast');
		});
	} else {
		div.stop(true, false).html(html);
	}
}