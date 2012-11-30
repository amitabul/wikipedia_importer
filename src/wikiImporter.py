#!/usr/bin/env python

from __future__ import with_statement

from contextlib import closing
#from StringIO import StringIO
from io import StringIO
from optparse import OptionParser
import sys
from xml.sax import make_parser
from xml.sax.handler import ContentHandler

from bs4 import BeautifulSoup
import WikiExtractor

import HTMLParser    
import MySQLdb

db = None
db_cursor = None


#
#from blueplate.parsing.tsv import create_default_writer

__docformat__ = "restructuredtext"


class WPXMLHandler(ContentHandler):

    """Parse the enwiki-latest-pages-meta-history.xml file.

    This parser looks for just the things we're interested in.  It maintains a
    tag stack because the XML format actually does have some depth and context
    does actually matter.

    """

    def __init__(self, page_handler):
        """Do some setup.

        page_handler
            This is a callback.  It will be a called with a page in the form
            of a dict such as::

                {'id': u'8',
                 'revisions': [{'timestamp': u'2001-01-20T15:01:12Z',
                                'user': u'ip:pD950754B.dip.t-dialin.net'},
                               {'timestamp': u'2002-02-25T15:43:11Z',
                                'user': u'ip:Conversion script'},
                               {'timestamp': u'2006-09-08T04:16:46Z',
                                'user': u'username:Rory096'},
                               {'timestamp': u'2007-05-24T14:41:48Z',
                                'user': u'username:Ngaiklin'},
                               {'timestamp': u'2007-05-25T17:12:09Z',
                                'user': u'username:Gurch'}],
                 'title': u'AppliedEthics'}

        """
        self._tag_stack = []
        self._page_handler = page_handler

    def _try_calling(self, method_name, *args):
        """Try calling the method with the given method_name.

        If it doesn't exist, just return.

        Note, I don't want to accept **kargs because:

         a) I don't need them yet.
         b) They're really expensive, and this function is going to get called
            a lot.

        Let's not think of it as permature optimization, let's think of it as
        avoiding premature flexibility ;)

        """
        try:
            f = getattr(self, method_name)
        except AttributeError:
            pass
        else:
            return f(*args)

    def startElement(self, name, attr):
        """Dispatch to methods like _start_tagname."""
        self._tag_stack.append(name)
        self._try_calling('_start_' + name, attr)
        self._setup_characters()

    def _start_page(self, attr):
        self._page = dict(revisions=[])

    def _start_revision(self, attr):
        self._page['revisions'].append({})

    def _start_redirect(self, attr):
        self._page['redirect'] = attr['title']

    def endElement(self, name):
        """Dispatch to methods like _end_tagname."""
        self._teardown_characters()
        self._try_calling('_end_' + name)
        self._tag_stack.pop()

    def _end_page(self):
        self._page_handler(self._page)

    def _setup_characters(self):
        """Setup the callbacks to receive character data.

 The Parser will call the "characters" method to report each chunk of
 character data.  SAX parsers may return all contiguous character data
 in a single chunk, or they may split it into several chunks.  Hence,
 this class has to take care of some buffering.

        """
        method_name = '_characters_' + '_'.join(self._tag_stack)
        if hasattr(self, method_name):
            self._characters_buf = StringIO()
        else:
            self._characters_buf = None

    def characters(self, s):
        """Buffer the given characters."""
        if self._characters_buf is not None:
            self._characters_buf.write(s)

    def _teardown_characters(self):
        """Now that we have the entire string, put it where it needs to go.

 Dispatch to methods like _characters_some_stack_of_tags.  Drop strings
 that are just whitespace.

        """
        if self._characters_buf is None:
            return
        s = self._characters_buf.getvalue()
        if s.strip() == '':
            return
        method_name = '_characters_' + '_'.join(self._tag_stack)
        self._try_calling(method_name, s)

    def _characters_mediawiki_page_title(self, s):
        self._page['title'] = s
        
    def _characters_mediawiki_page_id(self, s):
        self._page['id'] = s

    def _characters_mediawiki_page_revision_timestamp(self, s):
        self._page['revisions'][-1]['timestamp'] = s

    def _characters_mediawiki_page_revision_text(self, s):
        self._page['revisions'][-1]['text'] = s

    def _characters_mediawiki_page_revision_contributor_username(self, s):
        self._page['revisions'][-1]['user'] = 'username:' + s

    def _characters_mediawiki_page_revision_contributor_ip(self, s):
        self._page['revisions'][-1]['user'] = 'ip:' + s


def parsewpxml(file, page_handler):
    """Call WPXMLHandler.

    file
        This is the name of the file to parse.

    page_handler
        See WPXMLHandler.__init__.

    """
    parser = make_parser()
    wpxmlhandler = WPXMLHandler(page_handler)
    parser.setContentHandler(wpxmlhandler)
    parser.parse(file)


def main(argv=None,  # Defaults to sys.argv.
         input=sys.stdin, _open=open):

    """Run the application.

    The arguments are really there for dependency injection.

    """

    def page_handler(page):
        global db_cursor
        global db


        try:

                if 'redirect' in page:
                    synonym_data = {
                        'synonym': page['title'] + ';',
                        'redirect': page['redirect']
                    }

                    db_cursor.execute("""
                            UPDATE articles  
                            SET synonyms = 
                                IFNULL(CONCAT(synonyms, %(synonym)s), %(synonym)s)
                            WHERE title = %(redirect)s
                            """, synonym_data)
                    #print('Number of rows inserted: %d' % db_cursor.rowcount)
                    db.commit()
                    return

                """Write the right bits to the right files."""
                #print(page['title'])
                #print(page['title'])
                #print("page_id :",page['id'])
        #print(page['redirect'])
                #print("time :",page['revisions'][-1]['timestamp'])
                text = HTMLParser.HTMLParser().unescape(page['revisions'][-1]['text'])
                text = ''.join(BeautifulSoup(text).findAll(text=True))
                text = WikiExtractor.clean(text)
                text = ''.join(WikiExtractor.compact(text))
                #print(text)

                article_data = {
                    'id': page['id'],
                    'title': page['title'],
                    'timestamp': page['revisions'][-1]['timestamp'],
                    'text': text
                }
                print(page['id'])
                db_cursor.execute("""
                        INSERT INTO articles(id, title, timestamp, text) 
                            VALUES (%(id)s, %(title)s, %(timestamp)s, %(text)s)
                        """, article_data)

                #print('Number of rows inserted: %d' % db_cursor.rowcount)
                db.commit()
        except Exception, e:
            print >> sys.stderr, "invoked error. id : %s, %s" % (page['id'], e)
        
#        try:
#            atoms_writer.writerow((page['id'], page['title']))
#            for rev in page['revisions']:
#                if not 'user' in rev:
#                    continue
#                triplets_writer.writerow(
#                    (rev['user'], rev['timestamp'], page['id']))
#        except Exception, e:
#            print >> sys.stderr, "%s: %s\n%s" % (parser.get_prog_name(),
#                                                 e, page)

    # db connect 
    global db
    db = MySQLdb.connect(db='kowikipedia', user='root', passwd='2002!nfo', host='localhost', charset='utf8', use_unicode=True)

    global db_cursor
    db_cursor = db.cursor()

    parsewpxml(input, page_handler)

    # db close
    db_cursor.close()
#db.commit()
    db.close()

if __name__ == '__main__':
    main()
