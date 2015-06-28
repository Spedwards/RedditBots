# Define_It
Dictionary bot for Reddit.

Requires all that was listed on the main page, and [Wordnik](https://github.com/wordnik/wordnik-python3)

In your code, you can use it like this:

	import praw
	import Define_It
	
	r = praw.Reddit('Useragent')
	bot = Define_It.Define_It(r)
	
	bot.run()

## Config
Define_It uses a single config file to store the API URL and key for Wordnik. The default file for this is `define_it.conf` but you can specify it during initialization. The file contents are as simple as below:

    api_url
	api_secret_key