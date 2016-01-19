import re
import json
import sys
import os
import requests
import datetime
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
import dateutil.parser
from pytz import timezone
import pytz
import flask
from flask import Flask
from flask import render_template
from gender_detector import GenderDetector
import nltk
import string
from collections import defaultdict
import codecs

from mediameter.cliff import Cliff

sent_detector = nltk.data.load('tokenizers/punkt/english.pickle')
sex_detector = GenderDetector('us')
my_cliff = Cliff('http://civicprod.media.mit.edu',8080)



app = Flask(__name__)


class Article:
  def __init__(self, section, author=None, social=False):
    self.author = author

  def append_feedgen(self, fe):
    fe.title(self.title)
    for byline in self.bylines:
      fe.author({"name":byline["name"]})
    fe.link([{"href":self.url},{"href":self.image}])
    fe.id(self.url)
    fe.updated(self.date)
    fe.pubdate(self.date)
    fe.description(self.subtitle)

class AtlanticArticle(Article):
  def __init__(self, section, author=None, social=False):
    #extract information from the page
    title_link = section.findAll("a")[0]#findAll(attrs={"class":"article"})[0].findAll("a")[0]
    self.title = title_link.findAll("h2")[0].get_text()
    self.url = re.sub(r'\#.*', '', title_link['href'])
    eastern = timezone('US/Eastern')
    self.article_text = None
    self.cliff = None
    # some dates come in as July/August 2014, so strip the first month field from it
    datefield = section.findAll("time")[0]#re.sub(r'.*\/?','',section.findAll(attrs={"class":"date"})[0].get_text())
    #import pdb;pdb.set_trace()
    self.date = eastern.localize(dateutil.parser.parse(datefield.text.strip()))
    self.subtitle = section.findAll(attrs={"class":"dek"})[0].get_text()
    self.bylines = []
    if author is None:
      for auth in section.findAll(attrs={"class":"author"}):
        self.bylines.append({"name": auth.get_text(), "url": auth['href']})
    else:
      self.bylines.append({"name":author})

    self.image = None
    thumb = section.findAll("figure")
    if(len(thumb)>0):
      img = thumb[0].findAll("img")
      if(len(img)>0):
        self.image = img[0]['src']
    #print self.image

    #TODO: download the first paragraph from the article
    print self.title.encode('ascii', 'ignore')
    self.get_article_text()
    self.query_cliff()
    self.get_gender_counts()
    #TODO: download social media metrics for the article
    if(social):
      self.facebook = facebook("http://theatlantic.com/" + self.url)
      #self.twitter = twitter(self.url)
  def get_article_text(self):
    res = requests.get("http://theatlantic.com" + self.url)
    soup = BeautifulSoup(res.text)
    body_tag = soup.findAll(attrs={"class":"article-body"})
    self.article_text = body_tag[0].text.replace("\n", " \n")
    self.sentences = len(sent_detector.tokenize(self.article_text))
    return self.article_text

  def query_cliff(self):
    #cliff_url = "http://cliff.mediameter.org/process"
    a_text = self.article_text#.encode('ascii', 'ignore')
    #res = requests.post(cliff_url, data={"demonyms":"false", "text":a_text})
    self.cliff = my_cliff.parseText(a_text)#json.loads(res.text)
    #f = codecs.open("articletext.log", "a", encoding='utf_8')
    #f.write(a_text)
    #f.write("\n\n ---------------\n\n")
    #f.write(self.cliff)
    #f.write("\n\n ---------------\n\n")
    #f.close()
    self.cliff['results']['mentions']=None
    self.cliff['results']['places']=None
    return self.cliff

  def person_list(self):
    return {"names":set(),"first":None, "gender":"unknown", "count":0}

  def get_gender_counts(self):
    if(self.cliff is None):
      return None
    people_list = defaultdict(self.person_list)
    for person in self.cliff['results']['people']:
      fullname = person['name']
      nametokens = string.split(fullname.strip(), ' ')
      surname = nametokens[-1]
      if(len(nametokens)==0):
        continue

      ## ASSUMPTION: SINGLE NAME IS A SURNAME SITUATION
      people_list[surname]['names'].add(fullname)
      people_list[surname]['count'] += person['count']
      if(len(nametokens)>1):
        people_list[surname]['first'] = nametokens[0]

    counts = {"male":0, "female":0, "unknown":0}
    for key in people_list.keys():
      person = people_list[key]
      if(person['first'] is None):
        counts['unknown'] += person['count']
        continue
      gender = sex_detector.guess(person['first'])
      counts[gender] += person['count']
      people_list[gender] = gender

    self.people_list = people_list
    self.gender_counts = counts

    


