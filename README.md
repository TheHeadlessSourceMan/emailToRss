# emailToRss

[![Unit tests](https://github.com/TheHeadlessSourceMan/emailToRss/actions/workflows/unit-tests.yml/badge.svg)](https://github.com/TheHeadlessSourceMan/emailToRss/actions/workflows/unit-tests.yml)
[![Pylint type checking](https://github.com/TheHeadlessSourceMan/emailToRss/actions/workflows/pylint-type-checking.yml/badge.svg)](https://github.com/TheHeadlessSourceMan/emailToRss/actions/workflows/pylint-type-checking.yml)
[![Coverage](https://img.shields.io/badge/coverage-13%25-red)](https://theheadlesssourceman.github.io/emailToRss/coverage/)

I have a problem called email clutter.  Maybe you can relate.

The main culprit is all these newsletters I have signed up for.  While many of them have good information, they add up really fast and turn my inbox into a nightmare.

**How does converting to RSS help?**

Good question.  The total garbage can be gotten rid of with careful filters, for instance in Thunderbird or Betterbird. That, you probably know.

But what about stuff that you want to see when it comes in, but don't necessarily want to keep around forever?  That's where this tool comes in.

**how does this work?**

What you do is simply tag each message either "RSS" to show on-screen news ticker, or more to the point, "RSS+DEL" to show it to you, and delete the original email.

This way you don't miss out on something that you may want, but at the same time, don't have it cluttering up your mailbox and making you feel tired every time you look at it.

Meanwhile a friendly little server is working in the background to watch for those tags and serve them up as RSS.
Use your favorite RSS ticker to view.

## Settings / configuration / usage

Settings are found in te file: ./data/settings.yaml

For the most part they are pretty self-explanitory.

But notice that you can only do IMAP acconts and/or local maildir directories (eg. Thunderbird).

You CANNOT connect directly to POP accounts because there is no such thing as tags in POP. You will have to use a local client to connect to those, then save the tags locally in maildir directories.

As stated earlier, you will need to add email filters (either in your email client, or whatever) to tag the messages you want added to the RSS feed.  Either use "RSS+DEL" for emails you want added to the feed and deleted from email, or "RSS" if you want to add them to the feed but still keep them in email.

Then simply run `python emailToRssServer.py` to start
