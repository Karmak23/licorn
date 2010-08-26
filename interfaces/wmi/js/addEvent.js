function pageLoader() {
	sweetTitles.init();

	/*
	Nifty("div#menu a","small transparent top");
	Nifty("ul#intro li","same-height");
	Nifty("div.date");
	Nifty("div#content,div#side","same-height");
	Nifty("div.comments div");
	Nifty("div#footer");
	Nifty("div#container","bottom");
	*/
	//Nifty("div#license");
}

addEvent(window, 'unload', EventCache.flush);
addEvent(window, 'load',   pageLoader);
