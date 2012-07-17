(function( $ ){

  $.fn.checkbox = function( options ) {  

    // Create some defaults, extending them with any options that were provided
    var settings = $.extend( {
      'on_image'   : '/media/images/jquery_checkbox/on.png',
      'off_image'  : '/media/images/jquery_checkbox/off.png',

      'on_text'    : 'ON',
      'off_text'   : 'OFF'
    }, options);

    return this.each(function() {        

    	var checkbox = this
    	var checkbox_wrapper = $('<span class="jquery_checkbox"><span class="jquery_checkbox_text"></span></span>')

    	$(checkbox).css({position: 'absolute', zIndex: -1, visibility: 'hidden'}).after(checkbox_wrapper)
    	
    	checkbox_wrapper.click(function(event) {
          $(checkbox).trigger('click')
          event.preventDefault();
          event.stopPropagation();
    	});

    	$(checkbox).change(function() {
       console.log('change')
        if ($(this).is(':checked')) {
       			checkbox_wrapper
    				.css({background: "url('"+settings.on_image+"')"})
					.find('.jquery_checkbox_text')
						.removeClass('jquery_checkbox_off')
						.addClass('jquery_checkbox_on')
						.html(settings.on_text)
    		} else {
    			checkbox_wrapper
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