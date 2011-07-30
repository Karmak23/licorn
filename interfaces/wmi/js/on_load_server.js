$(document).ready(function(){
	/*$.jqplot.config.enablePlugins = true;

	$(".pie_chart").each(function() {
		var tab = [];
		var color = [];
		$(this).find('input').each(function() {
			console.log("pushing "+this.name+" : "+ parseFloat(this.value));
			bla = [""+this.name, parseFloat(this.value)];
			pushed = tab.push(bla);
			color_pushed = color.push($(this).attr('color'));
		});

		title = $(this).attr('title');
		id = $(this).find('.pie_receiver').attr('id');
		console.log("id = "+id);
		console.log("tab "+tab);
		$.jqplot(id, [tab], {
			seriesColors:color,
			title: {
				//text: title,
				text: "",
				show: false,
			},
			seriesDefaults:{renderer:$.jqplot.PieRenderer, rendererOptions:{shadow:false,  diameter: 150}},
			legend:{show:true, location:'s'},
			grid: {drawGridLines: false, borderWidth: 0, shadow:false},
			cursor: { style: 'crosshair', show: false}
		  
		});

	
	});

	$('.jqplot-title').hide();*/
	/*
	var tab = [];
	var color = [];
	$(".pie_chart > input").each(function() {
		console.log("pushing "+this.name+" : "+ parseFloat(this.value));
		bla = [""+this.name, parseFloat(this.value)];
		pushed = tab.push(bla);
		color_pushed = color.push($(this).attr('color'));
	});
	title = $(".pie_chart").attr('title');
	id = $(".pie_chart").find('.pie_receiver').attr('id');
	console.log("id = "+id);
	console.log("tab "+tab);
	$.jqplot('chart1', [tab], {
	  seriesColors:color,
	  title: title,
	  seriesDefaults:{renderer:$.jqplot.PieRenderer, rendererOptions:{shadow:false}},
	  legend:{show:false},
	  
	});
	*/

 });
