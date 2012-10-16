(function( $ ){

  $.fn.checkbox = function( options ) {

    // Create some defaults, extending them with any options that were provided
    var settings = $.extend( {
      'on_image'   : '/media/images/jquery_checkbox/on.png',
      'off_image'  : '/media/images/jquery_checkbox/off.png',

      'on_text'    : 'ON',
      'off_text'   : 'OFF',

      "wrapper"    : "checkbox_wrapper"
    }, options);

    return this.each(function() {

    	var checkbox = this
    	var checkbox_wrapper = $('<span class="'+settings.wrapper+'"></span>')


      var jquery_checkbox = $('<span class="jquery_checkbox"><span class="jquery_checkbox_text"></span></span>')
      checkbox_wrapper.append(jquery_checkbox)


    	$(checkbox).css({position: 'absolute', zIndex: -1, visibility: 'hidden'}).after(checkbox_wrapper)

    	jquery_checkbox.click(function(event) {
          $(checkbox).trigger('click')
          event.preventDefault();
          event.stopPropagation();
    	});

    	$(checkbox).change(function() {
        if ($(this).is(':checked')) {
       			jquery_checkbox
    				.css({background: "url('"+settings.on_image+"')"})
					.find('.jquery_checkbox_text')
						.removeClass('jquery_checkbox_off')
						.addClass('jquery_checkbox_on')
						.html(settings.on_text)
    		} else {
    			jquery_checkbox
    				.css({background: "url('"+settings.off_image+"')"})
	    			.find('.jquery_checkbox_text')
	    				.removeClass('jquery_checkbox_on')
						.addClass('jquery_checkbox_off')
						.html(settings.off_text)
    		}
    	}).change()
    });
  };
})( jQuery );