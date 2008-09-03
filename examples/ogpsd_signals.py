#!/usr/bin/env python

import gobject
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from time import gmtime, strftime

name = 'org.freesmartphone.ogpsd'
path = '/org/freedesktop/Gypsy'

def onConnectionStatusChanged(constatus):
	print 'ConnectionStatusChanged: constatus = %u' % constatus,
	print '%s' % constatus and '(TRUE)' or '(FALSE)'
def onFixStatusChanged(fixstatus):
	print 'FixStatusChanged: fixstatus = %d' % fixstatus,
	if   fixstatus == 1: print '(NONE)'
	elif fixstatus == 2: print '(2D)'
	elif fixstatus == 3: print '(3D)'
	else:                print '(INVALID)'
def onPositionChanged(fields, tstamp, lat, lon, alt):
	print 'PositionChanged:',
	print 'fields = %d,' % fields,
	print 'tstamp = %d (%s),' % (tstamp, strftime('%F %T', gmtime(tstamp))),
	print 'lat = %f (%s),' % (lat, fields & (1 << 0) and 'OK' or 'INVALID'),
	print 'lon = %f (%s),' % (lon, fields & (1 << 1) and 'OK' or 'INVALID'),
	print 'alt = %f (%s)'  % (alt, fields & (1 << 2) and 'OK' or 'INVALID')
def onAccuracyChanged(fields, pdop, hdop, vdop):
	print 'AccuracyChanged:',
	print 'fields = %d,' % fields,
	print 'pdop = %f (%s),' % (pdop, fields & (1 << 0) and 'OK' or 'INVALID'),
	print 'hdop = %f (%s),' % (hdop, fields & (1 << 1) and 'OK' or 'INVALID'),
	print 'vdop = %f (%s)'  % (vdop, fields & (1 << 2) and 'OK' or 'INVALID')
def onCourseChanged(fields, tstamp, speed, heading, climb):
	print 'CourseChanged:',
	print 'fields = %d,' % fields,
	print 'tstamp = %d (%s),' % (tstamp, strftime('%F %T', gmtime(tstamp))),
	print 'speed = %f (%s),'   % (speed,   fields & (1 << 0) and 'OK' or 'INVALID'),
	print 'heading = %f (%s),' % (heading, fields & (1 << 1) and 'OK' or 'INVALID'),
	print 'climb = %f (%s)'    % (climb,   fields & (1 << 2) and 'OK' or 'INVALID')
def onTimeChanged(time):
	print 'TimeChanged: time = %d (%s)' % (time, strftime('%F %T', gmtime(time)))
def onSatellitesChanged(satellites):
	print 'SatellitesChanged:'
	for (satIndex, sat) in enumerate(satellites):
		print '\tindex = %d,' % satIndex,
		print 'prn = %u,' % sat[0],
		print 'used = %u (%s),' % (sat[1], sat[1] and 'TRUE' or 'FALSE'),
		print 'elevation = %u,' % sat[2],
		print 'azimuth = %u,' % sat[3],
		print 'snr = %u' % sat[4]

DBusGMainLoop(set_as_default=True)
mainloop = gobject.MainLoop()
bus = dbus.SystemBus()

bus.add_signal_receiver(onConnectionStatusChanged, 'ConnectionStatusChanged', 'org.freedesktop.Gypsy.Device', name, path)
bus.add_signal_receiver(onFixStatusChanged, 'FixStatusChanged', 'org.freedesktop.Gypsy.Device', name, path)
bus.add_signal_receiver(onPositionChanged, 'PositionChanged', 'org.freedesktop.Gypsy.Position', name, path)
bus.add_signal_receiver(onAccuracyChanged, 'AccuracyChanged', 'org.freedesktop.Gypsy.Accuracy', name, path)
bus.add_signal_receiver(onCourseChanged, 'CourseChanged', 'org.freedesktop.Gypsy.Course', name, path)
bus.add_signal_receiver(onTimeChanged, 'TimeChanged', 'org.freedesktop.Gypsy.Time', name, path)
bus.add_signal_receiver(onSatellitesChanged, 'SatellitesChanged', 'org.freedesktop.Gypsy.Satellite', name, path)

mainloop.run()

