#!/usr/bin/env python

import pygtk
import gtk
import gtk.glade

import dbus
import dbus.mainloop.glib

# This map the type string to the actual python types
str_to_type = {'int' : int, 'bool' : bool, 'str' : str, 'var': object, 'dict': dict}
type_to_str = dict( (v,k) for k,v in str_to_type.iteritems() )

class MyApp(object):
    def __init__(self):
        self.w_tree = gtk.glade.XML('test_gtk.glade', 'main_window') 
        dic = {
            "on_main_window_destroy" : gtk.main_quit,
            "on_service_combobox_changed" : self.on_service_combobox_changed,
            "on_profile_combobox_changed" : self.on_profile_combobox_changed
        }
        self.w_tree.signal_autoconnect(dic)
        
        self.connection = None  # This is just to keep track of the dbus signal connection
        
        # We init the service list
        bus = dbus.SessionBus()
        conf_manager = bus.get_object("org.freesmartphone.preferencesd", "/Preferences")
        services = conf_manager.GetServicesName()
        service_combobox = self.w_tree.get_widget('service_combobox')
        for s in services:
            service_combobox.append_text(s)
        
        self.parameters = gtk.ListStore(str, str, str, str)
        self.init_parameters_treeview()
        
        window = self.w_tree.get_widget('main_window')
        window.show()
        

    def init_parameters_treeview(self):
        treeview = self.w_tree.get_widget('parameters_treeview')
        # The name column
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Parameters', cell)
        column.set_attributes(cell, text=0)
        treeview.append_column(column)
        # The value column
        def on_edited(w, path, new_text):
            key = self.parameters[path][0]
            type = self.parameters[path][2]
            type = str_to_type[type]
            new_value = type(eval(new_text))
            self.service.SetValue(key, new_value)
        
        cell = gtk.CellRendererText()
        cell.set_property("editable", True)
        cell.connect('edited', on_edited)
        def cell_data_function(celllayout, cell, model, iter):
            value = model[iter][1]
            cell.set_property('text', str(value))
        column = gtk.TreeViewColumn('Value', cell, text=1)
        column.set_cell_data_func(cell, cell_data_function)
        treeview.append_column(column)
        
        # The type column
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Type', cell)
        column.set_attributes(cell, text=2)
        treeview.append_column(column)
        
        # The profilable column
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Profilable', cell)
        column.set_attributes(cell, text=3)
        treeview.append_column(column)
        
        treeview.set_model(self.parameters)
        
    def on_service_combobox_changed(self, w):
        # first we get the service remote object
        service = w.get_active_text()
        bus = dbus.SessionBus()
        conf_manager = bus.get_object("org.freesmartphone.preferencesd", "/Preferences")
        service_path = conf_manager.GetService(service)
        self.service = bus.get_object("org.freesmartphone.preferencesd", service_path)
        # Then we get all the keys in this service 
        keys = self.service.GetKeys()
        # Now we populate our parameters list
        self.parameters.clear()
        for key in keys:
            print key
            value = self.service.GetValue(key)
            type_str = self.service.GetType(key)
            type = str_to_type[type_str]
            value = type(value)
            profilable = self.service.IsProfilable(key) and "Yes" or "No"
            self.parameters.append( (key, value, type_str, profilable) )
        # We also want to update the list when the service notify us of changes
        def on_notify(key, value):
            self.on_service_combobox_changed(w)
        if self.connection:
            self.connection.remove()    # We remove the previous connection, since we are going to create a new one
        self.connection = self.service.connect_to_signal('Notify', on_notify, dbus_interface="org.freesmartphone.Preferences.Service")

    def on_profile_combobox_changed(self, w):
        profile = w.get_active_text()
        bus = dbus.SessionBus()
        conf_manager = bus.get_object("org.freesmartphone.preferencesd", "/Preferences")
        conf_manager.SetProfile(profile)

if __name__ == "__main__":
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    app = MyApp()
    gtk.main()
