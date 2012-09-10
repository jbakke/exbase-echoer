"""
Accept input that will make a valid article and return an HTML document
that is easily used as a local file and easily scraped into a database.
"""

from datetime import datetime
from datetime import tzinfo
import json
import os.path
import re
import sys
from time import mktime
import tornado.ioloop
import tornado.web
from uuid import UUID
from uuid import uuid4

# Regex patterns that match UUIDs with added constraints to represent
# object types recognized by the application

UP_ARTICLE = '1[a-z0-9]{7}-[a-z0-9]{4}-[a-z0-9]{4}-[ab89][a-z0-9]{3}-[a-z0-9]{12}'

# When these functions are inverses of each other, they let the app
# appear to be behind a reverse proxy when it isn't. Useful for serving
# static files and the API from the same Tornado application with the
# intent to move the static files to nginx later.

def url_api(url):
    return '/api'+url
def url_deapi(url):
    if re.match('/api/', url):
        return re.sub('^/api/(.*)$', r'/\1', url)
    if url == '/api':
        return '/'
    raise ValueError('%s does not resemble a reverse-proxied URL' % url)

def clean_string(string):
	return ' '.join(string.split())
    
def san_html(txt):
    txt = txt.replace('&', '&amp;')
    txt = txt.replace("'", '&apos;')
    txt = txt.replace('"', '&quot;')
    txt = txt.replace('<', '&lt;')
    txt = txt.replace('>', '&gt;')
    return txt

class App(tornado.web.Application):
    def __init__(self, *args, **kwargs):
        self.articles = {}
        
        tornado.web.Application.__init__(self, *args, **kwargs)

    def to_url_deapi(self, *args, **kwargs):
        return url_deapi(self.reverse_url(*args, **kwargs))

    class RHPost(tornado.web.RequestHandler):
        def post(self):
            if self.request.headers['Content-Type'] != 'application/json':
                raise tornado.web.HTTPError(415)
            
            try:
                obj = json.loads(self.request.body.decode('utf-8')) 
            except ValueError:
                raise tornado.web.HTTPError(400)
            
            try:
                # strftime requires year >= 1900 which strptime does not
                # enforce.
                datetime.strptime(obj['datetime-of-publication'], '%Y-%m-%dT%H:%M:%S').strftime('%a, %d %b %Y')
                
                uuid = '1' + str(uuid4())[1:]
                self.application.articles[uuid] = {
                    'headline': clean_string(obj['headline']),
                    'url-original': clean_string(obj['url-original']),
                    'tags': list(clean_string(t) for t in obj['tags']),
                    'datetime-of-publication': datetime.strptime(obj['datetime-of-publication'], '%Y-%m-%dT%H:%M:%S'),
                    'publications': list(clean_string(p) for p in obj['publications']),
                    'storer': clean_string(obj['storer']),
                    'datetime-of-storage': datetime.now(),
                    'body': list(clean_string(p) for p in obj['body'])
                }
            except (KeyError, ValueError) as e:
                print repr(e)
                raise tornado.web.HTTPError(403)
            
            self.set_status(201)
            self.set_header('Location', self.application.to_url_deapi('Get', uuid))

    class RHGet(tornado.web.RequestHandler):
        def get(self, uuid):
            try:
                article=self.application.articles[uuid]
            except KeyError:
                raise tornado.web.HTTPError(404)
            
            self.set_header('Content-Type', 'text/html; charset=utf-8')
            # UNCOMMENT THESE TO FREE MEMORY AND ENFORCE DOWNLOAD
            # BEHAVIOR IN PRODUCTION
            del self.application.articles[uuid]
            self.set_header('Content-Disposition', 'attachment; filename="'+uuid+'.htm"')
            
            txt = ''.join([
                "<!DOCTYPE html><html><head><meta charset='utf-8'><title>",
                san_html(article['headline']),
                "</title></head><body><h1 id='headline'>",
                san_html(article['headline']),
                "</h1><p id='url-original'><a href='",
                san_html(article['url-original']),
                "'>",
                san_html(article['url-original']),
                "</a></p><p id='tags'>Tagged in <span class='tag'>",
                "</span>, <span class='tag'>".join(san_html(t) for t in article['tags']),
                "</span></p><p id='publications'>Published on <span id='date-of-publication'>",
                article['datetime-of-publication'].strftime('%a, %d %b %Y'),
                "</span> in <span class='publication'>",
                "</span>, <span class='publication'>".join(san_html(p) for p in article['publications']),
                "</span></p><p id='storage'>Stored by <span id='storer'>",
                article['storer'],
                "</span> on <span id='date-of-storage'>",
                article['datetime-of-storage'].strftime('%a, %d %b %Y'),
                "</span> at <span id='time-of-storage'>",
                article['datetime-of-storage'].strftime('%H:%M:%S PST'),
                "</span></p><p class='body'>",
                "</p><p class='body'>".join(san_html(p) for p in article['body']),
                "</p></body></html>"
            ])
            
            # NEXT LINE IS FOR TESTING UNICODE
            print txt
            self.write(txt)
    
    class RHUi(tornado.web.RequestHandler):
        def get(self):
            self.write(open(os.path.join(os.path.dirname(__file__), 'ui.htm'), 'r').read())

def main(port):
    app = App([
        tornado.web.URLSpec(url_api('/'), App.RHPost, name='Post'),
        tornado.web.URLSpec(url_api('/('+UP_ARTICLE+').htm'), App.RHGet, name='Get'),
        
        ('/ui', App.RHUi)
    ])
    
    app.listen(port)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    main(sys.argv[1])
