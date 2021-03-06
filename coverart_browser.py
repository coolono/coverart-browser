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

# define plugin
import rb
import locale
import gettext

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import RB
from gi.repository import GdkPixbuf
from gi.repository import Peas
from gi.repository import Gio

from coverart_browser_prefs import Preferences
from coverart_browser_prefs import GSetting
from coverart_browser_prefs import CoverLocale
from coverart_browser_source import CoverArtBrowserSource
from coverart_utils import Theme
import coverart_rb3compat as rb3compat

class CoverArtBrowserEntryType(RB.RhythmDBEntryType):
    '''
    Entry type for our source.
    '''
    def __init__(self):
        '''
        Initializes the entry type.
        '''
        RB.RhythmDBEntryType.__init__(self, name='CoverArtBrowserEntryType')


class CoverArtBrowserPlugin(GObject.Object, Peas.Activatable):
    '''
    Main class of the plugin. Manages the activation and deactivation of the
    plugin.
    '''
    __gtype_name = 'CoverArtBrowserPlugin'
    object = GObject.property(type=GObject.Object)

    def __init__(self):
        '''
        Initialises the plugin object.
        '''
        GObject.Object.__init__(self)
        if rb3compat.pygobject_version() < 3.9:
             GObject.threads_init()

    def do_activate(self):
        '''
        Called by Rhythmbox when the plugin is activated. It creates the
        plugin's source and connects signals to manage the plugin's
        preferences.
        '''

        print("CoverArtBrowser DEBUG - do_activate")
        self.shell = self.object
        self.db = self.shell.props.db

        try:
            entry_type = CoverArtBrowserEntryType()
            self.db.register_entry_type(entry_type)
        except NotImplementedError:
            entry_type = self.db.entry_register_type(
                'CoverArtBrowserEntryType')

        cl = CoverLocale()
        cl.switch_locale(cl.Locale.LOCALE_DOMAIN)

        entry_type.category = RB.RhythmDBEntryCategory.NORMAL
        
        group = RB.DisplayPageGroup.get_by_id('library')
        # load plugin icon
        theme = Gtk.IconTheme.get_default()
        rb.append_plugin_source_path(theme, '/icons')

        # lets assume that python3 versions of RB only has the new icon attribute in the source
        if rb3compat.PYVER >=3:
                iconfile = Gio.File.new_for_path(
                    rb.find_plugin_file(self, 'img/' + Theme(self).current\
                    + '/covermgr.png'))
                    
                self.source = CoverArtBrowserSource(
                        shell=self.shell,
                        name=_("CoverArt"), 
                        entry_type=entry_type,
                        plugin=self,
                        icon=Gio.FileIcon.new(iconfile), 
                        query_model=self.shell.props.library_source.props.base_query_model)
        else:
                what, width, height = Gtk.icon_size_lookup(Gtk.IconSize.LARGE_TOOLBAR)
                pxbf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    rb.find_plugin_file(self, 'img/' + Theme(self).current\
                    + '/covermgr.png'), width, height)

                self.source = CoverArtBrowserSource(
                        shell=self.shell,
                        name=_("CoverArt"), entry_type=entry_type,
                        plugin=self, pixbuf=pxbf,
                        query_model=self.shell.props.library_source.props.base_query_model)
                    
        self.shell.register_entry_type_for_source(self.source, entry_type)
        self.shell.append_display_page(self.source, group)

        self.source.props.query_model.connect('complete', self.load_complete)

        print("CoverArtBrowser DEBUG - end do_activate")

    def do_deactivate(self):
        '''
        Called by Rhythmbox when the plugin is deactivated. It makes sure to
        free all the resources used by the plugin.
        '''
        print("CoverArtBrowser DEBUG - do_deactivate")
        self.source.delete_thyself()
        del self.shell
        del self.db
        del self.source

        print("CoverArtBrowser DEBUG - end do_deactivate")

    def load_complete(self, *args, **kwargs):
        '''
        Called by Rhythmbox when it has completed loading all data
        Used to automatically switch to the browser if the user
        has set in the preferences
        '''
        gs = GSetting()
        setting = gs.get_setting(gs.Path.PLUGIN)

        if setting[gs.PluginKey.AUTOSTART]:
            GObject.idle_add(self.shell.props.display_page_tree.select,
                self.source)
                
    def _translation_helper(self):
        '''
        a method just to help out with translation strings
        it is not meant to be called by itself
        '''
        
        # define .plugin text strings used for translation
        plugin = _('CoverArt Browser')
        desc = _('Browse and play your albums through their covers')
        
        #. TRANSLATORS: This is the icon-grid view that the user sees
        #. TRANSLATORS: Please try to keep the translation to less than 8 characters
        tile = _('Tiles')
        
        #. TRANSLATORS: This is the cover-flow view the user sees - they can swipe album covers from side-to-side
        #. TRANSLATORS: Please try to keep the translation to less than 8 characters
        artist = _('Flow')
        
        #. TRANSLATORS: percentage size that the image will be expanded
        scale = _('Scale by %:')