@app.route("/metrics/byline/<byline>")
def byline_metrics(byline):
  url = "http://www.theatlantic.com/author/" + byline.replace("/","") + "/"
  fg, articles = get_fg(url,social=True)
  #twitter = [str(x.twitter) for x in articles]
  twitter = []
  facebook = [str(x.facebook['data'][0]['total_count']) for x in articles]
  labels = ['"' + x.date.strftime('%b %d %Y') + '"' for x in articles]
  labels.reverse()
  data = {"twitter":twitter,"facebook":facebook}
  data['twitter'].reverse()
  data['facebook'].reverse()
  return render_template("metrics.html", fg = fg, articles=articles, byline=byline, twitter = twitter, facebook=facebook, labels=labels, data=data)

# get a feed for a  byline
@app.route("/byline/<byline>")
def byline(byline):
  url = "http://www.theatlantic.com/" + byline.replace("/","") + "/"
  #print url
  return get_feed_for_url(url)

# get a feed for a section
@app.route("/section/<sectiona>/<sectionb>/<sectionc>/")
def section(sectiona,sectionb,sectionc):
  url = "http://www.theatlantic.com/{0}/{1}/{2}".format(sectiona,sectionb,sectionc)
  return get_feed_for_url(url)

def get_fg(url, social=False):
  res = requests.get(url)
  soup = BeautifulSoup(res.text)
#load the articles into classes
  articles = []

  author_tag = soup.findAll("div", attrs={"class":"author-header"})
  #at = author_tag.findAll("div", attrs={"class":"name"})
  author = None
  if len(author_tag)>0:
    at = author_tag[0].findAll(attrs={"class":"name"})
    #author = ' '.join(author_tag[0].get_text().split())
    author = at[0].text.strip()

  for article in soup.findAll(attrs={"class":"article"}):
    articles.append(AtlanticArticle(article, author=author,social=social))

  #import pdb; pdb.set_trace()
#set up the feed, with basic metadata
  fg = FeedGenerator()
  fg.link(href=url)
  if(author is None and len(articles)>0):
    fg.author(name=articles[0].bylines[0])
  else:
    fg.author(name=author)

  title_tag = soup.findAll(attrs={"class":"display-category"})
#set the title if there's not a category -- e.g. it's a person's page
  if(len(title_tag)>0):
    title = ' '.join(title_tag[0].get_text().split())
  else:
    title = "Atlantic posts by {0}".format(author.encode('ascii', 'ignore'))
  fg.title(title)

#set the description
  description = soup.findAll(attrs={"class":"bio"})
  if len(description)>0:
    fg.description(' '.join(description[0].get_text().split()))
  else:
    fg.description("RSS Feed for {0}, generated by Pond Hopper 0.1".format(title))

#add each article to the feed
  for article in articles:
    article.append_feedgen(fg.add_entry())
  return fg, articles

#return a feed for a url
def get_feed_for_url(url):
  fg = get_fg(url)[0]
  return flask.Response(fg.rss_str(pretty=True), mimetype='application/rss+xml')

#get facebook data for a url
def facebook(url):
  #res = requests.get("http://graph.facebook.com/" + url)
  res = requests.get("https://graph.facebook.com/fql?q=SELECT%20like_count,%20total_count,%20share_count,%20click_count,%20comment_count%20FROM%20link_stat%20WHERE%20url%20=%20%22{0}%22".format(url.replace("http://","")))
  j = json.loads(res.text)
  if "data" in j.keys() and len(j['data'])>0:
    return j
  else:
    return {"data":[{"total_count":0}]}

#def twitter(url):
#  res = requests.get("http://urls.api.twitter.com/1/urls/count.json?url=" + url)
#  return json.loads(res.text)['count']

def reddit(url):
  reddit_url = "http://buttons.reddit.com/button_info.json?url={0}".format(url)
  res = requests.get(reddit_url)
  #import pdb; pdb.set_trace()
  j = json.loads(res.text)
  if not "data" in j:
    print "REDDIT ERROR WITH {0}".format(reddit_url)
    return {"ups":"0", "num_comments":"0"}
  else:
    data = j['data']
  if "children" in data and len(data["children"]) > 0 and "data" in data["children"][0]:
    child = data["children"][0]
    return {"ups":child["data"]["ups"],"num_comments":child["data"]["num_comments"]}
  return {"ups":"0", "num_comments":"0"}

 

if __name__ == "__main__":
  app.debug = True
  app.run(host='0.0.0.0',port=5050)
