/* TODO :
	- couleur checkbox + margin-left du "on" et "off" => OK
	- coté public : file size limit => OK
	- coté wmi : popover on click ailleur se ferme => OK

	- verif popover sur les users/groups

*/
$(document).ready(function(){
	//http://api.jquery.com/category/events/event-object/
	$.event.props.push("dataTransfer");
});

(function( $ ){

  $.fn.upload_dnd = function( options ) {

    // Create some defaults, extending them with any options that were provided
    var settings = $.extend( {
    	'upload_action_url': '/',			// post upload action
    	'upload_data' : {},					// additionnal data to pass to the action (ex: crf token)

    	'pre_function' : null,			// pre func to run before upload. return a dict of post argument sent during post upload action

    	'recap_element' : null,			// recap element, if null, will be added just after the upload_box

    	'upload_box_style': {},
    	'upload_box_style_on_hover': {},

    	'error_hanlder' : null,
    	'success_hanlder' : null,

    	"recap_line" : '<div><span id="recap_file_name"></span><span id="recap_file_size"></span><span id="recap_file_progress"></span></div>',


     	"error_image_url" : '/media/images/16x16/check_bad.png',
     	"file_size_max" : null,
    }, options);

    return this.each(function() {
    	////console.log('settings ,', settings)

    	// http://help.dottoro.com/ljccpmjk.php
    	// bind the drop event

    	/*this.ondrop=function() {
    		//console.log('droppppppppp')
    	}

		dropbox = document.getElementById("file_upload");

    	// init event handlers
		dropbox.addEventListener("dragenter", dragEnter, false);
		dropbox.addEventListener("dragexit", dragExit, false);
		dropbox.addEventListener("dragleave", dragExit, false);
		dropbox.addEventListener("dragover", dragOver, false);
		dropbox.addEventListener("drop", drop, false);


		function dragEnter(evt)
		{
		//console.log("enter box");
		evt.stopPropagation();
		evt.preventDefault();
		}
		function dragExit(evt)
		{

		//console.log("exit box")
		evt.stopPropagation();
		evt.preventDefault();
		}
		function dragOver(evt)
		{

		//console.log("over box")
		evt.stopPropagation();
		evt.preventDefault();
		}

		function droped(evt)
		{
		evt.stopPropagation();
		evt.preventDefault();

		var files = evt.dataTransfer.files;
		var count = files.length;

		if (count > 0)
		{
		    alert("files dropped");
		    //handleFiles(files);
		}
		}


    	//console.log(this)*/



    	$(this).bind('drop', { 'settings' : settings, 'drag_target': this }, drop )
    	$(this).bind('dragover', stop_event )
    	// bind the dragenter to apply a style when drag enter in the upload box
    	// NOTE : we use a counter, because in Chromium, a dragleave event is triggered when entering a child
    	$(this).bind('dragenter', { 'settings' : settings, 'drag_target': this }, drag_enter );

    	$(this).bind('dragleave', { 'settings' : settings, 'drag_target': this }, drag_leave);

    	// if recap_element is not set, add it after the upload box
    	if (settings.recap_element == null) {
    		settings.recap_element = $('<div id="recap_div">&nbsp;</div>')
	    	$(this).after(settings.recap_element)
    	}

    	// apply default css
    	$(this).css(settings.upload_box_style)

    	// append the help text :
    	$(this).append("Drop files here to upload them to this share.");
    	$(this).append("<div id='max_size_file'>" + "maximum size: "
			+ getReadableFileSizeString(settings.file_size_max) + "</div>");
    	$('#max_size_file').css({ "margin-top" : "110px", "font-size" : 11, "text-align":"center"})

    	// append the "normal upload" form
    	normal_html = "<input type='file' id='classic_upload'/>"
    	$(settings.recap_element).append(normal_html)

    	// bind our events to the "normal" http file browser
		$('#classic_upload').change(function(event){
			// get files
			var files = event.target.files

			if (settings.run_function != null) {
				// the default action is overwritten
				settings.run_function(files, settings)
			}
			else {
				do_upload(files, settings)
			}
		});



    	//$(this).bind({
		//	"dragenter dragexit dragover" : stop_event,
		//});
    });
  };
})( jQuery );

var num_drag_event = 0;

function drag_enter(event) {
	//console.log('dragenter')
	settings = event.data.settings
	target = $(event.data.drag_target)

	num_drag_event++;
    target.css(settings.upload_box_style_on_hover);

    stop_event(event)
}
function drag_leave(event) {
	//console.log('dragleave')
	settings = event.data.settings
	target = $(event.data.drag_target)

	num_drag_event--;
	if (num_drag_event == 0) {
		//console.log(settings.upload_box_style)
		target.css(settings.upload_box_style);
	}

	stop_event(event)
}



// http://code.google.com/p/chromium/issues/detail?id=106705
// issue with dragleave qui se répete on hover:  http://bugs.jquery.com/ticket/11801

function drop(event){
	stop_event(event)
	//console.log(">> drop function")
	// get settings
	settings = event.data.settings

	// get upload files from event
	var files = event.dataTransfer.files;
	////console.log('>>>> files ', files)

	stop_event(event);
	// drag leave
	$(event.data.drag_target).trigger('dragleave')

	if (settings.run_function != null) {
		// the default action is overwritten
		settings.run_function(files, settings)
	}
	else {
		do_upload(files, settings)
	}


}

