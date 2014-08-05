pond-hopper
===========

Create an RSS feed and engagement metrics for Atlantic writers who aren't given RSS feeds by The Atlantic.

This server will eventually include engagement metrics.

This requires Python and flask.

```
pip install requests BeautifulSoup4 pytz flask
```

Edit the code if you want it to run on any port other than 5050

And then:
```
python pond-hopper.py
```

To view a person's RSS feed, load http://localhost:5050/byline/ATLANTIC_BYLINE_SLUG

To view a section's RSS feed, load http://localhost:5050/section/CATEGORYA/CATEGORYB/CATEGORYC


The atlantic byline slug can be obtained by looking at the URL for the author page of any Atlantic author. For example, the ATLANTIC_BYLINE_SLUG for "www.theatlantic.com/j-nathan-matias/" is "j-nathan-matias" so the resulting RSS feed URL would be http://localhost:5050/byline/j-nathan-matias

Categories may be similarly obtained. "www.theatlantic.com/entertainment/category/1book140/" becomes "http://localhost:5050/section/entertainment/category/1book140/"

At some imaginary point in my copious free time, I plan to download a list of all bylines and use that to create an index. I also plan to add metrics and other material.
