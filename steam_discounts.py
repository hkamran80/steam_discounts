#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author: Ricardo Garcia
# Code released to the public domain.
#
import HTMLParser
import htmlentitydefs
import itertools
import re

class Entry(object):
    def __init__(self):
        self.title = u''
        self.orig_price = u''
        self.discount = u''
        self.price = u''
        self.url = u''

    # Entries can be sorted by title.
    def __cmp__(self, other):
        return cmp(self.title.lower(), other.title.lower())

    # Entries can be hashed by URL.
    def __hash__(self):
        return hash(self.url)
    
class DiscountsParser(HTMLParser.HTMLParser):
    def __init__(self):
        self.url_re_ = re.compile(
                r'^(http://store\.steampowered\.com/(?:app|sub)/\d+/)')
        HTMLParser.HTMLParser.__init__(self)
    
    @staticmethod
    def entity2uni(name):
        return unichr(htmlentitydefs.name2codepoint[name])

    @staticmethod
    def ref2uni(ref):
        return unichr(int(ref))

    def reset(self):
        HTMLParser.HTMLParser.reset(self)

        self.current_entry_ = None
        self.entries_ = []

        self.in_h4_ = False
        self.in_discount_pct_ = False
        self.in_tab_price_ = False
        self.in_strike_ = False

    def handle_starttag(self, tag, attrs):
        attrs_map = dict(attrs)

        if tag == 'a':
            match = self.url_re_.search(attrs_map.get('href', ''))
            if match is not None:
                # First field to extract, hence new entry.
                self.current_entry_ = Entry()
                self.current_entry_.url += match.group(1)

        if tag == 'h4':
            self.in_h4_ = True

        elif tag == 'div':
            if attrs_map.get('class', '') == 'tab_discount discount_pct':
                self.in_discount_pct_ = True
            elif attrs_map.get('class', '') == 'tab_price':
                self.in_tab_price_ = True

        elif tag == 'strike':
            self.in_strike_ = True
    
    def handle_endtag(self, tag):
        if tag == 'h4':
            self.in_h4_ = False

        elif tag == 'div':
            if self.in_discount_pct_:
                self.in_discount_pct_ = False
            elif self.in_tab_price_:
                self.in_tab_price_ = False
                # This was the last field to extract.
                self.entries_.append(self.current_entry_)

        elif tag == 'strike':
            self.in_strike_ = False

    def append_text(self, text):
        if self.in_h4_:
            self.current_entry_.title += text
        elif self.in_discount_pct_:
            self.current_entry_.discount += text
        elif self.in_strike_:
            self.current_entry_.orig_price += text
        elif self.in_tab_price_:
            # Note we only enter here if not in <strike>.
            self.current_entry_.price += text

    def handle_data(self, data):
        self.append_text(data.strip())
    
    def handle_entityref(self, name):
        self.append_text(self.entity2uni(name))
    
    def handle_charref(self, ref):
        self.append_text(self.ref2uni(ref))
    
    # Behave like a sequence of Entries.
    def __len__(self):
        return self.entries_.__len__()

    def __getitem__(self, key):
        return self.entries_.__getitem__(key)

    def __iter__(self):
        return self.entries_.__iter__()

    def __reversed__(self):
        return self.entries_.__reversed__()

    def __contains__(self, item):
        return self.entries_.__contains__(item)

# Program entry point.
if __name__ == '__main__':
    # Extra imports
    import os
    import re
    import subprocess
    import sys
    #import urllib
    import requests
    
    # Constants.
    TITLE_WIDTH = 40
    MAX_BATCH_SIZE = 10

    # Get the number of discounts first.
    conn = requests.get('http://store.steampowered.com/search/?specials=1')
    page = conn.text
    mo = re.search(r'showing.*of +(\d+)', page)
    if mo is not None:
        max_discounts = int(mo.group(1))
    else:
        sys.exit('ERROR: unable to obtain the number of discounts')

    # Retrieve the discounts.
    obtained = 0
    remaining = max_discounts
    batches = []

    while remaining > 0:
        # Get batch page.
        batch_size = min(remaining, MAX_BATCH_SIZE)
        discounts_url = \
            'http://store.steampowered.com/search/tab?bHoverEnabled=true&' + \
            'style=&navcontext=1_4_4_&tab=Discounts&start=%d&count=%d' % \
            (obtained, batch_size)

        conn = requests.get(discounts_url)
        page = conn.text
        encoding = conn.headers['charset']
        page = page.decode(encoding)

        # Debug.
        #file('page%s.html' % (obtained, ), "w").write(page.encode('utf-8'))

        # Parse discounts.
        discounts_parser = DiscountsParser()
        discounts_parser.feed(page)

        # Compose output.
        batches.append(discounts_parser)
        # Update data
        received_size = len(discounts_parser)
        obtained += received_size
        remaining -= received_size

        # The server sometimes "lies" about the exact number of discounts.
        if received_size < batch_size:
            break

    # Compose output.
    entries = sorted(list(set(itertools.chain(*batches))))
    output = 'Listing %d discounts.\n' % (len(entries), )
    for entry in entries:
        output += (u'%s ...%s %7s [%12s] -- %s\n' %
                (
                    entry.title[:TITLE_WIDTH],
                    '.' * (TITLE_WIDTH - len(entry.title)),
                    entry.price,
                    u'%7s %s' % (entry.orig_price, entry.discount),
                    entry.url,
                    )
                ).encode('utf-8')

    # Print output, paging it if appropriate.
    if sys.stdout.isatty():
        cmd = os.getenv('PAGER', default='less')
        pager = subprocess.Popen(cmd.split(), stdin=subprocess.PIPE)
        pager.stdin.write(output)
        pager.stdin.close()
        pager.wait()
    else:
        sys.stdout.write(output)
