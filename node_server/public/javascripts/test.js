var webSocket = new WebSocket('ws://localhost:13254')

var map = {
	'10': 'depression',
	'7': 'glasses',
	'6': 'female',
	'4': 'male',
	'5': 'beard',
	'15': 'power_save_mode'
}

var value;
webSocket.onmessage = function(event) {
	value = map[String(event.data.size)]
	console.log(value);

	$('html').fadeTo('slow', 0.3, function(){
    	$(this).css('background', 'url(../images/' + value + '.jpeg)');
	}).fadeTo('slow', 1);

	webSocket.send('a')
}