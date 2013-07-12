# -*- Mode: python; coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
#
# Copyright (C) 2012 - fossfreedom
# Copyright (C) 2012 - Agustin Carrasco
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA.

from coverart_external_plugins import CreateExternalPluginMenu
from gi.repository import WebKit
from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gio
from coverart_browser_prefs import GSetting
from coverart_album import AlbumsModel
from coverart_widgets import AbstractView
import rb
import json
import os
from os.path import expanduser
from xml.sax.saxutils import escape

from collections import namedtuple


class FlowShowingPolicy(GObject.Object):
    '''
    Policy that mostly takes care of how and when things should be showed on
    the view that makes use of the `AlbumsModel`.
    '''

    def __init__(self, flow_view):
        super(FlowShowingPolicy, self).__init__()

        self._flow_view = flow_view
        self.counter = 0
        self._has_initialised = False

    def initialise(self, album_manager):
        if self._has_initialised:
            return

        self._has_initialised = True
        self._album_manager = album_manager
        self._model = album_manager.model
        #self._connect_signals()

    def _connect_signals(self):
        self._model.connect('album-updated', self._album_updated)
        self._model.connect('visual-updated', self._album_updated)
        

    def _album_updated(self, model, album_path, album_iter):
        self.counter = self.counter + 1
        # this method is called once for every album in the model if the events above are connected
        #for row in self._model.store:
        #    print row[:]
        print model.get_from_path(album_path).cover.original


class CoverFlowView(AbstractView):
    __gtype_name__ = "CoverFlowView"

    name = 'coverflowview'

    def __init__(self, *args, **kwargs):
        super(CoverFlowView, self).__init__(*args, **kwargs)
        
        self.ext_menu_pos = 0
        self._external_plugins = None
        self.gs = GSetting()
        self.show_policy = FlowShowingPolicy(self)
        self.view = WebKit.WebView()
        self._last_album = None
        self._has_initialised = False
        self._flow_first_call = False
        
    def filter_changed(self, *args):
        print "############filter_changed"
        #for some reason three filter change events occur on startup
        path = rb.find_plugin_file(self.plugin, 'coverflow/index.html')
        f = open(path)
        string = f.read()
        f.close()

        string = self.flow.initialise(string, self.album_manager.model)
        string = string.replace('#BACKGROUND_COLOUR', 'white') # to be user-defined - black/white
        string = string.replace('#FACTOR', '1.5') # to be user-defined
        
        base =  os.path.dirname(path) + "/"
        self.view.load_string(string, "text/html", "UTF-8", "file://" + base)

        self.scroll_to_album()
        
    def get_view_icon_name(self):
        return "flowview.png"

    def scroll_to_album(self):

        def start_scroll(*args):
            self._flow_first_call = True
            self.flow.scroll_to_album(self.last_album, self.view)

        # hack - wait a couple of seconds on the very first time that
        # the flow has loaded to give it time to finish loading before
        # initiating the scroll otherwise the scroll signal will get lost
        if not self._flow_first_call:
            Gdk.threads_add_timeout(GLib.PRIORITY_DEFAULT_IDLE, 2000, start_scroll, None)
        else:
            self.flow.scroll_to_album(self.last_album, self.view)
        
    def initialise(self, source):
        print "###########initialise"
        if self._has_initialised:
            print "exited"
            return
            
        self._has_initialised = True

        self.source = source
        self.plugin = source.plugin
        self.album_manager = source.album_manager
        self.ext_menu_pos = 10

        # lets check that all covers have finished loading before
        # initialising the flowcontrol and other signals
        if not self.album_manager.cover_man.has_finished_loading:
            self.album_manager.cover_man.connect('load-finished', self.covers_loaded)
        else:
            self.covers_loaded()

    def covers_loaded(self, *args):
        print "#########coversloaded"
        self.flow = FlowControl(self)
        self.view.connect("notify::title", self.flow.receive_message_signal)
        self.album_manager.model.connect('album-updated', self.flow.update_album, self.view)
        self.album_manager.model.connect('visual-updated', self.flow.update_album, self.view)
        self.album_manager.model.connect('filter-changed', self.filter_changed)
        self.filter_changed()

    @property
    def last_album(self):
        return self._last_album

    @last_album.setter
    def last_album(self, new_album):
        if self._last_album != new_album:
            self._last_album = new_album
            self.source.click_count = 0
            self.selectionchanged_callback()

    def item_rightclicked_callback(self, album):
        if not self._external_plugins:
            # initialise external plugin menu support
            self._external_plugins = \
            CreateExternalPluginMenu("ca_covers_view",
                self.ext_menu_pos, self.popup)
            self._external_plugins.create_menu('popup_menu', True)
            
        self.last_album = album
        
        self.popup.get_gtkmenu(self.source, 'popup_menu').popup(None,
                        None, 
                        None,
                        None,
                        3,
                        Gtk.get_current_event_time())
            
    def item_clicked_callback(self, album):
        '''
        Callback called when the user clicks somewhere on the flow_view.
        Along with source "show_hide_pane", takes care of showing/hiding the bottom
        pane after a second click on a selected album.
        '''
        # to expand the entry view
        self.source.click_count += 1
            
        self.last_album = album

        if self.source.click_count == 1:
            Gdk.threads_add_timeout(GLib.PRIORITY_DEFAULT_IDLE, 250,
                self.source.show_hide_pane, album)

    def item_activated_callback(self, album):
        '''
        Callback called when the flow view is double clicked. It plays the selected album
        '''
        self.last_album = album
        self.source.play_selected_album()

        return True

    def get_selected_objects(self):
        if self.last_album:
            return [self.last_album]
        else:
            return []

    def select_and_scroll_to_path(self, path):
        album = self.source.album_manager.model.get_from_path(path)
        self.flow.scroll_to_album(album, self.view)

    def switch_to_view(self, source, album):
        self.initialise(source)
        self.show_policy.initialise(source.album_manager)
        
        self.last_album = album
        self.scroll_to_album()

