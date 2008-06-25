#!/usr/bin/env bash

# We assume that the framework deamon is running

echo "== test of the DBus service : org.freesmartphone.opreferencesd =="

echo "Get the 'profiles' service object"
dbus-send --system --print-reply --dest=org.freesmartphone.opreferencesd /org/freesmartphone/Preferences org.freesmartphone.Preferences.GetService string:'profiles'


echo "Ask for the profiles parameter of the profiles service"
dbus-send --system --print-reply --dest=org.freesmartphone.opreferencesd /org/freesmartphone/Preferences/profiles org.freesmartphone.Preferences.Service.GetValue string:'profiles'
