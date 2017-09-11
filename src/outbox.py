#
# Reads an email inbox via IMAP and renders the
# inbox to some HTML and Javascript
#
import socketserver
import sys
import imaplib
import getpass
import email
import email.header
import datetime
import bs4
import hashlib
import os

import pickle
import requests
import click
import http.server

from bs4 import Tag
from mako.template import Template
from mako.lookup import TemplateLookup

# Where is the index.html file hosted from?
BASE_URI=""

# What are we calling the static files directory?
STATIC_URI_PATH="/static"

# What's the local publish folder location?
PUBLISH_DIR="published"

class URLPreview(object):
    """
    Scrape a URL for the thumbnail, page title and description
    to render in the email
    """
    def __init__(self, url):
        self.url = url
        self.title = None
        self.thumbnail_url = None
        self.description = None
        self.template = "themes/default/templates/previews/url.html"
        self.body = None
        self.body_soup = None

        r = requests.get(url)
        if r.status_code is 200:
            self.body = r.content
            self.body_soup = bs4.BeautifulSoup(self.body, "lxml")
        else:
            print("URLPreview status", r.status_code)

        # This denotes the order of preference, most important first
        self.extract_opengraph()
        self.extract_html_info()

        # TODO: Cache the thumbnail URL


    def _replace_tag_text_if_none(self, val, tag, properties):
        if val is not None:
            return None
        if not self.body_soup:
            return None
        t = self.body_soup.find_all(tag, properties)
        if t:
            return t.text
        return None

    def _replace_content_text_if_none(self, val, tag, properties):
        if val is not None:
            return None
        if not self.body_soup:
            return None
        t = self.body_soup.find_all(tag, properties)
        print(val,tag,properties,t)
        if len(t):
            return t[0]['content']
        return None

    def extract_opengraph(self):
        self.title = self._replace_content_text_if_none(self.title, "meta", {"property": "og:title"})
        self.thumbnail_url = self._replace_content_text_if_none(self.thumbnail_url, "meta", {"property": "og:image"})
        self.description = self._replace_content_text_if_none(self.description, "meta", {"property": "og:description"})

    def extract_html_info(self):
        if self.title is None or len(self.title) == 0:
            self.title = self.url
            if len(self.title)>30:
                self.title = self.title[0:30] + "..."

    def render(self):
        tpl = Template(filename=self.template)
        return tpl.render(
            **{
                "title": self.title,
                "description":self.description,
                "thumbnail_url": self.thumbnail_url,
                "url": self.url
            }
        )



class ImgurPreview(object):
    """
    Perform an in-line embed of an imgur link with
    a "via imgur" box
    """
    pass

class TwitterTweetPreview(object):
    """
    Embed a single tweet
    """
    pass

class Image(object):
    """
    Handles images attached to images, allows us to sanitize, thumbnail
    and perform various actions on the images.
    """
    def __init__(self, data, mime):
        self.data = data
        self.mime = mime

        h = hashlib.sha3_256()
        h.update(data)
        self.imgid = h.hexdigest()

        if mime == "image/jpeg":
            self.extension = "jpeg"

    @property
    def path(self):
        return "{0}/{1}/{2}.{3}".format(PUBLISH_DIR, STATIC_URI_PATH, self.imgid, self.extension)

    @property
    def uri(self):
        return "{0}{1}/{2}.{3}".format(BASE_URI, STATIC_URI_PATH, self.imgid, self.extension)

    def save(self, clobber=False):
        if os.path.isfile(self.path) and clobber is False:
            return

        with open(self.path, 'wb+') as f:
            f.write(self.data)




class ImageCollection(object):
    """
    Collections of images can be rendered as a gallery-type
    and presented to users in a certain way.
    """
    pass


