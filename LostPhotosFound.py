#!/usr/bin/env python
# -*- coding: utf-8 -*-
# code is under GPLv2
# <caio1982@gmail.com>

import os
import sys
import time

# to build the mail object and pickle fields
from email import message_from_string
from email.header import decode_header
from email.utils import parsedate

# the working man (should we connect to IMAP as a read-only client btw?)
from imapclient import IMAPClient

# for configuration file
import ConfigParser

class Server:
    """ Server class to fetch and filter data

    Connects to the IMAP server, search according to a criteria,
    fetch all attachments of the mails matching the criteria and
    save them locally with a timestamp.

    """
    def __init__(self, host):
        if not host:
            raise Exception('Missing IMAP host parameter in your config')
        try:
            # isn't it ugly to have so many code inside a try?
            self.server = IMAPClient(host, use_uid=True, ssl=True)
            setattr(self.server, 'debug', True)
        except:
            raise Exception('Could not successfully connect to the IMAP host')

    def login(self, username, password):
        s = self.server

        if not username or not password:
            raise Exception('Missing username or password parameters')

        # you may want to hack this to only fetch attachments from a
        # different exclusive label (assuming you have them in english)
        all_mail = '[Gmail]/All Mail'
        
        try:
            s.login(username, password)
        except:
            raise Exception('Cannot login, check username/password, are you using 2-factor auth?')

        if not s.folder_exists(all_mail):
            for folder in s.xlist_folders():
                labels = folder[0]
                if 'AllMail' in labels[-1]:
                    all_mail = folder[2]
    
        s.select_folder(all_mail)
        self.session = s

    def _messages(self):
        # that's why we only support gmail
        # for other mail services we'd have to translate the custom
        # search to actual IMAP queries, thus no X-GM-RAW cookie to us
        criteria = 'X-GM-RAW "has:attachment filename:(jpg OR jpeg OR gif OR png OR tiff OR tif OR ico OR xbm OR bmp)"'
        try:
            messages = self.server.search([criteria])
        except:
            raise Exception('Search criteria return a failure, it must be a valid gmail search')    

        # stats logging
        print 'LOG: %d messages matched the search criteria %s' % (len(messages), criteria)
        return messages
 
    def lostphotosfound(self):
        messages = self._messages()
        server = self.server
        for m in messages:
            data = server.fetch([m], ['RFC822'])
            for d in data:
                # SEQ is also available
                mail = message_from_string(data[d]['RFC822'])
                if mail.get_content_maintype() != 'multipart':
                    continue
                
                # this whole mess up to the print statement
                # is only for debugging purposes, is it worth it? :-(
                header_from = mail["From"]
                if not decode_header(header_from).pop(0)[1]:
                    header_from = decode_header(header_from).pop(0)[0].decode('iso-8859-1').encode('utf-8')
                else:
                    header_from = decode_header(header_from).pop(0)[0].decode(decode_header(header_from).pop(0)[1]).encode('utf-8')
                
                header_subject = mail["Subject"]
                if not decode_header(header_subject).pop(0)[1]:
                    header_subject = decode_header(header_subject).pop(0)[0].decode('iso-8859-1').encode('utf-8')
                else:
                    header_subject = decode_header(header_subject).pop(0)[0].decode(decode_header(header_subject).pop(0)[1]).encode('utf-8')
               
                # more debugging
                print '[%s]: %s' % (header_from, header_subject)
        
                for part in mail.walk():
                    if part.get_content_maintype() == 'multipart':
                        continue
                    if part.get('Content-Disposition') is None:
                        continue
                    self._save_part(part, mail)
  
    def _save_part(self, part, mail):
        if not hasattr(self, "seq"):
            self.seq = 0;
    
        filename = decode_header(part.get_filename()).pop(0)[0].decode('iso-8859-1').encode('utf-8')
        if not filename:
            filename = 'attachment-%06d.bin' % (self.seq)
    	self.seq += 1
        
        header_date = parsedate(mail['date'])
        header_date = '%s-%s-%s_%s:%s:%s_' % (header_date[0],
                                              header_date[1],
                                              header_date[2],
                                              header_date[3],
                                              header_date[4],
                                              header_date[5])
        filename = header_date + filename
    
        username = config.get('gmail', 'username')
        if not os.path.isdir(username):
            os.mkdir(username)
    
        # logging complement
        print '\t...%s' % (filename)
    
        saved = os.path.join(username, filename)
        if not os.path.isfile(saved):
            f = open(saved, 'wb')

            # for some reason get_payload fails sometimes
            # it is suspected to happen when images are not
            # really multipart attachments but inline instead?
            f.write(part.get_payload(decode=True))
            f.close()
    
    def close(self):
        self.server.close_folder()
        self.server.logout()
    
class Config:
    """ Configuration file manager

    Locate, open and read configuration file options. Create a template
    if no configuration file is found.

    """
    def __init__(self):
        self._dir = os.path.expanduser('~/.LostPhotosFound')
        self._file = os.path.join(self._dir, 'config')

        if not os.path.isdir(self._dir):
            os.mkdir(self._dir, 0700)
            self._create_file()
        elif not os.path.isfile(self._file):
            self._create_file()
        
        self._config = ConfigParser.ConfigParser()
        self._config.read(self._file)

    def get(self, section, option):
        return self._config.get(section, option)

    def _create_file(self):
        config = ConfigParser.ConfigParser()
        config.add_section('gmail')
        config.set('gmail', 'host', 'imap.gmail.com')
        config.set('gmail', 'username', 'username@gmail.com')
        config.set('gmail', 'password', 'password')

        with open(self._file, 'w') as configfile:
            config.write(configfile)

        print '\nPlease edit your config file %s\n' % (self._file)
        sys.exit()

if __name__ == "__main__":
    config = Config()
    host = config.get('gmail', 'host')
    username = config.get('gmail', 'username')
    password = config.get('gmail', 'password')

    imap = Server(host)
    imap.login(username, password)
    imap.lostphotosfound()
    imap.close()

    print 'All done!'
    sys.exit()