class FlowBatch(object):
    def __init__(self):
        self.filename = []
        self.title = []
        self.caption = []
        self.identifier = []
        self.fetched = False

    def append(self, fullfilename, title, caption, identifier):
        self.filename.append(fullfilename)
        self.title.append(title)
        self.caption.append(caption)
        self.identifier.append(identifier)

    def html_elements(self):
        str = ""
        for loop in range(len(self.filename)):
            str = str + '<div class="item"><img class="content" src="' +\
                escape(self.filename[loop]) + '" title="' +\
                escape(self.title[loop]) + '" identifier="' +\
                self.identifier[loop] + '"/> <div class="caption">' +\
                escape(self.caption[loop]) + '</div> </div>'

        self.fetched = True
        return str

class FlowControl(object):
    batch_size = 50
    
    def __init__(self, callback_view):
        self.next_batch = 0
        self.batches = []
        self.album_identifier = {}
        self.callback_view = callback_view
        
    def get_flow_batch(self, args):
        messagevalue = args[0]
        index = int(args[1])

        obj = {}
        position = 'stop'

        if messagevalue == 'next':
            calc_batch = int(index / self.batch_size) + 1
                        
            if ((calc_batch >= self.next_batch) and
                (len(self.batches) > calc_batch) and
                (not self.batches[calc_batch].fetched)):

                position = 'last'
                chosen = self.batches[calc_batch]
                size = len(chosen.filename)
                params = []
            
                for index in range(0, size):
                    batch = {}
                    batch['filename'] = chosen.filename[index]
                    batch['title'] = chosen.title[index]
                    batch['caption'] = chosen.caption[index]
                    batch['identifier'] = chosen.identifier[index]

                    params.append(batch)
                obj['flowbatch'] = params
                self.batches[calc_batch].fetched = True
                self.next_batch = calc_batch + 1
        else:
            print ("unknown message %", messagevalue)
            
        obj['batchtype'] = position
        ret = json.dumps(obj)
        return ret

    def update_album(self, model, album_path, album_iter, webview):
        album = model.get_from_path(album_path)
        index = -1
        for row in self.album_identifier:
            if self.album_identifier[row] == album:
                index = row
                break

        if index == -1:
            return

        obj = {}
        obj['filename'] = album.cover.original
        obj['title'] = album.artist
        obj['caption'] = album.name
        obj['identifier'] = str(index)

        webview.execute_script("update_album('%s')" % json.dumps(obj))
                 
    def receive_message_signal(self, webview, param):
        # this will be key to passing stuff back and forth - need
        # to develop some-sort of message protocol to distinguish "events"
        
        title = webview.get_title()
        if (not title) or (title == '"clear"'):
            return

        args = json.loads(title)
        try:
            signal = args["signal"]
        except:
            print ("unhandled: %s " % title)
            return

        if signal == 'getflowbatch':
            s = self.get_flow_batch(args['param'])
            webview.execute_script("new_flow_batch('%s')" % s)
        elif signal == 'clickactive':
            self.callback_view.item_clicked_callback(self.album_identifier[int(args['param'][0])])
        elif signal == 'rightclickactive':
            self.callback_view.item_rightclicked_callback(
                self.album_identifier[int(args['param'][0])])
        elif signal == 'doubleclickactive':
            self.callback_view.item_activated_callback(self.album_identifier[int(args['param'][0])])
        else:
            print ("unhandled signal: %s" % signal)

    def scroll_to_album(self, album, webview):
        for row in self.album_identifier:
            if self.album_identifier[row] == album:
                webview.execute_script("scroll_to_identifier('%s')" % str(row))
                break

    def initialise(self, string, model):
        element = 0
        batch = None

        album_col = model.columns['album']
        pos = 0
        del self.batches[:]
        
        for row in model.store:
            if not (element < self.batch_size):
                batch = None
                element = 0
                pos = pos + 1
            
            if not batch:
                batch = FlowBatch()
                self.batches.append(batch)

            cover = row[album_col].cover.original.replace(
                'rhythmbox-missing-artwork.svg',
                'rhythmbox-missing-artwork.png')  ## need a white vs black when we change the background colour

            index = (pos*self.batch_size) + element
            self.album_identifier[index] = row[album_col]
            
            element = element + 1
            
            batch.append(
                fullfilename = cover,
                caption=row[album_col].name,
                title=row[album_col].artist,
                identifier=str(index))

        items = ""

        index = 0
        while index <  len(self.batches) and index != 3:
            items += self.batches[index].html_elements()
            index += 1

        self.next_batch = index
        
        if index != 0:
            self.callback_view.last_album = self.album_identifier[0]
        else:
            self.callback_view.last_album = None

        string = string.replace('#ITEMS', items)
        
        return string
        