class BlogPost(object):

    def __init__(self, uid):
        self.images = []
        self.attachments = []
        self.url_previews = []
        self.html = ""
        self.uid = uid
        self.publish_date = None
        self.template_src = TemplateLookup(directories=['themes/default/templates'])
        self.subject=None
        self.is_long_post = False

        # When we have some text, then a HTML img tag,
        # then some more text, we switch to in-place images
        # meaning they appear where inserted in the email.
        #
        # When we have text only before or after one or more images,
        # we render a gallery and assume it is just a "Checkout my holiday snaps"
        # type post with a whole load of images.
        self.in_place_images = False

    def add_attachment(self, bytes, content_type):
        """
        Add an attachment to the post. This is typically
        something we _cant_ render, so we include it as a
        download link.

        We write the file to the static directory when
        rendering the blog post

        :param bytes:
        :param content_type:
        :return:
        """
        self.attachments.append((content_type, bytes,))


    def add_image(self, bytes, content_type):
        """
        We treat images differently. We can collate them in to
        an image gallery and whatnot.
        :param bytes:
        :param content_type:
        :return:
        """
        self.images.append(Image(bytes,content_type))

    def publish_str(self, embedded=False):
        """
        Here we write static files and HTML to the publish directory
        :param embedded: If we should render a standalone HTML segment
                        rather than a fully-fledged HTML page.
        :return:
        """
        # save our images out, we need them for the HTML render
        for image in self.images:
            image.save()
        tpl = Template(filename="themes/default/templates/post.html", lookup=self.template_src)
        return tpl.render(**{
            "body": self.html,
            "subject": self.subject,
            "images": self.images,
            "url_previews": self.url_previews
        })

    def body_from_text(self, text, encoding='utf-8'):
        decoded = text.decode(encoding)
        self.html = decoded.replace('\r\n', '<br/>')

    def body_from_html(self, html):
        """
        Do some cleanup of the HTML, getting rid of the <head>
        elements and stripping back the HTML to the following:
            <a>, <b>, <i>
        :param html: The unsanitised source HTML
        :return:
        """
        self.html = html.decode('utf-8')

        soup = bs4.BeautifulSoup(self.html, "lxml")
        # Try and classify the post as being long-form
        if len(soup.text) > 256:
            self.is_long_post = True

        # TODO: set in-place images
        if not self.in_place_images:
            # Clear out any image tags relating to email content
            for imgtag in soup.find_all("img"):
                if imgtag['src'].startswith("cid:"):
                    imgtag.decompose()


        for a in soup.find_all("a"):
            if a['href'] and a['href'].startswith("http"):
                self.url_previews.append(URLPreview(a['href']))


        # Cleanup empty divs or those containing just BR tags,
        # an artifact of gmail that could be generalised.
        for div in soup.find_all("div"):
            c = list(div.children)
            if len(c) == 0 and div.text.strip()=="":
                div.decompose()
                continue
            if len(c)==1 and type(c[0]) is Tag and c[0].name == "br":
                div.decompose()

        self.html = soup.prettify()



