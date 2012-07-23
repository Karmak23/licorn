/*
 * jQuery iselectable 1.0.0
 * Copyright 2010, Peter Mayer
 * http://iselectable.com/
 *
 */
(function($){ 

   $.fn.iselectable = function(options) {
		
		var container = this;
		var mousedown = false;
		
		//disable text selection
		if($.browser.mozilla){//Firefox
			$(this).css('-moz-user-select','none');
		}else if($.browser.msie){//IE
			$(this).bind('selectstart',function(){return false;});
		}else{//Opera, etc.
			$(this).mousedown(function(){return false;});
		}
		
		//disable text selection cursor
		$(this).css("cursor","default");
		  
		 
		return this.each(function() {
			
			//default settings
			var settings = {
        		'acccept': '',
				'exclude': '',
        		'active' : 'active'
      	};

			//override settings with user options
			if ( options ) { 
        		$.extend( settings, options );
      	}

			//set the children class for accepted items
			var children_class= '';
			if (settings.accept) children_class = settings.accept;
			else if (settings.exclude) children_class = ':not('+settings.exclude+')';
					
			$(this).children(children_class).mousedown(function(e) {

				mousedown = true;
				
				//control click
				if(e.ctrlKey) {
					
					//Prevent context menu (Mac)
					$(this).bind("contextmenu",function(e){
              		return false;
       			});
					
					if($(this).hasClass(settings.active)) {
						$(this).removeClass(settings.active);
					} else {
						$(this).addClass(settings.active);
					}
					
				//shift click
				} else if(e.shiftKey) {
					
					$(this).addClass("iselectable-clicked");
					
					//get the first, last and clicked item
					var i = 0;
					var fst = false;
					var lst = false;
					var sel = false;
					$(container).children(children_class).each(function() {
						if($(this).hasClass(settings.active)) {
							if (fst===false) fst=i; //set first selected
							lst=i; //set last selected
						}
						if($(this).hasClass("iselectable-clicked")) {
							sel=i; //set last clicked
							$(this).removeClass("iselectable-clicked");
						}
						i++;
					});
					
					//set selection start and end point, depending of clicking above and below selection
					if (fst==sel) { //if first selected item is clicked
						var start=fst;
						var end=fst;
					} else if (fst<sel) { //ist clicked item is before first active item
						var start=fst;
						var end=sel;
					} else { //if clicked item is after first active item 
						var start=sel;
						var end=lst;
					}
					
					//set active class on selected items
					$(container).children(children_class).removeClass(settings.active);
					for (i=start;i<=end;i++) {
						$(container).children(children_class).eq(i).addClass(settings.active);
					}
					
				//normal click
				} else {

					$(this).addClass("iselectable-dragstart");
					var size = container.children("."+settings.active).size();
					
					if (size==1 && $(this).hasClass(settings.active)) {
						$(this).removeClass(settings.active);
					} else {
						container.children("."+settings.active).removeClass(settings.active);
						$(this).addClass(settings.active);
					}
					
				}
			
			});
			
			$('body').mouseup(function(e) {
					mousedown = false;
					$(container).children().removeClass("iselectable-dragstart");
			});
			
			//drag select
			$(this).children(children_class).mouseenter(function(e) {
				if (mousedown && !e.ctrlKey && !e.shiftKey) {
					$(this).addClass("iselectable-dragend");
					i=0;
					$(container).children(children_class).each(function() {
						if($(this).hasClass("iselectable-dragstart")) {
							fst=i; //set last selected
						}
						if($(this).hasClass("iselectable-dragend")) {
							lst=i; //set last clicked
							$(this).removeClass("iselectable-dragend");
						}
						i++;
					});
					
					if (fst==lst) { //if first selected item is clicked
						var start=fst;
						var end=fst;
					} else if (fst<lst) { //ist clicked item is before first active item
						var start=fst;
						var end=lst;
					} else { //if clicked item is after first active item 
						var start=lst;
						var end=fst;
					}
					
					$(container).children(children_class).removeClass(settings.active);
					for (i=start;i<=end;i++) {
						$(container).children(children_class).eq(i).addClass(settings.active);
					}
					
				}
			});
			
			
			
		});  
	};
	
})(jQuery);  