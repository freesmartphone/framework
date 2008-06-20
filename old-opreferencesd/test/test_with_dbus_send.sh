#!/usr/bin/env bash

# Simple test script that start the server, then try a few dus-send commands



run_test() {
    # Get the phone service
    dbus-send --print-reply --dest=org.freesmartphone.preferencesd /Preferences org.freesmartphone.Preferences.GetService string:'phone'
    # Get the value of the 'ring-volume' parameter
    dbus-send --print-reply --dest=org.freesmartphone.preferencesd /Preferences/phone org.freesmartphone.Preferences.Service.Get string:'ring-volume'
}


# Start the server, using this directory as a root for the conf files
../preferencesd/preferenced . &
run_test
