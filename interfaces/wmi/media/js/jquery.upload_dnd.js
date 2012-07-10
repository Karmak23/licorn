/* 
	* Add a div "upload_recap" for upload results
	* add a div "classic_upload" if you need it, it will be bind to the same action as the drag and drop upload function

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

    	'pre_function' : null,			// pre func to run before upload. return a dict of post argument sent during post upload action

    	'error_hanlder' : null,
    	'success_hanlder' : null,

    	"recap_line" : '<div><span id="recap_file_name"></span><span id="recap_file_size"></span><span id="recap_file_progress"></span></div>',


     	"error_image_url" : '/media/images/16x16/emblem-important.png',
     	"file_size_max" : null,
    }, options);

    return this.each(function() {
    
    	$(this).bind('drop', { 'settings' : settings, 'drag_target': this }, drop )
    	$(this).bind('dragover', stop_event )
    
    	// bind the dragenter to apply a style when drag enter in the upload box
    	// NOTE : we use a counter, because in Chromium, a dragleave event is triggered when entering a child
    	$(this).bind('dragenter', { 'settings' : settings, 'drag_target': this }, drag_enter );

    	$(this).bind('dragleave', { 'settings' : settings, 'drag_target': this }, drag_leave);

    	// apply default css
    	$(this).addClass('upload_area_default');
    	
    	    	
    	// bind our events to the "normal" http file browser, if found
    	if ($('#classic_upload') != []) {
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
		}
    });
  };
})( jQuery );

var num_drag_event = 0;

function drag_enter(event) {
	settings = event.data.settings
	target = $(event.data.drag_target)

	num_drag_event++;
    target.addClass('upload_area_hover');

    stop_event(event)
}
function drag_leave(event) {
	settings = event.data.settings
	target = $(event.data.drag_target)

	num_drag_event--;
	if (num_drag_event == 0) {
		target.removeClass('upload_area_hover');
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
	  	console.log($('#upload_recap'), $('#upload_recap') != [])
	  	if ($('#upload_recap') != []) {
			var recap_line = $(settings.recap_line)
			$(recap_line).find('#recap_file_name').html(file.name)
			$(recap_line).find('#recap_file_size').html(getReadableFileSizeString(file.size))
			console.log(recap_line)
			$('#upload_recap').append(recap_line)
		}

	  	// prepare the error_div
	  	var error_div = $('<center><img src="'+settings.error_image_url+'"><center>')


		var can_continue = true;

	  	// check unknown file type (e.g. a public user drop a directory)
	  	//console.log('checkfiletype ', file.type)
	  	if (file.type == "") {
	  		//console.log('UNKNOWN FILE TYPE')
	  		recap_line
		    	.find('#recap_file_progress').html('').append(error_div.attr('title', "Unknown file type"));
		    recap_line.addClass('upload-result-error')

		    can_continue = false;
	  	}
	  	else if( settings.file_size_max != null) {
	  		console.log("max size set to ", settings.file_size_max)
	  		if (file.size > settings.file_size_max) {
	  			recap_line
					.find('#recap_file_progress').html('').append(error_div.attr('title', "File too big, maximun allowed "+getReadableFileSizeString(settings.file_size_max)));
				recap_line.addClass('upload-result-error')
	  			can_continue = false;
	  		}

	  	}


		if (can_continue) {

			// bind upload events
			var xhr = jQuery.ajaxSettings.xhr();
			if(xhr.upload){
				xhr.upload.addEventListener('progress', function (e) {
					if (e.lengthComputable) {
						var percentage = Math.round((e.loaded * 100) / e.total);
						recap_line
							.find('#recap_file_progress')
								.html('<div class="progress progress-striped" style="display:\'inline\'"> <div class="bar" style="width: '+percentage+'%;">'+percentage+'%</div></div>')
						recap_line.addClass('upload-result-success')
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
			
			var csrf_token = {};
			if ($('input[name$="csrfmiddlewaretoken"]') != null) {
				csrf_token = { csrfmiddlewaretoken : $('input[name$="csrfmiddlewaretoken"]').attr('value') }
			}


			var datas = $.extend( {
				'file': file,			// post upload action

			}, csrf_token);

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
					recap_line.addClass('upload-result-error')
					if (settings.error_handler != null) {
						settings.error_handler()
					}
					
				}
			});

		}
	});
	
}

// prevent default event and its propagation
function stop_event(event){
	event.stopPropagation();
	event.preventDefault();
	return false;
}

function getReadableFileSizeString(fileSizeInBytes) {

    var i = -1;
    var byteUnits = [' kB', ' MB', ' GB', ' TB', ' PB', ' EB', ' ZB', ' YB'];
    do {
        fileSizeInBytes = fileSizeInBytes / 1024;
        i++;
    } while (fileSizeInBytes > 1024);

    return Math.max(fileSizeInBytes, 0.1).toFixed(1) + byteUnits[i];
};