function do_upload(files, settings) {
	//console.log('\t >> do upload')

	$.each(files, function(i, file) {
		//console.log('tototototo')

		//console.log(file)


	  	// prepare the recap line
	  	var recap_line = $(settings.recap_line)
	  	$(recap_line).find('#recap_file_name').html(file.name)
	  	$(recap_line).find('#recap_file_size').html(getReadableFileSizeString(file.size))
	  	//console.log(recap_line)
	  	$(settings.recap_element).append(recap_line)

	  	// prepare the error_div
	  	var error_div = $('<center><img src="'+settings.error_image_url+'"><center>')

	  	// check unknown file type (e.g. a public user drop a directory)
	  	//console.log('checkfiletype ', file.type)
	  	if (file.type == "") {
	  		//console.log('UNKNOWN FILE TYPE')
	  		recap_line
		    	.find('#recap_file_progress').html('').append(error_div.attr('title', "Unknown file type"));

		    return false;
	  	}
	  	else if( settings.file_size_max != null) {
	  		console.log("max size set to ", settings.file_size_max)
	  		if (file.size > settings.file_size_max) {
	  			recap_line
					.find('#recap_file_progress').html('').append(error_div.attr('title', "File too big, maximun allowed "+getReadableFileSizeString(settings.file_size_max)));

	  			return false;
	  		}

	  	}



	  	// AT this point, all should be ok

			// bind upload events
			var xhr = jQuery.ajaxSettings.xhr();
			if(xhr.upload){
				xhr.upload.addEventListener('progress', function (e) {
					if (e.lengthComputable) {
	                    var percentage = Math.round((e.loaded * 100) / e.total);
					    recap_line
					    	.find('#recap_file_progress')
					    		.html('<div class="progress progress-striped" style="display:\'inline\'"> <div class="bar" style="width: '+percentage+'%;">'+percentage+'%</div></div>')
	                    ////console.log("Percentage loaded: ", percentage);
	                }
	                stop_event(e)
	            }, false);
			}

			xhr.upload.addEventListener("load", function(e) {
					//console.log('LOAD EVENT', e)
					stop_event(e)
				}, false);
			xhr.upload.addEventListener("error", function(e) {
					//console.log('RROR EVENT')
					stop_event(e)
				}, false);
			xhr.upload.addEventListener("abort", function() {
					//console.log('CANCEL EVENT')
					stop_event(e)
				}, false);



			provider=function(){ return xhr; };


			var datas = $.extend( {
		    	'file': file,			// post upload action

		    }, settings.upload_data);

		    d = new FormData
		  	$.map(datas, function(value, key) {
		    	d.append(key, value)
		    })

			////console.log('d', d)
			////console.log('settings', settings)

			// Requete ajax pour envoyer le fichier
			$.ajax({
				url:settings.upload_action_url,
				type: 'POST',
				data: d,
				async: true,

				xhr:provider,
				processData:false,
				contentType:false,
				success:function(data) {
					settings.success_handler(data)
				},
				error:function(error){
					recap_line.find('#recap_file_progress').html('').append(error_div.attr('title', error.statusText))
					settings.error_handler()
				}
			});






});


	/*
	// On vÃ©rifie que des fichiers ont bien Ã©tÃ© dÃ©posÃ©s
	if(files.length>0){
		for(var i in files){
			// Si c'est bien un fichier
			if(files[i].size!=undefined) {

				var fic=files[i];

				// On ajoute un listener progress sur l'objet xhr de jQuery
				xhr = jQuery.ajaxSettings.xhr();
				if(xhr.upload){
					xhr.upload.addEventListener('progress', function (e) {
						////console.log(e);
						update_progress(e,fic);
					},false);
				}
				provider=function(){ return xhr; };

				// On construit notre objet FormData
				var fd=new FormData;
				fd.append('file',fic);
				fd.append('csrfmiddlewaretoken', $('input[name$="csrfmiddlewaretoken"]').attr('value'))

				// Requete ajax pour envoyer le fichier
				$.ajax({
					url:'/share/robin/UTT/upload/filename',
					type: 'POST',
					data: fd,
					xhr:provider,
					processData:false,
					contentType:false,
					complete:function(data){
						$('#'+data.responseText+' .percent').css('width', '100%');
						$('#'+data.responseText+' .percent').html('100%');
					}
				});


				// On prÃ©pare la barre de progression au dÃ©marrage
				var id_tmp=fic.size;
				$('#output').after('<div class="progress_bar loading" id="'+id_tmp+'"><div class="percent">0%</div></div>');
				$('#output').addClass('output_on');

				// On ajoute notre fichier Ã  la liste
				$('#output-listing').append('<li>'+files[i].name+'</li>');

			}
		}
	}*/

}

// Fonction stoppant toute Ã©vÃ¨nement natif et leur propagation
function stop_event(event){
	event.stopPropagation();
	event.preventDefault();
	return false;
}

// Mise Ã  jour de la barre de progression
function update_progress(evt,fic) {

	var id_tmp=fic.size;

	if (evt.lengthComputable) {
		var percentLoaded = Math.round((evt.loaded / evt.total) * 100);
		if (percentLoaded <= 100) {
			$('#'+id_tmp+' .percent').css('width', percentLoaded + '%');
			$('#'+id_tmp+' .percent').html(percentLoaded + '%');
		}
	}
}

function getReadableFileSizeString(fileSizeInBytes) {

    var i = -1;
    var byteUnits = [' kB', ' MB', ' GB', ' TB', 'PB', 'EB', 'ZB', 'YB'];
    do {
        fileSizeInBytes = fileSizeInBytes / 1024;
        i++;
    } while (fileSizeInBytes > 1024);

    return Math.max(fileSizeInBytes, 0.1).toFixed(1) + byteUnits[i];
};