class IMAPMessageProvider(object):
    # !/usr/bin/env python
    #
    # Very basic example of using Python 3 and IMAP to iterate over emails in a
    # gmail folder/label.  This code is released into the public domain.
    #
    # This script is example code from this blog post:
    # http://www.voidynullness.net/blog/2013/07/25/gmail-email-with-python-via-imap/
    #
    # This is an updated version of the original -- modified to work with Python 3.4.
    #


    # Use 'INBOX' to read inbox.  Note that whatever folder is specified,
    # after successfully running this script all emails in that folder
    # will be marked as read.
    EMAIL_FOLDER = "INBOX"

    def process_mailbox(self, M):
        """
        Do something with emails messages in the folder.
        For the sake of this example, print some headers.
        """

        rv, data = M.search(None, "ALL")
        if rv != 'OK':
            print("No messages found!")
            return

        for num in data[0].split():
            rv, data = M.fetch(num, '(RFC822)')
            if rv != 'OK':
                print("ERROR getting message", num)
                return

            msg = email.message_from_bytes(data[0][1])
            hdr = email.header.make_header(email.header.decode_header(msg['Subject']))
            subject = str(hdr)

            # Build a stable UID for the email
            m = hashlib.sha3_256()
            m.update(data[0][1])

            post = BlogPost(m.hexdigest())

            post.subject = subject

            for part in msg.walk(): # type: email.message.Message
                if part.is_multipart():
                    continue
                ct = part.get_content_type()
                print(ct)
                if ct == "image/jpeg":
                    post.add_image(part.get_payload(decode=True), "image/jpeg")
                elif ct == "text/plain":
                    post.body_from_text(part.get_payload(decode=True))
                elif ct == "text/html":
                    post.body_from_html(part.get_payload(decode=True))

            # Now convert to local date-time
            date_tuple = email.utils.parsedate_tz(msg['Date'])
            if date_tuple:
                post.publish_date = datetime.datetime.fromtimestamp(
                    email.utils.mktime_tz(date_tuple))

            self.blog_posts.append(post)

    def __init__(self, server, user, password):
        self.mailbox = imaplib.IMAP4_SSL(server)
        self.user = user
        self.password = password
        self.blog_posts = []

    def load_messages(self):
        try:
            self.mailbox.login(self.user, self.password)
        except imaplib.IMAP4.error as e:
            print("LOGIN FAILED!!! ", e)
            sys.exit(1)


        rv, data = self.mailbox.select(self.EMAIL_FOLDER)
        if rv == 'OK':
            print("Processing mailbox...\n")
            self.process_mailbox(self.mailbox)
            self.mailbox.close()
        else:
            print("ERROR: Unable to open mailbox ", rv)

        self.mailbox.logout()

    def write_cache(self, writable):
        pickled = pickle.dumps(self.blog_posts)
        writable.write(pickled)

    def load_cache(self, readable):
        #self.blog_posts = pickle.loads(readable)
        pass


def render_inbox(mailbox, publish_dir, theme):
    """
    Write the site to disk based on the mailbox, theme and publish
    directory. If this function returns normally, the publish
    directory should contain a publishable site.
    """
    # For the index page
    template_src = TemplateLookup(directories=['themes/default/templates'])
    index_tpl = template_src.get_template("index.html")
    post_embeds = []

    for post in reversed(mailbox.blog_posts):
        post_embeds.append(post.publish_str())

    print("Writing index.html with {0} embeds".format(len(post_embeds)))
    with open('published/index.html', 'w+') as f:
        f.write(index_tpl.render(**{
            "post_embeds": post_embeds
        }))


def launch_devserver(host, port):
    """
    Boot the development server
    """
    os.chdir("published")
    print("Launching local HTTP server on {0}:{1}".format(host,port))
    with socketserver.TCPServer((host, port), http.server.SimpleHTTPRequestHandler) as httpd:
        httpd.serve_forever()



@click.command()
@click.option('--theme', default="default", help="The theme to use")
@click.option('--server', default=False, help="Run the development server")
@click.option('--imap-host', help="the hostname or IP address (with optional port) of the IMAP server")
@click.option('--imap-username', help="Your IMAP username")
@click.option('--imap-password', help="Your IMAP password")
def command(theme, server, imap_host, imap_username, imap_password):
    """
    Render an email outbox to a static website. Make a secret email address and
    send emails to it to update your site.
    """
    mailsource = IMAPMessageProvider(imap_host, imap_username, imap_password)

    if(server is not False):
        if os.path.exists("_imap_cache"):
            mailsource.load_cache(open("_imap_cache", "rb"))
        else:
            mailsource.load_messages()
            mailsource.write_cache(open("_imap_cache", "wb+"))

        # TODO Fix the cache pickle
        #render_inbox(mailsource, "published", theme)
        launch_devserver(server.split(':')[0], int(server.split(':')[1]))
    else:
        mailsource.load_messages()
        print("Downloaded {0} messages".format(len(mailsource.blog_posts)))
        render_inbox(mailsource, "published", theme)


if __name__ == "__main__":

    command()