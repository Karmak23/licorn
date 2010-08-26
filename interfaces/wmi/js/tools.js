/*
* JavaScript tools
*
* Copyright (C) 2006 Régis Cobrun <regis.cobrun@ryxeo.com>
* Licensed under the terms of the GNU GPL version 2
*/


/*
* Check all checkbox which have name which matches with slaves_regex. master is the id of the control which make the operation.
*/
function checkAll(master, slaves_regex)
{
	var bvalue = document.getElementById(master).checked;
	var all_input = document.getElementsByTagName("input");
	
	// Searching checkbox in all_input
	var checkbox = new Array();
	for(var i=0 ; i<all_input.length ; i++)
		if((all_input[i].name).match(slaves_regex) != null)
			all_input[i].checked = bvalue;
}

/*
* Watch all the checkbox which their name is name. The ids of checked checkbox 
*/
function getIdsOfCheckedCheckbox(name)
{
	var elements = document.getElementsByName(name);
	var checked_elements = new Array();
	var ind = 0; // index for checked_elements
	for(var i=0 ; i<elements.length ; i++)
	{
		if(elements[i].checked)
		{
			checked_elements[ind] = elements[i].id;
			ind++;
		}
	}
	
	return checked_elements
}

/*
* Exchanges between two list box with buttons "to right & to left"
*
* Drop selected elements from source_id (<select multiple> id) to dest_id ((<select multiple> id so)
* option tags of source must respect : id = innerHTML. However, when there are several listbox in a document,
* we need differenciation, so there is epsilon :
* epsilon is the prefix of ids
*/
function ListBoxDropping(source_id, dest_id, epsilon)
{
	var source = document.getElementById(source_id);
	var destination = document.getElementById(dest_id);
	
	var id_elem = epsilon + source.value;
	while(id_elem != epsilon) /* While an element is selected */
	{
		/* Move the selected element to destinated listbox */
		destination.add(document.getElementById(id_elem), null);
		document.getElementById(id_elem).selected = false; // unselect
		id_elem = epsilon + source.value;
	}
}

/*
* Hide/unhide a element
*/
function hideUnhide(id)
{
	var element = document.getElementById(id);
	if(element.style.display == "none")
		unhide(element);
	else
		hide(element);
}
function hide(element) {
	element.style.display = "none";
	element.style.visibility = "hidden";
}
function unhide(element) {
	element.style.display = "";
	element.style.visibility = "visible";
}

/*
* Select all the contents of all select-multiple in the current form,
* so that POST variables will be filled with all values (this is what we want).
* Then submit the form !
*/
function selectAllMultiValues(form_id)
{
	var form = document.getElementById(form_id);
	var elements = form.elements;

	for(var i=0 ; i < elements.length ; i++)
	{
		var element = elements[i];
		var tag     = element.tagName
		var type    = element.type;

		if(tag == "SELECT") {
			if(type == "select-multiple") {
				// If the select-multiple is a source or dest listbox (listboxdropping),
				// we have to get "by hand" the elements contained in the list
				for(var j=0 ; j < element.length ; j++) {
					element[j].selected = true;
				}
			}
		}
	}
}

/*
* Filter a RichTableWidget
*/
function filter_the_table(tableid, filterinputid)
{
	var MINLENGTH = 2;
	var filter = document.getElementById(filterinputid).value;
	if(filter.length < MINLENGTH) {
		if(filter.length == 0)
			reset_filtering(tableid)
		return;
	}
	var table = document.getElementById(tableid);
	var rows = table.childNodes[1].childNodes;
	filter = filter.toLowerCase();

	for(var i=2; i < rows.length ; i+=2) {
		if(rows[i].innerHTML.toLowerCase().indexOf(filter) == -1)
			hide(rows[i]);
		else
			unhide(rows[i]);
	}
}
function reset_filtering(tableid)
{
	var table = document.getElementById(tableid);
	var rows = table.childNodes[1].childNodes;
	for(var i=2; i < rows.length ; i+=2)
		unhide(rows[i]);
}
